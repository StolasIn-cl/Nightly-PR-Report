"""Validate LLM-generated author-notes HTML against nightly report data."""

import argparse
from collections import Counter
import html
from html.parser import HTMLParser
import json
import re
import sys


def required_priorities(review_markdown: str | None) -> set[str]:
    """Return the P1/P2 findings explicitly present in a review."""
    return set(required_priority_counts(review_markdown))


def required_priority_counts(review_markdown: str | None) -> Counter[str]:
    """Count each explicit P1/P2 finding in a review."""
    return Counter(priority.upper() for priority in re.findall(
        r"\[(P[12])\]", review_markdown or "", re.I
    ))


class _AuthorNotesParser(HTMLParser):
    """Extract each PR entry's run URL, rendered summary text, and labels."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict] = []
        self._depth = 0
        self._entry: dict | None = None
        self._entry_depth: int | None = None
        self._paragraph: dict | None = None
        self._paragraph_depth: int | None = None
        self._priority_label: dict | None = None
        self._priority_label_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "div" and "pr-entry" in classes:
            self._entry = {
                "href": None,
                "summary": [],
                "paragraphs": [],
                "orphan_labels": [],
            }
            self.entries.append(self._entry)
            self._entry_depth = self._depth
        if self._entry is None:
            return
        if tag == "a" and self._entry["href"] is None:
            self._entry["href"] = attributes.get("href")
        if tag == "p":
            self._paragraph = {"content": [], "labels": []}
            self._entry["paragraphs"].append(self._paragraph)
            self._paragraph_depth = self._depth
        if "priority-label" in classes:
            priority_classes = sorted(
                class_name.removeprefix("priority-").upper()
                for class_name in classes
                if re.fullmatch(r"priority-p\d+", class_name, re.I)
            )
            self._priority_label = {
                "priority": priority_classes[0] if len(priority_classes) == 1 else None,
                "priority_classes": priority_classes,
                "text": [],
            }
            self._priority_label_depth = self._depth
            if self._paragraph is None:
                self._entry["orphan_labels"].append(self._priority_label)
            else:
                self._paragraph["labels"].append(self._priority_label)
                self._paragraph["content"].append(("label", self._priority_label))

    def handle_endtag(self, tag: str) -> None:
        if self._priority_label_depth == self._depth:
            self._priority_label = None
            self._priority_label_depth = None
        if (self._entry is not None and tag == "p"
                and self._depth == self._paragraph_depth):
            self._paragraph = None
            self._paragraph_depth = None
        if (self._entry is not None and tag == "div"
                and self._depth == self._entry_depth):
            self._entry = None
            self._entry_depth = None
            self._paragraph = None
            self._paragraph_depth = None
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._priority_label is not None:
            self._priority_label["text"].append(data)
        elif self._entry is not None and self._paragraph is not None:
            self._entry["summary"].append(data)
            if data.strip():
                self._paragraph["content"].append(("text", data))


def _rendered_text(parts: list[str]) -> str:
    return " ".join(html.unescape("".join(parts)).split())


def validate_author_notes(data: dict, author_html: str) -> list[str]:
    """Return author-notes validation errors, or an empty list when valid."""
    parser = _AuthorNotesParser()
    parser.feed(author_html)
    parser.close()

    entries_by_run_url: dict[str, list[dict]] = {}
    for entry in parser.entries:
        href = entry["href"]
        if href:
            entries_by_run_url.setdefault(href, []).append(entry)

    errors = []
    for pr in data.get("prs", []):
        summary = pr.get("summary") or {}
        run_url = summary.get("run_url")
        title = summary.get("title") or ""
        review_markdown = pr.get("review_markdown")
        required = required_priority_counts(review_markdown)
        entries = entries_by_run_url.get(run_url, [])

        if not entries:
            errors.append(f"Missing author-notes entry for {run_url or title}.")
            continue

        rendered_summaries = [_rendered_text(entry["summary"]) for entry in entries]
        title_only_phrases = {
            f"This PR addresses {title}.",
            f"This PR covers: {title}",
        }
        if review_markdown and any(text in title_only_phrases for text in rendered_summaries):
            errors.append(f"title-only summary for reviewed PR {run_url or title}.")

        present: Counter[str] = Counter()
        for entry in entries:
            for label in entry["orphan_labels"]:
                errors.append(
                    f"Priority label must be in its own summary paragraph for "
                    f"{run_url or title}."
                )
            for paragraph in entry["paragraphs"]:
                labels = paragraph["labels"]
                if len(labels) > 1:
                    errors.append(
                        f"Summary paragraph has multiple priority labels for "
                        f"{run_url or title}."
                    )
                if labels and (
                    not paragraph["content"]
                    or paragraph["content"][0][0] != "label"
                ):
                    errors.append(
                        f"Priority label must be the paragraph's first meaningful content "
                        f"for {run_url or title}."
                    )
                for label in labels:
                    priority = label["priority"]
                    label_text = _rendered_text(label["text"]).upper()
                    if priority not in {"P1", "P2"} or label_text != priority:
                        classes = " ".join(label["priority_classes"]) or "missing priority class"
                        errors.append(
                            f"Unsupported priority label ({classes}) for "
                            f"{run_url or title}."
                        )
                        continue
                    present[priority] += 1

        for priority in ("P1", "P2"):
            expected_count = required[priority]
            actual_count = present[priority]
            if actual_count < expected_count:
                errors.append(
                    f"Expected {expected_count} {priority} priority label(s), found "
                    f"{actual_count}, for {run_url or title}."
                )
            elif actual_count > expected_count:
                errors.append(
                    f"Invented {priority} priority label(s): expected {expected_count}, "
                    f"found {actual_count}, for {run_url or title}."
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="Path to nightly-report-data.json")
    parser.add_argument("--html", required=True, help="Path to Author Notes HTML fragment")
    args = parser.parse_args()

    with open(args.data, encoding="utf-8") as data_file:
        data = json.load(data_file)
    with open(args.html, encoding="utf-8") as html_file:
        author_html = html_file.read()

    errors = validate_author_notes(data, author_html)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
