# Nightly Report Artifact Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read the current nightly-rebuild artifacts, render Dart/C++/combined coverage plus C++ failure diagnostics, remove obsolete data-branch files, and create a PDF without sending email.

**Architecture:** The fetcher becomes the compatibility boundary: it reads current artifact names from `origin/data/test-mapping` into explicit report-payload keys. The HTML generator renders these payload fields independently so incomplete native coverage remains diagnostic rather than fatal. Data-branch deletion happens only after the script tests pass; the PDF run reads the resulting remote branch state.

**Tech Stack:** Python 3 standard library, `unittest`, Git, WeasyPrint (or its existing Chromium fallback for PDF conversion).

## Global Constraints

- Use `full-coverage-summary.json` status fields; never turn missing, `incomplete`, or `not_applicable` coverage into 0%.
- Read `dart-failed-tests.json`, `cpp-failed-tests.json`, and `dart-test-timings*.json`; do not read their replaced artifact names.
- C++ failure output contains package and reason only; it must not infer or display an author.
- Keep `codebase-coverage.json`, current coverage artifacts, Dart-prefixed timings, mapping data, and retained `pr-runs/` data.
- Delete only `mapping-fragment-*.json`, `rebuild-failed-tests.json`, `cpp-coverage-failures.json`, `test-timings.json`, and `test-timings-previous.json` from `data/test-mapping`.
- Do not send email or write an email-success run status.

---

### Task 0: Restore the setup-template test contract

**Files:**
- Modify: `scripts/tests/test_setup_nightly_report.py:84-105`

**Interfaces:**
- Confirms that `setup_nightly_report.py` preserves the `SKILL.md` template
  and renders a `SKILL.local.md` whose only resolved placeholders are the
  ones currently used by the template.

- [ ] **Step 1: Make the stale assertion match the current template contract**

Replace the obsolete `{{REPORT_EMAIL}}` assertion with assertions that the
template retains `{{NR_DIR_WINDOWS}}` and `{{SCRIPT_SOURCE_WINDOWS}}`, while
the rendered local skill contains the workspace path and no longer contains
those two placeholders.

- [ ] **Step 2: Run the baseline suite to verify the repair**

Run: `python -m unittest discover -s scripts/tests -v`

Expected: PASS; the test no longer expects the removed `{{REPORT_EMAIL}}`
placeholder.

- [ ] **Step 3: Commit the baseline-test repair**

```bash
git add scripts/tests/test_setup_nightly_report.py
git commit -m "test: align setup skill template assertions"
```

### Task 1: Fetch the current artifact contract

**Files:**
- Create: `scripts/tests/test_get_nightly_report_data.py`
- Modify: `scripts/get_nightly_report_data.py:24-110`

**Interfaces:**
- Produces `load_branch_artifacts(ref: str, git_root: str) -> dict`.
- Produces report keys `full_coverage_summary`, `dart_failed_tests`,
  `cpp_failed_tests`, `dart_test_timings`, and `dart_test_timings_previous`.
- Continues producing `codebase_coverage` for the existing Dart aggregate.

- [ ] **Step 1: Write the failing fetch-contract tests**

```python
class BranchArtifactTests(unittest.TestCase):
    def test_load_branch_artifacts_uses_current_names(self):
        with mock.patch.object(fetcher, "git_show", side_effect=fake_git_show) as show:
            artifacts = fetcher.load_branch_artifacts("origin/data/test-mapping", "repo")

        self.assertEqual(artifacts["full_coverage_summary"]["schema_version"], 1)
        self.assertEqual(artifacts["cpp_failed_tests"]["failed_package_count"], 1)
        self.assertEqual(artifacts["dart_test_timings"]["metadata"]["test_count"], 2)
        requested = [call.args[1] for call in show.call_args_list]
        self.assertNotIn("rebuild-failed-tests.json", requested)
        self.assertNotIn("cpp-coverage-failures.json", requested)
        self.assertNotIn("test-timings.json", requested)

    def test_load_branch_artifacts_returns_none_for_missing_optional_artifact(self):
        with mock.patch.object(fetcher, "git_show", return_value=None):
            artifacts = fetcher.load_branch_artifacts("origin/data/test-mapping", "repo")
        self.assertIsNone(artifacts["full_coverage_summary"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest scripts.tests.test_get_nightly_report_data -v`

Expected: FAIL because `load_branch_artifacts` does not exist.

- [ ] **Step 3: Implement the artifact loader and wire it into `report`**

