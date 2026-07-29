"""Validate LLM-generated author-notes HTML against nightly report data."""

import argparse
import html
from html.parser import HTMLParser
import json
import re
import sys


def required_priorities(review_markdown: str | None) -> set[str]:
    """Return the P1/P2 findings explicitly present in a review."""
    return {priority.upper() for priority in re.findall(
        r"\[(P[12])\]", review_markdown or "", re.I
    )}


class _AuthorNotesParser(HTMLParser):
    """Extract each PR entry's run URL, rendered summary text, and labels."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict] = []
        self._depth = 0
        self._entry: dict | None = None
        self._entry_depth: int | None = None
        self._in_summary = False
        self._priority_label_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._depth += 1
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "div" and "pr-entry" in classes:
            self._entry = {"href": None, "summary": [], "priorities": set()}
            self.entries.append(self._entry)
            self._entry_depth = self._depth
        if self._entry is None:
            return
        if tag == "a" and self._entry["href"] is None:
            self._entry["href"] = attributes.get("href")
        if tag == "p":
            self._in_summary = True
        if "priority-label" in classes:
            self._priority_label_depth = self._depth
            if "priority-p1" in classes:
                self._entry["priorities"].add("P1")
            if "priority-p2" in classes:
                self._entry["priorities"].add("P2")

    def handle_endtag(self, tag: str) -> None:
        if self._entry is not None and tag == "p":
            self._in_summary = False
        if self._priority_label_depth == self._depth:
            self._priority_label_depth = None
        if (self._entry is not None and tag == "div"
                and self._depth == self._entry_depth):
            self._entry = None
            self._entry_depth = None
            self._in_summary = False
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        if (self._entry is not None and self._in_summary
                and self._priority_label_depth is None):
            self._entry["summary"].append(data)


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
        required = required_priorities(review_markdown)
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

        present = set().union(*(entry["priorities"] for entry in entries))
        for priority in sorted(required):
            if priority not in present:
                errors.append(f"Missing {priority} priority label for {run_url or title}.")

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
