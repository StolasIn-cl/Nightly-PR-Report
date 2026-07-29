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
recipients, report data, or any output artifact. The local skill will invoke
this refresh as its first step, then re-read the refreshed local skill before
performing any report work.

The script will:

1. Require `SKILL.md` and `recipients.json` to exist.
2. Replace the four existing local-path tokens.
3. Fail if a `{{...}}` token remains after rendering.
4. Write `SKILL.local.md` only after all preflight checks pass.
5. Print the source template hash and the rendered local-skill hash for
   diagnostics.

The current `SKILL.local.md` will be refreshed manually once during rollout so
it gains this preflight step. After that, every 08:00 Cowork run refreshes its
own local skill and re-reads it before following the report workflow. No new
Windows scheduled task is required.

## Boundaries

- The Cowork task remains responsible for invoking the subagent and running
  `validate_author_notes.py`; the refreshed local skill contains those required
  gates.
- The refresh step is self-referential by design: the currently loaded local
  skill performs the render, then discards its stale instructions and follows
  the freshly generated file from the beginning.
- Refresh failure leaves the previous `SKILL.local.md` unchanged and exits
  non-zero. It does not send email, render a PDF, or write `run-status.json`.
- This design does not auto-pull repository commits. Repository updates must be
  present locally before the daily refresh renders them.

## Testing

Unit tests will prove successful rendering, unresolved-token rejection, and
non-destructive behavior when recipients are absent. Existing setup tests will
continue to cover the one-time setup path. A source-content test will verify
that the template requires refresh-and-re-read before report data is touched.