```python
def load_branch_artifacts(ref, git_root):
    paths = {
        "codebase_coverage": "codebase-coverage.json",
        "full_coverage_summary": "full-coverage-summary.json",
        "dart_failed_tests": "dart-failed-tests.json",
        "cpp_failed_tests": "cpp-failed-tests.json",
        "dart_test_timings": "dart-test-timings.json",
        "dart_test_timings_previous": "dart-test-timings-previous.json",
    }
    return {key: parse_json(git_show(ref, path, git_root)) for key, path in paths.items()}
```

Replace the individual legacy `git_show` calls in `main()` with this loader
and merge its return value into `report`.

- [ ] **Step 4: Run the focused and full Python test suites**

Run: `python -m unittest scripts.tests.test_get_nightly_report_data -v`

Expected: PASS.

Run: `python -m unittest discover -s scripts/tests -v`

Expected: PASS with all existing report and setup tests.

- [ ] **Step 5: Commit the fetcher migration**

```bash
git add scripts/get_nightly_report_data.py scripts/tests/test_get_nightly_report_data.py
git commit -m "feat: read current nightly coverage artifacts"
```

### Task 2: Render coverage states and C++ failures

**Files:**
- Modify: `scripts/new_pr_report_html.py:215-481`
- Modify: `scripts/tests/test_new_pr_report_html.py:1-160`

**Interfaces:**
- Consumes the Task 1 report keys.
- Produces `build_coverage_section(summary: dict | None) -> str` and
  `build_cpp_failures_section(failures: dict | None) -> str`.

- [ ] **Step 1: Write failing coverage and C++ failure rendering tests**

```python
def test_coverage_section_shows_measured_dart_and_incomplete_cpp(self):
    html = rpt.build_coverage_section({
        "complete": False,
        "dart": {"status": "measured", "percent": 64.12,
                 "covered_lines": 8298, "eligible_source_lines": 12942},
        "cpp": {"status": "measured", "measurement_complete": False,
                "percent": 2.02, "covered_lines": 811,
                "eligible_source_lines": 40196},
        "combined": {"status": "incomplete", "percent": None},
    })
    self.assertIn("Dart", html)
    self.assertIn("64.12%", html)
    self.assertIn("C++", html)
    self.assertIn("incomplete", html)
    self.assertNotIn("0%", html)

def test_cpp_failures_show_package_and_reason_without_author(self):
    html = rpt.build_cpp_failures_section({
        "failed_package_count": 1,
        "failures": [{"package_name": "ai_generator",
                      "reason": "test executable is missing"}],
    })
    self.assertIn("ai_generator", html)
    self.assertIn("test executable is missing", html)
    self.assertNotIn("Author", html)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest scripts.tests.test_new_pr_report_html.CoverageSectionTests scripts.tests.test_new_pr_report_html.CppFailureSectionTests -v`

Expected: FAIL because both renderer functions do not exist.

- [ ] **Step 3: Add small independent renderers and connect them in `main()`**

Implement the functions using HTML-escaped package/reason values. Each coverage
card must show a numeric percentage only when its metric has one; otherwise
show the exact status. Append `build_coverage_section(data.get("full_coverage_summary"))`
and `build_cpp_failures_section(data.get("cpp_failed_tests"))` as standalone
report sections. Replace timing inputs with `dart_test_timings` and
`dart_test_timings_previous`; replace the existing Dart failure input with
`dart_failed_tests`.

- [ ] **Step 4: Run the renderer and regression suites**

Run: `python -m unittest scripts.tests.test_new_pr_report_html -v`

Expected: PASS.

Run: `python -m unittest discover -s scripts/tests -v`

Expected: PASS.

- [ ] **Step 5: Commit the report rendering changes**

```bash
git add scripts/new_pr_report_html.py scripts/tests/test_new_pr_report_html.py
git commit -m "feat: report native coverage and failures"
```

### Task 3: Remove obsolete data artifacts and produce the PDF

**Files:**
- Data branch only: `data/test-mapping` obsolete root artifacts and
  `mapping-fragment-*.json`
- Generated, gitignored: `nightly-report-data.json`, `nightly-report.html`,
  `nightly-report.pdf`

**Interfaces:**
- Consumes the Task 1/2 script behavior and the current remote data branch.
- Produces a committed/pushed cleanup of only the global-constraint paths and
  a local PDF for the 2026-07-27 report date.

- [ ] **Step 1: Verify the exact data-branch deletion set before modifying it**

Run:

