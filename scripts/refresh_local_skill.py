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


def _windows_path(value: str | Path) -> str:
    """Return an explicitly supplied path in Windows separator form."""
    rendered = str(value).replace("/", "\\")
    if not rendered:
        raise RefreshError("Windows repository path must not be empty")
    return rendered


def render_local_skill(
    repo_dir: Path,
    *,
    template_path: Path | None = None,
    windows_repo_dir: str | Path | None = None,
) -> tuple[str, str]:
    """Render a trusted template into the session-local SKILL.local.md.

    ``repo_dir`` is the session path used only for the output and recipients
    validation.  ``windows_repo_dir`` controls all Windows path substitutions.
    """
    repo_dir = Path(repo_dir).resolve()
    template_path = (
        Path(template_path).resolve() if template_path is not None else repo_dir / "SKILL.md"
    )
    recipients_path = repo_dir / "recipients.json"
    output_path = repo_dir / "SKILL.local.md"
    windows_root = _windows_path(windows_repo_dir if windows_repo_dir is not None else repo_dir)

    if not template_path.is_file():
        raise RefreshError(f"Missing skill template: {template_path}")
    if not recipients_path.is_file():
        raise RefreshError(f"Missing recipients file: {recipients_path}")

    try:
        source_bytes = template_path.read_bytes()
        source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise RefreshError(f"Unable to read skill template: {template_path}") from error
    _validate_recipients(recipients_path)

    replacements = {
        b"{{RECIPIENTS_PATH_WINDOWS}}": f"{windows_root}\\recipients.json".encode("utf-8"),
        b"{{NR_DIR_WINDOWS}}": windows_root.encode("utf-8"),
        b"{{SCRIPT_SOURCE_WINDOWS}}": (
            f"{windows_root}\\scripts\\new_pr_report_html.py".encode("utf-8")
        ),
        b"{{PDF_PATH_WINDOWS}}": f"{windows_root}\\nightly-report.pdf".encode("utf-8"),
    }
    rendered_bytes = source_bytes
    for token, value in replacements.items():
        rendered_bytes = rendered_bytes.replace(token, value)

    unresolved = sorted(
        token.decode("utf-8", errors="replace")
        for token in set(re.findall(br"{{[^{}]+}}", rendered_bytes))
    )
    if unresolved:
        raise RefreshError("Unresolved placeholders: " + ", ".join(unresolved))

    source_hash = hashlib.sha256(source_bytes).hexdigest()
    local_hash = hashlib.sha256(rendered_bytes).hexdigest()

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=repo_dir, prefix=".SKILL.local.", delete=False
        ) as temporary:
            temporary.write(rendered_bytes)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output_path)
    except OSError as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise RefreshError(f"Unable to write local skill: {output_path}") from error

    return source_hash, local_hash


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="session repository directory containing recipients.json and SKILL.local.md",
    )
    parser.add_argument(
        "--template-path",
        type=Path,
        help="trusted SKILL.md template path; defaults to --repo-dir/SKILL.md",
    )
    parser.add_argument(
        "--windows-repo-dir",
        help="explicit Windows repository root used for path placeholders",
    )
    args = parser.parse_args()

    try:
        source_hash, local_hash = render_local_skill(
            args.repo_dir,
            template_path=args.template_path,
            windows_repo_dir=args.windows_repo_dir,
        )
    except RefreshError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Source SHA-256: {source_hash}")
    print(f"Local SHA-256: {local_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
