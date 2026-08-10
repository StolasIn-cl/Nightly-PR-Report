# Dart Coverage Delta Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split Dart Coverage Delta file changes into New, Coverage Increased, and Coverage Decreased groups while omitting unchanged entries.

**Architecture:** Keep `build_coverage_delta_section` as the public renderer. Add small helpers in `scripts/new_pr_report_html.py` to classify, order, and render coverage rows, then compose only non-empty groups into the existing section wrapper. Use the existing section-label, table, and row-cap patterns from Nightly Rebuild Timing.

**Tech Stack:** Python 3 standard library, `unittest`, HTML strings.

## Global Constraints

- Preserve the current total-coverage header and no-data behavior.
- Omit zero-delta entries.
- Cap rows and render the `+N more` note independently for each group.
- Preserve unrelated in-progress timing changes in the same files.

---

### Task 1: Grouped Coverage Delta Renderer

**Files:**

- Modify: `scripts/tests/test_new_pr_report_html.py`
- Modify: `scripts/new_pr_report_html.py`

**Interfaces:**

- Consumes: a `dart_coverage_delta` object whose `files` entries contain `path`, `status`, `previous_pct`, `current_pct`, and `delta_pct`.
- Produces: `build_coverage_delta_section(delta) -> str` with named non-empty groups.

- [x] **Step 1: Write failing tests for classification, ordering, omission, and caps**

```python
def test_coverage_delta_groups_new_increased_and_decreased(self):
    html = rpt.build_coverage_delta_section({
        "total": {"current_line_pct": 70, "delta_line_pct": 1},
        "files": [
            {"path": "lib/new.dart", "status": "new", "previous_pct": None, "current_pct": 60, "delta_pct": None},
            {"path": "lib/small_gain.dart", "previous_pct": 70, "current_pct": 71, "delta_pct": 1},
            {"path": "lib/large_gain.dart", "previous_pct": 40, "current_pct": 50, "delta_pct": 10},
            {"path": "lib/loss.dart", "previous_pct": 90, "current_pct": 80, "delta_pct": -10},
            {"path": "lib/unchanged.dart", "previous_pct": 50, "current_pct": 50, "delta_pct": 0},
        ],
    })
    self.assertIn("New &mdash; 1 file(s)", html)
    self.assertIn("Coverage Increased &mdash; 2 file(s)", html)
    self.assertIn("Coverage Decreased &mdash; 1 file(s)", html)
    self.assertLess(html.index("large_gain.dart"), html.index("small_gain.dart"))
    self.assertNotIn("unchanged.dart", html)
```

- [x] **Step 2: Run the focused test and confirm it fails because group labels are absent**

Run: `python -m unittest scripts.tests.test_new_pr_report_html.CoverageDeltaSectionTests.test_coverage_delta_groups_new_increased_and_decreased -v`

Expected: FAIL because the current renderer has no grouped labels and includes the unchanged row.

- [x] **Step 3: Add minimal grouping and rendering helpers**

```python
def _coverage_delta_groups(files):
    groups = {"new": [], "increased": [], "decreased": []}
    for entry in files:
        delta = entry.get("delta_pct")
        if entry.get("previous_pct") is None:
            groups["new"].append(entry)
        elif delta is not None and delta > 0:
            groups["increased"].append(entry)
        elif delta is not None and delta < 0:
            groups["decreased"].append(entry)
    groups["increased"].sort(key=lambda entry: entry["delta_pct"], reverse=True)
    groups["decreased"].sort(key=lambda entry: entry["delta_pct"])
    return groups
```

Render each non-empty group with the existing four-column table shape, its own row cap, and a coloured section label.

- [x] **Step 4: Run the focused tests and confirm they pass**

Run: `python -m unittest scripts.tests.test_new_pr_report_html.CoverageDeltaSectionTests -v`

Expected: PASS.

- [x] **Step 5: Run the complete renderer test module**

Run: `python -m unittest scripts.tests.test_new_pr_report_html -v`

Expected: PASS with existing timing tests unchanged.

- [ ] **Step 6: Commit only when the user requests it**
