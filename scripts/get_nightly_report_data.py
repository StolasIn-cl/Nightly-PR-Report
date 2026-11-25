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


def validate_rebuild_status(status, day):
    """Friday reports require that Friday's full rebuild has published results.

    This is publication readiness, not test success or coverage completeness.
    Key the check to the report date so delayed/manual runs retain the same gate.
    """
    target = datetime.date.fromisoformat(day)
    if target.weekday() != 4:
        return
    error = f"Friday full rebuild for {day} is not confirmed published"
    if not isinstance(status, dict):
        raise ValueError(f"{error}: missing or invalid rebuild-status.json")
    run = status.get("run")
    publish = status.get("publish")
    if not isinstance(run, dict) or not isinstance(publish, dict):
        raise ValueError(f"{error}: invalid run/publish metadata")
    if status.get("operation") != "full" or run.get("taipei_date") != day:
        raise ValueError(f"{error}: rebuild date or operation does not match")
    if publish.get("state") != "published":
        raise ValueError(f"{error}: publish.state={publish.get('state')!r}")
    for key in ("workflow_run_id", "workflow_run_attempt"):
        value = str(run.get(key, ""))
        if not value.isascii() or not value.isdigit() or int(value) < 1:
            raise ValueError(f"{error}: missing or invalid {key}")
    try:
        published_at = datetime.datetime.fromisoformat(
            publish["published_at"].replace("Z", "+00:00")
        )
        if published_at.utcoffset() is None:
            raise ValueError("timezone required")
        taipei_date = published_at.astimezone(
            datetime.timezone(datetime.timedelta(hours=8))
        ).date()
        if taipei_date < target:
            raise ValueError("publication predates rebuild date")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError(f"{error}: invalid publish.published_at") from exc


def load_branch_artifacts(ref, git_root):
    paths = {
        "rebuild_status": "rebuild-status.json",
        "codebase_coverage": "codebase-coverage.json",
        "full_coverage_summary": "full-coverage-summary.json",
        "dart_failed_tests": "dart-failed-tests.json",
        "cpp_failed_tests": "cpp-failed-tests.json",
        "unsafe_merge_folders": "unsafe-merge-folders.json",
        "dart_test_timings": "dart-test-timings.json",
        "dart_test_timings_previous": "dart-test-timings-previous.json",
        "dart_coverage_delta": "dart-coverage-delta.json",
        "quality_metrics_history": "quality-metrics-history.json",
    }
    return {key: parse_json(git_show(ref, path, git_root)) for key, path in paths.items()}


def fetch_data_branch(data_branch, git_root):
    """Fetch the report source branch, failing instead of reading a stale ref."""
    result = git(["fetch", "origin", data_branch], cwd=git_root)
    if result.returncode == 0:
        return

    detail = (result.stderr or result.stdout or "").strip()
    suffix = f": {detail}" if detail else ""
    raise RuntimeError(f"Unable to fetch origin/{data_branch}{suffix}")


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

    try:
        fetch_data_branch(data_branch, git_root)
        snapshot = git(["rev-parse", "--verify", "FETCH_HEAD^{commit}"], cwd=git_root)
        if snapshot.returncode != 0 or not snapshot.stdout.strip():
            raise RuntimeError("Unable to resolve fetched data branch commit")
        ref = snapshot.stdout.strip()
        artifacts = load_branch_artifacts(ref, git_root)
        validate_rebuild_status(artifacts.get("rebuild_status"), date)
    except (RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    # List all files under pr-runs/<date>/
    r = git(["ls-tree", "-r", "--name-only", ref], cwd=git_root)
    if r.returncode != 0:
        print("ERROR: Unable to list fetched PR data", file=sys.stderr)
        sys.exit(1)
    all_files = [f for f in r.stdout.splitlines() if f.startswith(prefix)]
    shas = sorted({f[len(prefix):].split("/")[0] for f in all_files})

    prs = []
    for sha in shas:
        base    = f"{prefix}{sha}"
        summary = parse_json(git_show(ref, f"{base}/summary.json", git_root))
        review  = git_show(ref, f"{base}/review.md", git_root)

        if summary is None:
            # No summary.json on the data branch for this commit (e.g. the CI
            # run's summary write failed or hasn't landed yet). Without a PR
            # number, author, or run URL there is nothing attributable to
            # report, so skip it rather than emitting an orphaned entry that
            # can never be matched in the Author Notes section.
            print(
                f"WARNING: skipping {sha} — no summary.json under {base}/ "
                f"on {data_branch} (orphaned review.md with no attributable PR)",
                file=sys.stderr,
            )
            continue

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

    report = {
        "date":                   date,
        "generated_at":           datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_branch":            data_branch,
        "data_commit":            ref,
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
