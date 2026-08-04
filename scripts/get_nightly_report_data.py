#!/usr/bin/env python3
"""
get_nightly_report_data.py
Gather all PR-run data for a given day from the data/test-mapping branch into one JSON file.
Read-only: fetches the data branch and reads files via `git show` (no checkout).

Usage:
    python3 get_nightly_report_data.py [--date YYYY-MM-DD] [--data-branch BRANCH] [--out FILE]
"""

import argparse
import datetime
import json
import os
import subprocess
import sys


def git(args, cwd, capture=True):
    return subprocess.run(
        ["git"] + args,
        capture_output=capture,
        text=True,
        encoding="utf-8",   # force UTF-8; prevents cp950 decode errors on Windows
        errors="replace",   # replace unmappable bytes instead of crashing
        cwd=cwd,
    )


def git_show(ref, path, cwd):
    r = git(["show", f"{ref}:{path}"], cwd=cwd)
    if r.returncode == 0 and r.stdout is not None:
        return r.stdout.lstrip("﻿")   # strip UTF-8 BOM (PowerShell artefact)
    return None


def parse_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def load_branch_artifacts(ref, git_root):
    paths = {
        "codebase_coverage": "codebase-coverage.json",
        "full_coverage_summary": "full-coverage-summary.json",
        "dart_failed_tests": "dart-failed-tests.json",
        "cpp_failed_tests": "cpp-failed-tests.json",
        "dart_test_timings": "dart-test-timings.json",
        "dart_test_timings_previous": "dart-test-timings-previous.json",
        "dart_coverage_delta": "dart-coverage-delta.json",
    }
    return {key: parse_json(git_show(ref, path, git_root)) for key, path in paths.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",        default="",  help="YYYY-MM-DD (default: today)")
    parser.add_argument("--data-branch", default="data/test-mapping")
    parser.add_argument("--out",         default="",  help="Output JSON path")
    args = parser.parse_args()

    date        = args.date or datetime.date.today().strftime("%Y-%m-%d")
    data_branch = args.data_branch
    ref         = f"origin/{data_branch}"

    r = git(["rev-parse", "--show-toplevel"], cwd=os.getcwd())
    if r.returncode != 0:
        print("Not inside a git repository.", file=sys.stderr)
        sys.exit(1)
    git_root = r.stdout.strip()

    out_file = args.out or os.path.join(git_root, "nightly-report-data.json")
    prefix   = f"pr-runs/{date}/"

    # Fetch latest data branch (ignore errors — may already be up-to-date or offline)
    git(["fetch", "origin", data_branch], cwd=git_root)

    # List all files under pr-runs/<date>/
    r = git(["ls-tree", "-r", "--name-only", ref], cwd=git_root)
    all_files = [f for f in r.stdout.splitlines() if f.startswith(prefix)]
    shas = sorted({f[len(prefix):].split("/")[0] for f in all_files})

    prs = []
    for sha in shas:
        base    = f"{prefix}{sha}"
        summary = parse_json(git_show(ref, f"{base}/summary.json", git_root))
        review  = git_show(ref, f"{base}/review.md", git_root)

        # Best-effort head commit message (only if commit is reachable locally)
        commit_msg = None
        r2 = git(["log", "-1", "--format=%s%n%n%b", sha], cwd=git_root)
        if r2.returncode == 0 and r2.stdout.strip():
            commit_msg = r2.stdout.strip()

        prs.append({
            "head_sha":            sha,
            "summary":             summary,
            "review_markdown":     review,
            "head_commit_message": commit_msg,
        })

    # Sort PRs chronologically by CI run completion time (earliest first).
    # The default order is alphabetical by SHA, which is not meaningful.
    prs.sort(key=lambda p: (p.get("summary") or {}).get("generated_at") or "")

    artifacts = load_branch_artifacts(ref, git_root)

    report = {
        "date":                   date,
        "generated_at":           datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_branch":            data_branch,
        "pr_count":               len(prs),
        "prs":                    prs,
        **artifacts,
    }

    out_dir = os.path.dirname(out_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Collected {len(prs)} PR run(s) -> {out_file}")


if __name__ == "__main__":
    main()
