# Nightly report data-branch artifact migration

## Goal

Make Nightly-PR-Report consume the current nightly-rebuild artifact contract,
remove files that the rebuild must no longer retain, and generate the report
without sending email.

## Data-branch contract

Retain these current inputs:

- `test_mapping.json` and `unsafe-merge-folders.json`.
- `pr-runs/<date>/<sha>/summary.json` and optional `review.md`, subject to the
  existing retention policy.
- `codebase-coverage.json` for the Dart rebuild aggregate.
- `dart-total-coverage.json`, `cpp-total-coverage.json`, and
  `full-coverage-summary.json` for coverage metrics and completion status.
- `dart-failed-tests.json` and `cpp-failed-tests.json` for language-specific
  failure diagnostics.
- `dart-test-timings.json` and `dart-test-timings-previous.json` for the
  Nightly Rebuild Timing section.

Remove these stale items from `data/test-mapping`:

- All `mapping-fragment-*.json`; a completed nightly rebuild is authoritative
  and must remove unmerged PR fragments.
- `rebuild-failed-tests.json` and `cpp-coverage-failures.json`, which were
  replaced by the Dart and C++ failure artifacts.
- `test-timings.json` and `test-timings-previous.json`, which were replaced by
  the Dart-prefixed timing artifacts.

## Report data flow

`get_nightly_report_data.py` will read the retained artifacts directly from
the data branch and place them in the combined report JSON under explicit
language-specific names. It will continue to tolerate an absent optional
artifact by serializing `null` so a report is still possible during rollout.

`new_pr_report_html.py` will:

- render Dart, C++, and combined coverage from `full-coverage-summary.json`;
- distinguish `measured`, `incomplete`, and `not_applicable` states rather
  than treating a missing or incomplete metric as zero;
- retain the existing Dart rebuild-failure table using
  `dart-failed-tests.json`;
- add a C++ rebuild-failure table from `cpp-failed-tests.json`, showing package
  and reason only (no author lookup); and
- use `dart-test-timings*.json` for timing comparisons.

If a coverage or failure artifact is missing or malformed, only its affected
section is omitted or marked unavailable; HTML/PDF generation continues.

## Verification and execution

Tests will first cover the new fetch payload names and the C++ HTML section,
including incomplete C++ coverage and author-free failure rows. After the
tests pass, the current data branch will be fetched for `2026-07-27`, the HTML
will be produced, and a sub agent will convert it to PDF without invoking any
email or status-writing step.
