# Self-refreshing Local Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep each Cowork report run aligned with the committed `SKILL.md` by refreshing the local, path-resolved skill before report work begins.

**Architecture:** A standalone Python refresher renders the template using its repository root and local `recipients.json`, atomically replaces `SKILL.local.md` only after validation, and prints source/output hashes. `SKILL.md` invokes it as Step 0 and then directs the agent to reload the refreshed instructions from Step 1 without looping. Tests exercise the refresher directly.

**Tech Stack:** Python 3 standard library (`argparse`, `hashlib`, `pathlib`, `unittest`), Markdown workflow instructions.

## Global Constraints

- Do not change Outlook, email sending, run status, report data, recipients, or Windows scheduled tasks.
- Keep `SKILL.md` as the committed template and `SKILL.local.md` gitignored.
- Do not overwrite an existing local skill if required inputs or token substitution validation fails.
- Preserve pre-existing unstaged Chrome/attachment edits in `SKILL.md`.

---

### Task 1: Token-free local-skill refresher

**Files:**
- Create: `scripts/refresh_local_skill.py`
- Create: `scripts/tests/test_refresh_local_skill.py`

**Interfaces:**
- `render_local_skill(repo_dir: Path) -> tuple[str, str]` returns source and rendered SHA-256 hashes after successfully writing `SKILL.local.md`.
- CLI accepts optional `--repo-dir`; exits non-zero without modifying the old local skill if `SKILL.md` or `recipients.json` is absent or a `{{...}}` token remains.

- [ ] **Step 1: Write failing tests**

```python
def test_refresh_renders_all_tokens_and_writes_hashes(self):
    source_hash, local_hash = refresher.render_local_skill(self.repo)
    self.assertEqual(len(source_hash), 64)
    self.assertNotIn("{{NR_DIR_WINDOWS}}", self.local_text())

def test_missing_recipients_preserves_existing_local_skill(self):
    previous = self.local_text()
    (self.repo / "recipients.json").unlink()
    with self.assertRaises(refresher.RefreshError):
        refresher.render_local_skill(self.repo)
    self.assertEqual(self.local_text(), previous)

def test_unresolved_token_preserves_existing_local_skill(self):
    self.template.write_text("{{UNKNOWN_TOKEN}}", encoding="utf-8")
    with self.assertRaises(refresher.RefreshError):
        refresher.render_local_skill(self.repo)
```

- [ ] **Step 2: Verify RED** — run `python -m unittest scripts.tests.test_refresh_local_skill -v`; expect import failure because the refresher module is absent.

- [ ] **Step 3: Implement minimal refresher** — derive the four current replacements from `repo_dir`, validate source and recipients before rendering, reject unresolved tokens, write to a sibling temporary file then atomically replace `SKILL.local.md`, and print `Source SHA-256:` plus `Local SHA-256:` from the CLI.

- [ ] **Step 4: Verify GREEN** — run `python -m unittest scripts.tests.test_refresh_local_skill -v`; expect PASS.

### Task 2: Self-refreshing workflow instruction

**Files:**
- Modify: `SKILL.md:after path discovery`
- Modify: `README.md:202-212`
- Test: `scripts/tests/test_refresh_local_skill.py`

**Interfaces:**
- A local execution runs `python "$SCRIPTS/refresh_local_skill.py" --repo-dir "$NR_DIR" before reading report data.
- On success, it re-reads `SKILL.local.md` and continues at Step 1; it does not execute Step 0 a second time in the same run.

- [ ] **Step 1: Write failing source-content assertion**

```python
def test_template_requires_refresh_then_continue_at_step_one(self):
    template = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    self.assertIn("refresh_local_skill.py", template)
    self.assertIn("continue at Step 1", template)
```

- [ ] **Step 2: Verify RED** — run the focused test; expect failure because the template lacks the refresh instruction.

- [ ] **Step 3: Add Step 0** — place it before report-data access. It must stop on script failure, reload the updated local skill, and explicitly continue at Step 1 rather than repeat Step 0.

- [ ] **Step 4: Document the first-run rollout** — explain that the operator runs `python scripts/refresh_local_skill.py` once after updating the repo, then keeps Cowork pointed at `SKILL.local.md`.

- [ ] **Step 5: Verify GREEN** — run `python -m unittest scripts.tests.test_refresh_local_skill -v` and `python -m unittest discover -s scripts/tests -v`; expect PASS.

### Task 3: Roll out and verify the current local skill

**Files:**
- Generate: `SKILL.local.md` (gitignored)

- [ ] **Step 1: Run the refresher against the current repository** — require success and output hashes.
- [ ] **Step 2: Confirm local workflow content** — verify `SKILL.local.md` has no `{{...}}` tokens and contains the review-led P1/P2, validation, PDF, and Step 0 instructions.
- [ ] **Step 3: Preserve scope** — do not stage or commit `SKILL.local.md`, report outputs, or existing user-local files.

### Task 4: Harden the refresh boundary

**Files:**
- Modify: `scripts/refresh_local_skill.py`
- Modify: `scripts/tests/test_refresh_local_skill.py`
- Modify: `SKILL.md:Step 0`

**Interfaces:**
- The refresher accepts a trusted template path and an explicit Windows repository path, while still writing `SKILL.local.md` through the session repository path.
- Rendering preserves the template's exact newline bytes except for intended placeholder substitution, and computes the local hash before replacing the existing output.
- Step 0 uses the Windows Read/Write workflow already used for report sources so its script/template inputs cannot come from a stale session mount.

- [ ] **Step 1: Add failing cross-platform and CRLF tests** — demonstrate that a trusted Windows root renders Windows paths and a CRLF template does not become `CRCRLF`.
- [ ] **Step 2: Verify RED** — run the focused refresher tests and confirm the new assertions fail.
- [ ] **Step 3: Implement safe explicit inputs** — add the minimal CLI/API inputs, preserve atomic output behavior, and precompute the rendered-byte hash before replace.
- [ ] **Step 4: Harden Step 0** — read the refresher and template at their trusted Windows paths into the current session outputs directory, then run that copy with an explicit Windows root before continuing at Step 1.
- [ ] **Step 5: Verify GREEN** — run the focused and complete test suites; manually refresh the ignored local skill without staging it.