```powershell
git fetch origin data/test-mapping
git ls-tree -r --name-only origin/data/test-mapping -- `
  'mapping-fragment-*.json' `
  'rebuild-failed-tests.json' `
  'cpp-coverage-failures.json' `
  'test-timings.json' `
  'test-timings-previous.json'
```

Expected: only the nine current mapping fragments and four named legacy root
artifacts are listed; no `pr-runs/` path is listed.

- [ ] **Step 2: Create an isolated data-branch worktree and remove only the verified files**

Run a detached worktree under `C:\tmp`, switch it to a local
`data/test-mapping` branch based on `origin/data/test-mapping`, remove the
verified paths with `git rm`, inspect `git diff --cached --name-status`, then
commit `chore: remove obsolete nightly report artifacts [skip ci]` and push
`HEAD:data/test-mapping`.

- [ ] **Step 3: Verify the pushed branch contains no obsolete artifacts**

Run:

```powershell
git fetch origin data/test-mapping
git ls-tree -r --name-only origin/data/test-mapping | `
  Select-String -Pattern '(^mapping-fragment-|^rebuild-failed-tests\.json$|^cpp-coverage-failures\.json$|^test-timings(-previous)?\.json$)'
```

Expected: no output.

- [ ] **Step 4: Fetch report data and generate HTML without mail actions**

Run:

```powershell
python scripts/get_nightly_report_data.py --date 2026-07-27 --out nightly-report-data.json
python scripts/new_pr_report_html.py --data nightly-report-data.json --out nightly-report.html
```

Expected: the JSON includes the new language-specific keys and the HTML
includes C++ coverage plus C++ failure package/reason rows.

- [ ] **Step 5: Have a sub agent convert and inspect the PDF**

The sub agent runs WeasyPrint against `nightly-report.html`, falls back to
headless Chromium only if WeasyPrint cannot import, verifies that
`nightly-report.pdf` is non-empty, and reports the path and byte size. It must
not open Outlook, read recipients, send email, or create `run-status.json`.

- [ ] **Step 6: Run final evidence checks and commit any remaining tracked changes**

Run: `python -m unittest discover -s scripts/tests -v`

Expected: PASS.

Run: `git status --short`

Expected: no tracked script/test changes left uncommitted; generated report
files remain untracked or ignored.

### Task 4: Place coverage before PRs and simplify the header

**Files:**
- Modify: `scripts/new_pr_report_html.py:400-650`
- Modify: `scripts/tests/test_new_pr_report_html.py:1-200`

**Interfaces:**
- Keeps `build_coverage_section(summary: dict | None) -> str` unchanged.
- Changes the final document ordering so the coverage section precedes the PR
  table and removes the legacy `codebase_coverage` percentage/line-count text
  from the report header.

- [ ] **Step 1: Write the failing placement and header tests**

```python
def test_full_report_places_coverage_before_pr_table_and_omits_header_coverage(self):
    html = render_report_with_full_coverage()
    self.assertLess(html.index("Coverage Summary"), html.index("Pull Requests"))
    self.assertNotIn("Coverage <strong", html)
    self.assertNotIn("40318/290815 lines", html)
```

The fixture must include one PR plus `full_coverage_summary` containing Dart,
C++, and Combined metrics so the assertions verify the actual final document,
not a renderer helper in isolation.

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python -m unittest scripts.tests.test_new_pr_report_html.ReportLayoutTests -v`

Expected: FAIL because the current full HTML places coverage after the PR table
and retains the legacy header coverage text.

- [ ] **Step 3: Make the minimal document-layout change**

Remove the `codebase_coverage`-based header coverage fragment and place the
existing `{coverage_section}` immediately after the report header and before
the PR table. Do not change coverage values, C++ failure rows, author notes,
or timing behavior.

- [ ] **Step 4: Run focused and full report tests**

Run: `python -m unittest scripts.tests.test_new_pr_report_html -v`

Expected: PASS.

Run: `python -m unittest discover -s scripts/tests -v`

Expected: PASS.

- [ ] **Step 5: Commit and regenerate the local no-email PDF**

```bash
git add scripts/new_pr_report_html.py scripts/tests/test_new_pr_report_html.py
git commit -m "fix: place coverage before PR table"
python scripts/get_nightly_report_data.py --date 2026-07-27 --out nightly-report-data.json
python scripts/new_pr_report_html.py --data nightly-report-data.json --out nightly-report.html
```

Then have a sub agent regenerate `nightly-report.pdf` from the new HTML using
the verified Edge fallback if WeasyPrint remains unavailable. It must verify a
new non-empty file and must not invoke any mail or status-writing action.
