#!/usr/bin/env python3
"""Render the machine-local Nightly PR Report skill without requiring a token."""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path


class RefreshError(RuntimeError):
    """Raised when the local skill cannot be refreshed safely."""


def _validate_recipients(recipients_path: Path) -> None:
    try:
        recipients = json.loads(recipients_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RefreshError(f"Unable to read recipients file: {recipients_path}") from error

    if not isinstance(recipients, dict) or not isinstance(recipients.get("recipients"), list):
        raise RefreshError(f"Invalid recipients file: {recipients_path}")


def render_local_skill(repo_dir: Path) -> tuple[str, str]:
    """Render SKILL.md into SKILL.local.md and return their SHA-256 hashes."""
    repo_dir = Path(repo_dir).resolve()
    template_path = repo_dir / "SKILL.md"
    recipients_path = repo_dir / "recipients.json"
    output_path = repo_dir / "SKILL.local.md"

    if not template_path.is_file():
        raise RefreshError(f"Missing skill template: {template_path}")
    if not recipients_path.is_file():
        raise RefreshError(f"Missing recipients file: {recipients_path}")

    try:
        source_bytes = template_path.read_bytes()
        source = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RefreshError(f"Unable to read skill template: {template_path}") from error
    _validate_recipients(recipients_path)

    replacements = {
        "{{RECIPIENTS_PATH_WINDOWS}}": str(recipients_path),
        "{{NR_DIR_WINDOWS}}": str(repo_dir),
        "{{SCRIPT_SOURCE_WINDOWS}}": str(repo_dir / "scripts" / "new_pr_report_html.py"),
        "{{PDF_PATH_WINDOWS}}": str(repo_dir / "nightly-report.pdf"),
    }
    rendered = source
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)

    unresolved = sorted(set(re.findall(r"{{[^{}]+}}", rendered)))
    if unresolved:
        raise RefreshError("Unresolved placeholders: " + ", ".join(unresolved))

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=repo_dir, prefix=".SKILL.local.", delete=False
        ) as temporary:
            temporary.write(rendered)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output_path)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise RefreshError(f"Unable to write local skill: {output_path}") from error

    return hashlib.sha256(source_bytes).hexdigest(), hashlib.sha256(output_path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository directory containing SKILL.md and recipients.json",
    )
    args = parser.parse_args()

    try:
        source_hash, local_hash = render_local_skill(args.repo_dir)
    except RefreshError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Source SHA-256: {source_hash}")
    print(f"Local SHA-256: {local_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
