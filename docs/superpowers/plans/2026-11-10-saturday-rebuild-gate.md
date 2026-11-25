# Saturday rebuild gate implementation plan

**Goal:** Keep Tuesday–Friday fetch/report at 07:30/09:00; move Saturday to 19:30/20:00 and stop unless Friday's full rebuild is published.

**Architecture:** Share one Friday-date validator between fetch and report preflight. Fetch pins one data-branch commit and includes rebuild status in the snapshot. Configure separate weekday/Saturday triggers, preserving cleanup and delivery settings.

**Tech stack:** Python unittest, PowerShell ScheduledTasks, Codex automation tools.

**Spec:** User instruction in this chat, 2026-11-10. No automatic retries, no test emails, no cleanup changes.

## Tasks

- [x] Write and run failing tests for missing/stale/daily/unpublished status, valid full publication with test failures, weekday compatibility, and pinned snapshot reads.
- [x] Implement `validate_rebuild_status(status, day)` and call it before fetch output replacement and from preflight. Include source commit and status in fetched JSON.
- [x] Add Saturday fetch trigger at 19:30 and a fetch-only registration option that preserves existing task settings and cleanup.
- [x] Update README and producer instructions, refresh local instructions, run the full unittest suite.
- [x] Update existing Codex automation to Tue–Fri 09:00; create Saturday 20:00 with the same model/delivery configuration and explicit rebuild gate.
- [x] Read back installed Windows and Codex schedules; review diff and verify no mail was sent.

## Review focus

Missing or malformed status must stop Friday reports, including zero PRs. A different date or daily mode must stop. Test failures and incomplete coverage must remain reportable. Fetch failure must preserve existing output. All source files must use one immutable commit. Weekday preflight and cleanup behavior must remain unchanged.

Verification: 69 unittest tests passed, independent code review found no findings. Installed Windows triggers and both ACTIVE Codex automations were read back; fetch actions/settings/principal and complete cleanup XML match backups. Windows update required UAC elevation and succeeded. No emails sent.
