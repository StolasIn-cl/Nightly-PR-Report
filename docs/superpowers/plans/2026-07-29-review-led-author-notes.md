# Review-led Author Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate review-led Author Notes with compact P1/P2 labels and write a validated local PDF without sending email.

**Architecture:** A Python validator consumes the report JSON and subagent HTML. It identifies note entries by action-run URL, rejects title-only fallback, and requires priority labels for explicit P1/P2 findings. CSS supplies label-only colour, and the report workflow prompt becomes review-first.

**Tech Stack:** Python 3 standard library (`html.parser`, `json`, `re`, `unittest`), existing report HTML/CSS, WeasyPrint, Poppler.

## Global Constraints

- Never open Outlook, attach a file, send email, or modify `run-status.json`.
- Preserve every PR entry, author group, PR link, and title.
- Use only source title, commit text, and review text; do not invent risks.
- Colour only a compact leading P1/P2 label, not the summary sentence.
- Render null review text as `review unavailable`.

---

### Task 1: Validator

**Files:** Create `scripts/validate_author_notes.py`; create `scripts/tests/test_validate_author_notes.py`.

**Interfaces:** `required_priorities(review_markdown: str | None) -> set[str]`; `validate_author_notes(data: dict, author_html: str) -> list[str]`; CLI arguments `--data` and `--html`, with non-zero exit status for errors.

- [ ] **Step 1: Write failing tests**

```python
def test_accepts_review_summary_with_p1_label():
    self.assertEqual(validator.validate_author_notes(FIXTURE_DATA, AUTHOR_HTML_WITH_P1), [])

def test_rejects_title_only_summary_for_reviewed_pr():
    self.assertIn("title-only", "\n".join(validator.validate_author_notes(FIXTURE_DATA, TITLE_ONLY_AUTHOR_HTML)))

def test_rejects_missing_p2_label_for_explicit_p2_finding():
    self.assertIn("P2", "\n".join(validator.validate_author_notes(FIXTURE_DATA, AUTHOR_HTML_WITHOUT_P2)))
```

- [ ] **Step 2: Verify RED** — run `python -m unittest scripts.tests.test_validate_author_notes -v`; expect an import or missing-interface failure.

- [ ] **Step 3: Implement** — use `HTMLParser` to pair `pr-entry` link hrefs with rendered summary text. Match duplicate PRs by `run_url`; HTML-unescape before rejecting exact `This PR addresses {title}.` or `This PR covers: {title}` phrases. Use `re.findall(r"\\[(P[12])\\]", review_markdown or "", re.I)` to require matching `priority-label priority-p1` or `priority-p2` markup.

- [ ] **Step 4: Verify GREEN** — run `python -m unittest scripts.tests.test_validate_author_notes -v`; expect PASS.

- [ ] **Step 5: Commit** — stage only `scripts/validate_author_notes.py` and `scripts/tests/test_validate_author_notes.py`, then commit `feat: validate review-led author notes`.

### Task 2: Priority-label CSS

**Files:** Modify `scripts/new_pr_report_html.py:650-710`; modify `scripts/tests/test_new_pr_report_html.py`.

**Interfaces:** Author HTML may use `priority-label`, `priority-p1`, and `priority-p2`; style remains confined to those classes.

- [ ] **Step 1: Write failing test**

```python
def test_report_styles_priority_labels_without_coloring_note_bodies(self):
    report_html = self.render_report_with_full_coverage()
    self.assertIn(".priority-label", report_html)
    self.assertIn(".priority-p1", report_html)
    self.assertIn(".priority-p2", report_html)
```

- [ ] **Step 2: Verify RED** — run `python -m unittest scripts.tests.test_new_pr_report_html.ReportLayoutTests.test_report_styles_priority_labels_without_coloring_note_bodies -v`; expect failure.

- [ ] **Step 3: Implement CSS** — add `.priority-label { border-radius: 3px; font-size: 10px; font-weight: 700; padding: 1px 5px; }`, `.priority-p1 { background: #fce8e6; color: #b3261e; }`, and `.priority-p2 { background: #fff3e0; color: #b06000; }`. Do not modify `.pr-entry p` colour.

- [ ] **Step 4: Verify GREEN** — run `python -m unittest scripts.tests.test_new_pr_report_html -v`; expect PASS.

- [ ] **Step 5: Commit** — stage the generator and test, then commit `feat: style author-note priority labels`.

### Task 3: Review-first subagent workflow

**Files:** Modify `SKILL.md:76-205`.

**Interfaces:** The subagent returns raw author-card HTML; any explicit P1/P2 review begins with `<span class="priority-label priority-p1">P1</span>` or its P2 equivalent.

- [ ] **Step 1: Update prompt** — explicit P1/P2 findings must lead with the matching label and concisely paraphrase the reviewed impact. Reviewed PRs without findings must state reviewed behaviour or no actionable regression. Titles and commit text are context only, never the whole summary.

- [ ] **Step 2: Update HTML example** — include `<p><span class="priority-label priority-p1">P1</span> The review found ...</p>`.

- [ ] **Step 3: Update gates** — replace literal `high-risk`/`dangerous` detection with explicit P1/P2 finding handling; keep the no-invented-risk rule.

- [ ] **Step 4: Set local-only boundary** — document a stop after local PDF validation, skipping Outlook, attachment, send, and status writing.

- [ ] **Step 5: Commit** — stage only `SKILL.md`, then commit `docs: make author-note reviews actionable`.

### Task 4: Subagent generation and local verification

**Files:** Generate `author-slim.json`, `author-summary.html`, `nightly-report.html`, and `nightly-report.pdf`.

**Interfaces:** Consumes source report data, skeleton, subagent response, and validator; produces non-empty local PDF with no placeholder and zero validation errors.

- [ ] **Step 1: Generate inputs** — run the skeleton generator and derive the slim schema from `SKILL.md` into `author-slim.json`.

- [ ] **Step 2: Dispatch one subagent** — request raw HTML covering every source run URL, grouped by author, with priority labels and review-led summaries.

- [ ] **Step 3: Validate** — run `python scripts/validate_author_notes.py --data nightly-report-data.json --html author-summary.html`; require exit code 0 and `Author Notes validation passed`.

- [ ] **Step 4: Insert and render** — replace exactly one `<!-- AUTHOR_SUMMARY -->` and use WeasyPrint to generate a non-empty `nightly-report.pdf`.

- [ ] **Step 5: Verify** — run all Python tests, render Author Notes pages with Poppler PNG, and confirm labels, zero generic fallback, no placeholder, and no clipping or overlap.

- [ ] **Step 6: Stop** — do not invoke Chrome/Outlook and do not update `run-status.json`.
