#!/usr/bin/env python3
"""
setup_nightly_report.py
One-time setup: initialise Nightly-PR-Report as a git repo that tracks the
data/test-mapping branch of the promeo repository.

Usage:
    python scripts\\setup_nightly_report.py --token <GITHUB_PAT>
    python scripts\\setup_nightly_report.py

Options:
    --token         GitHub Personal Access Token. Embeds it in the remote URL
                    so git fetch works without any interactive prompt.
    --remote-url    Override the GitHub remote URL
                    (default: CyberLink-Team/promeo-pc-promeo).
    --branch        Data branch to track (default: data/test-mapping).
    --git-name      Git commit author name for this repo (prompted if omitted).
    --git-email     Git commit author email for this repo (prompted if omitted).
    --report-email  Semicolon-separated recipients for the nightly report,
                    stored locally in recipients.json (defaults to --git-email if omitted).

Note: commit authorship and the actual GitHub identity used to push/fetch are
separate. This script only sets the local git identity (user.name/user.email).
Whoever's credentials authenticate the fetch/push (Windows Credential Manager,
or an embedded --token / SSH key) determines the real GitHub account used, so
set that up separately so it is not a machine-wide shared login.
"""

import argparse
import json
import os
import subprocess
import sys
from urllib.parse import urlparse, urlunparse


def git(args, cwd, capture=True, check=False, encoding="utf-8"):
    result = subprocess.run(
        ["git"] + args,
        capture_output=capture,
        text=True,
        encoding=encoding,
        errors="replace",
        cwd=cwd,
    )
    if check and result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    return result


