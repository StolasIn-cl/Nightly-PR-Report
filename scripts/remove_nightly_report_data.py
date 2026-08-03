#!/usr/bin/env python3
"""
remove_nightly_report_data.py
Remove old pr-runs/ date sub-directories from the data/test-mapping branch.
Keeps the most recent N days of data (default: 7 = the last week) so that
the past week's PR data remains visible until the next cleanup.
Uses worktree + retry + rebase-push pattern.

Usage:
    python3 remove_nightly_report_data.py [--date YYYY-MM-DD] [--keep-days N] [--data-branch BRANCH]

Examples:
    python3 remove_nightly_report_data.py              # keep last 7 days
    python3 remove_nightly_report_data.py --keep-days 1  # keep only today
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time


def git(args, cwd, capture=True):
    return subprocess.run(
        ["git"] + args,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date",        default="", help="YYYY-MM-DD (for commit msg only)")
    parser.add_argument("--keep-days",   type=int, default=7,
                        help="Keep the most recent N days of data (default: 7)")
    parser.add_argument("--data-branch", default="data/test-mapping")
    args = parser.parse_args()

    date        = args.date or datetime.date.today().strftime("%Y-%m-%d")
    keep_since  = datetime.date.today() - datetime.timedelta(days=args.keep_days - 1)
    data_branch = args.data_branch

    r = git(["rev-parse", "--show-toplevel"], cwd=os.getcwd())
    if r.returncode != 0:
        print("Not inside a git repository.", file=sys.stderr)
        sys.exit(1)
    git_root = r.stdout.strip()

    # Commit author identity is set once by setup_nightly_report.py (local git
    # config on this repo) — not overridden here so it stays whatever the
    # person who ran setup configured, instead of a shared bot identity.

    max_retries    = 3
    push_succeeded = False

    for attempt in range(max_retries):
        worktree_path = tempfile.mkdtemp(prefix="data-cleanup-worktree-")
        try:
            git(["worktree", "prune"], cwd=git_root)
            git(["fetch", "origin", data_branch], cwd=git_root)

            r = git(["worktree", "add", "--detach", worktree_path,
                     f"origin/{data_branch}"], cwd=git_root)
            if r.returncode != 0:
                print(f"[attempt {attempt+1}] worktree add failed: {r.stderr.strip()}",
                      file=sys.stderr)
                continue

            git(["checkout", "-B", data_branch], cwd=worktree_path)

            # Rebuild the index from HEAD in case git checkout left it corrupt
            # (seen as "bad signature 0x00000000 / index file corrupt" errors).
            index_file = os.path.join(worktree_path, ".git", "index")
            if os.path.exists(index_file):
                os.remove(index_file)
            git(["read-tree", "HEAD"], cwd=worktree_path)

            pr_runs_path = os.path.join(worktree_path, "pr-runs")
            if not os.path.isdir(pr_runs_path):
                print(f"Nothing to remove: pr-runs/ not present on {data_branch}.")
                push_succeeded = True
                break

            # Only remove date sub-directories older than keep_since.
            # Keep the most recent keep_days days so yesterday's data stays visible.
            date_pat = re.compile(r'^\d{4}-\d{2}-\d{2}$')
            to_remove = []
            for name in sorted(os.listdir(pr_runs_path)):
                if not date_pat.match(name):
                    continue
                try:
                    d = datetime.date.fromisoformat(name)
                except ValueError:
                    continue
                if d < keep_since:
                    to_remove.append(f"pr-runs/{name}")

            if not to_remove:
                print(f"No date dirs older than {args.keep_days} day(s); nothing to do.")
                push_succeeded = True
                break

            print(f"Removing {len(to_remove)} dir(s): {', '.join(to_remove)}")
            for path in to_remove:
                git(["rm", "-r", "--quiet", "--ignore-unmatch", path], cwd=worktree_path)

            r = git(["diff", "--staged", "--name-only"], cwd=worktree_path)
            if not r.stdout.strip():
                print("No staged changes after rm; nothing to commit.")
                push_succeeded = True
                break

            git(["commit", "-m",
                 f"chore: remove pr-runs (reported {date}) [skip ci]"],
                cwd=worktree_path)

            r = git(["push", "origin", f"HEAD:refs/heads/{data_branch}"],
                    cwd=worktree_path)
            if r.returncode == 0:
                push_succeeded = True
            else:
                # Rebase and retry
                git(["fetch", "origin", data_branch],           cwd=worktree_path)
                r2 = git(["rebase", "--autostash",
                           f"origin/{data_branch}"],            cwd=worktree_path)
                if r2.returncode != 0:
                    git(["rebase", "--abort"],                   cwd=worktree_path)

        finally:
            git(["worktree", "remove", worktree_path, "--force"], cwd=git_root)
            shutil.rmtree(worktree_path, ignore_errors=True)

        if push_succeeded:
            break
        time.sleep(2 ** attempt)

    if not push_succeeded:
        print(f"[WARN] Failed to remove pr-runs after {max_retries} attempts.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Removed stale pr-runs/ dirs from {data_branch} (keeping last {args.keep_days} day(s), reported date: {date}).")


if __name__ == "__main__":
    main()
