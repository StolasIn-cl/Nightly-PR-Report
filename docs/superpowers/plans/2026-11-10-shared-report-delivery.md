# Shared Report Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extract Chrome Outlook delivery, retain project-owned email content, and schedule WER 08:00 / PR 09:00 with Sol 6.1 delivery diagnosis.

**Architecture:** Python stdlib SQLite ledger and immutable attachment spool; Chrome extension operations remain in one shared skill. Producers publish manifests and consume receipts. Existing schedules orchestrate both stages.

**Tech Stack:** Python, SQLite, Node/Playwright for local PDF, Codex CUA Chrome extension, Codex automations.

**Spec:** ../specs/2026-11-10-shared-report-delivery-design.md with user amendments: PR 09:00; WER 08:00; gpt-6.1-sol escalation for delivery failures only.

## Global Constraints

- Existing Chrome Outlook account; no Graph, SMTP, cookie extraction, or alternate mail backend.
- Report projects own subject, body, recipients, attachments. Report failures stop.
- Never retry an uncertain send. Never add a test email to the production list.
- Preserve unrelated working changes and legacy sent dates.

## Review Focus

- Atomic claim across processes and stale UI ownership: concurrent claims must fail; dead owners require explicit recovery.
- Generation changed on same date: never turn a changed payload into a resend.
- Attachment changes after submit: verify immutable spool immediately before Send.
- Crash after Send intent: persist uncertainty before clicking and require Sent Items evidence to resolve.
- Escalation: Sol diagnoses delivery only, one bounded recovery round, no repeated send or policy bypass.

### Task 1: Shared ledger and CLI

Files: Report-Delivery/delivery.py, Report-Delivery/tests/test_delivery.py, Report-Delivery/README.md.
Interfaces: Store.submit(manifest), claim(owner), transition(id, token, phase, evidence), recover(id), import_legacy(...); CLI exposes same operations and JSON.

- [x] Write failing tests for manifest validation, immutable snapshots, duplicate/date conflicts, claims, mailbox serialization, Send-intent uncertainty, recovery and legacy imports.
- [x] Run unittest discovery; expected import failure before implementation.
- [x] Implement transaction-protected SQLite state and token ownership, attachment verification and receipts.
- [x] Run tests, including two-process claim test; expected PASS.

### Task 2: Producers

Files: Nightly scripts/prepare_delivery.py, scripts/render_report.cjs, SKILL.md, README.md; WER daily_run.py, RUNBOOK.md, README.md; tests for adapters.
Interfaces: producers return manifest path; receipt sync updates legacy status after shared sent only.

- [x] Write failing tests for stale date, preserved project copy, zero-PR behavior, WER manifest and shared receipt compatibility.
- [x] Run new tests; expected missing adapter/contract failures.
- [x] Implement dated PDF output + manifest publishing and receipt synchronization. Remove project-owned Outlook procedures; regenerate local skill.
- [x] Run relevant existing and new suites; expected PASS. Render current local HTML to temporary dated output, without sending.

### Task 3: Skill, migration and schedules

Files: Report-Delivery/skill/SKILL.md, global report-delivery/SKILL.md, backup config, live automations via tool.
Interfaces: shared delivery CLI plus CUA; escalation uses collaboration.spawn_agent(gpt-6.1-sol, fork_turns=none) for delivery failures.

- [x] Write single maintained Chrome procedure, claim/recovery commands and explicit Sol ownership handoff protocol.
- [x] Import legacy sent/uncertain records; validate no send on re-submission.
- [x] Validate skill and Chrome sender account; perform user-authorized live tests only to Stolas_In@cyberlink.com with both PDFs.
- [x] Update existing automations through automation tool, preserve cron/heartbeat kinds, WER 08:00 and PR 09:00.
- [x] Review complete change, fix actionable findings, rerun affected checks and report evidence/limits.

## Execution ledger

Ruling: Work in the fixed local project paths on codex/shared-report-delivery and back up touched live files. These are installed local scheduled workflows and WER has no repository; another checkout would not exercise or update the authorized live paths. User approved implementation; no additional workflow confirmation is required.

Ruling: No automatic Chrome restart. Sol receives diagnostics and may use the same documented route; unresolved login, policy denial, unavailable delegated model, or unknown send remains an explicit non-success result.

Verification: shared ledger 16 tests; Nightly 60 tests; WER 23 tests passed. Both PDF renderers exercised on current local HTML. Skill quick_validate passed. Independent code review findings on recovery serialization, Send-intent time matching and delayed receipt synchronization were fixed with regressions; follow-up review found no remaining important issue.

Automation verification: updated existing nightly-pr-report-2 via app tool to Tuesday–Saturday 09:00, retaining gpt-6-luna/xhigh/local/project target; wer-crash remains daily 08:00 heartbeat on its original chat. Both ACTIVE. Both prompts reference the shared skill, Sol 6.1 delivery-only diagnosis and self-only tests.