def embed_token(url, token):
    """Return url with token embedded: https://TOKEN@github.com/..."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(netloc=f"{token}@{parsed.netloc}"))


def prompt_default(label, default):
    """Prompt interactively with a shown default; skip prompting if stdin is not a tty."""
    if not sys.stdin.isatty():
        return default
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def render_local_skill(template_path, output_path, replacements):
    with open(template_path, encoding="utf-8") as file:
        content = file.read()

    rendered = content
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    unresolved = sorted({token for token in (
        part.split("}}", 1)[0] + "}}"
        for part in rendered.split("{{")[1:]
        if "}}" in part
    )})
    if unresolved:
        print(
            "[WARN] Unresolved placeholders remain in local skill file: "
            + ", ".join(unresolved),
            file=sys.stderr,
        )

    if os.path.isfile(output_path):
        with open(output_path, encoding="utf-8") as file:
            previous = file.read()
    else:
        previous = None

    if previous == rendered:
        print(f"[OK] Local skill file already up to date: {output_path}")
        return

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(rendered)
    print(f"[OK] Wrote local skill file: {output_path}")


def write_recipients_file(output_path, recipients_text):
    """Write a local, gitignored JSON recipient list from semicolon-separated input."""
    recipients = [item.strip() for item in recipients_text.split(";") if item.strip()]
    if not recipients:
        print("[ERROR] At least one report recipient is required.", file=sys.stderr)
        sys.exit(1)

    content = json.dumps({"recipients": recipients}, indent=2, ensure_ascii=False) + "\n"
    previous = None
    if os.path.isfile(output_path):
        with open(output_path, encoding="utf-8") as file:
            previous = file.read()
    if previous == content:
        print(f"[OK] Recipient list already up to date: {output_path}")
        return

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(content)
    print(f"[OK] Wrote local recipient list: {output_path}")
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--token",
        default="",
        help="GitHub PAT; embeds token in the remote URL",
    )
    parser.add_argument(
        "--remote-url",
        default="https://github.com/CyberLink-Team/promeo-pc-promeo.git",
    )
    parser.add_argument("--branch", default="data/test-mapping")
    parser.add_argument(
        "--git-name",
        default="",
        help="Git commit author name for this repo (prompted if omitted)",
    )
    parser.add_argument(
        "--git-email",
        default="",
        help="Git commit author email for this repo (prompted if omitted)",
    )
    parser.add_argument(
        "--report-email",
        default="",
        help="Semicolon-separated recipients for the nightly report, stored in recipients.json "
        "(defaults to --git-email if omitted)",
    )
    args = parser.parse_args()

    remote_url = embed_token(args.remote_url, args.token) if args.token else args.remote_url
    display_url = args.remote_url
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"Target directory : {repo_dir}")
    print(f"Remote           : {display_url}")
    print(f"Branch           : {args.branch}")
    if args.token:
        print(f"Token            : ***{args.token[-4:]} (last 4 chars)")
    print()

    git_dir = os.path.join(repo_dir, ".git")
    if os.path.isdir(git_dir):
        print("[OK] .git already exists; skipping init")
    else:
        print("  Initialising git repo...")
        git(["init"], cwd=repo_dir, check=True)
        print("[OK] git init done")

    remote_result = git(["remote", "get-url", "origin"], cwd=repo_dir)
    if remote_result.returncode == 0:
        print(f"  Updating remote origin -> {display_url}" + (" (with token)" if args.token else ""))
        git(["remote", "set-url", "origin", remote_url], cwd=repo_dir, check=True)
    else:
        print(f"  Adding remote origin: {display_url}" + (" (with token)" if args.token else ""))
        git(["remote", "add", "origin", remote_url], cwd=repo_dir, check=True)
    print("[OK] remote set")

    print(f"  Fetching origin/{args.branch}...")
    fetch_result = git(["fetch", "origin", args.branch], cwd=repo_dir, capture=False)
    if fetch_result.returncode != 0:
        print(
            "\n[FAIL] git fetch failed.\n"
            "If you have not provided a token, run:\n"
            "  python scripts\\setup_nightly_report.py --token <YOUR_PAT>\n"
            "Required GitHub PAT scopes: Contents (read) for fetch; Contents (write) for cleanup push.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("[OK] fetch done")

    verify_result = git(["rev-parse", "--verify", f"origin/{args.branch}"], cwd=repo_dir)
    if verify_result.returncode != 0:
        print(f"[ERROR] origin/{args.branch} not found after fetch.", file=sys.stderr)
        sys.exit(1)
    print(f"[OK] origin/{args.branch} verified")

    global_name = git(["config", "--global", "user.name"], cwd=repo_dir).stdout.strip()
    global_email = git(["config", "--global", "user.email"], cwd=repo_dir).stdout.strip()

    git_name = args.git_name or prompt_default("Git commit author name for this repo", global_name)
    git_email = args.git_email or prompt_default("Git commit author email for this repo", global_email)
    if not git_name or not git_email:
        print(
            "[ERROR] --git-name / --git-email required "
            "(no global git identity to fall back to).",
            file=sys.stderr,
        )
        sys.exit(1)

    git(["config", "user.name", git_name], cwd=repo_dir, check=True)
    git(["config", "user.email", git_email], cwd=repo_dir, check=True)
    print(f"[OK] local git identity set: {git_name} <{git_email}>")

    report_email = args.report_email or prompt_default(
        "Report recipient email(s), separated by semicolons",
        git_email,
    )
    skill_template_path = os.path.join(repo_dir, "SKILL.md")
    local_skill_path = os.path.join(repo_dir, "SKILL.local.md")
    recipients_path = os.path.join(repo_dir, "recipients.json")
    if report_email and os.path.isfile(skill_template_path):
        write_recipients_file(recipients_path, report_email)
        render_local_skill(
            skill_template_path,
            local_skill_path,
            {
                "{{RECIPIENTS_PATH_WINDOWS}}": recipients_path,
                "{{NR_DIR_WINDOWS}}": repo_dir,
                "{{SCRIPT_SOURCE_WINDOWS}}": os.path.join(
                    repo_dir, "scripts", "new_pr_report_html.py"
                ),
                "{{PDF_PATH_WINDOWS}}": os.path.join(repo_dir, "nightly-report.pdf"),
            },
        )

    print()
    print("=" * 58)
    print("Setup complete!")
    print()
    print("Next steps:")
    print("  1. Register Windows scheduled tasks (if not done yet):")
    print("       powershell -ExecutionPolicy Bypass -File scripts\\register_tasks.ps1")
    print("  2. Connect this folder in Cowork (Settings -> Folders)")
    print("  3. Use SKILL.local.md when configuring the Cowork scheduled task")
    print("  4. Make sure fetch/push authenticates as YOUR OWN GitHub account,")
    print("     not a machine-wide shared credential (embedded --token, or a")
    print("     dedicated SSH key/host alias) - see README for details.")
    print("=" * 58)


if __name__ == "__main__":
    main()
