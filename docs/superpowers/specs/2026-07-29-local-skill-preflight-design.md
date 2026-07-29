# Local Skill Preflight Design

## Goal

Ensure every scheduled 08:00 Nightly PR Report run uses the current
review-led Author Notes workflow, including P1/P2 labels, validation before
PDF creation, and the existing no-send-on-validation-failure rule.

## Problem

Cowork reads the gitignored `SKILL.local.md`, while workflow updates are
committed to `SKILL.md`. The existing one-time setup writes the local file but
does not refresh it later, so a scheduled run can use stale instructions even
when the repository contains the required validation rules.

## Design

Add a small, token-free refresh script that renders `SKILL.md` to
`SKILL.local.md` using the current repository path and the existing local
`recipients.json` path. It does not change git configuration, credentials,
recipients, report data, or any output artifact.

The script will:

1. Require `SKILL.md` and `recipients.json` to exist.
2. Replace the four existing local-path tokens.
3. Fail if a `{{...}}` token remains after rendering.
4. Write `SKILL.local.md` only after all preflight checks pass.
5. Print the source template hash and the rendered local-skill hash for
   diagnostics.

`register_tasks.ps1` will add a `NightlyPR-RefreshLocalSkill` Windows task at
07:55. This is five minutes before the documented 08:00 Cowork task and after
the 07:00 data fetch. Re-registering tasks updates this task idempotently.

## Boundaries

- The Cowork task remains responsible for invoking the subagent and running
  `validate_author_notes.py`; the refreshed local skill contains those required
  gates.
- Refresh failure leaves the previous `SKILL.local.md` unchanged and exits
  non-zero. It does not send email, render a PDF, or write `run-status.json`.
- This design does not auto-pull repository commits. Repository updates must be
  present locally before the daily refresh renders them.

## Testing

Unit tests will prove successful rendering, unresolved-token rejection, and
non-destructive behavior when recipients are absent. Existing setup tests will
continue to cover the one-time setup path. A PowerShell content assertion will
verify that task registration creates the 07:55 refresh task and preserves the
existing fetch and cleanup tasks.
