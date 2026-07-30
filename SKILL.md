---
name: nightly-pr-report
description: 每天早上 8 點從 data/test-mapping branch 收集 PR 資料，產生 PDF 報告並以附件寄給本機 recipients.json 中的收件者
---

You are executing the nightly PR report for the promeo project.

For the local machine that renders this template, the Windows repo root is `{{NR_DIR_WINDOWS}}`.

## Path discovery (bash)

The session name changes on every run — never hardcode it. Resolve paths dynamically:

**Each bash call is independent: the working directory resets and shell variables do not carry over.** Re-run this whole block at the start of every bash call that uses `$NR_DIR`, `$DATA_FILE`, `$HTML_FILE`, `$AUTHOR_HTML_FILE`, or `$RECIPIENTS_FILE`. Never rely on exports from an earlier call, and never invoke a script by a relative path such as `scripts/foo.py` — always use `$NR_DIR/scripts/foo.py`.

```bash
export NR_DIR=$(ls -d /sessions/*/mnt/Nightly-PR-Report 2>/dev/null | head -1)
export SCRIPTS=$NR_DIR/scripts
export DATA_FILE=$NR_DIR/nightly-report-data.json
export HTML_FILE=$NR_DIR/nightly-report.html
export RECIPIENTS_FILE=$NR_DIR/recipients.json
echo "NR_DIR=$NR_DIR"
```

If `NR_DIR` is empty, stop and report the error: "Nightly-PR-Report directory not found. Ensure the folder is connected in Cowork."

---

## Step 0 — Refresh local workflow instructions

Before reading report data, refresh the local, path-resolved skill from the committed template. The session mount can be stale, so do **not** read the refresher or template from `$SCRIPTS` or `$NR_DIR` in bash.

Use the trusted Windows **Read** and **Write** workflow, as in Step 2:

1. Use the Read tool on `{{NR_DIR_WINDOWS}}\scripts\refresh_local_skill.py`, then use the Write tool to write that exact content to `refresh_local_skill.py` in the current session outputs directory on Windows.
2. Use the Read tool on `{{NR_DIR_WINDOWS}}\SKILL.md`, then use the Write tool to write that exact content to `SKILL.md` in the same session outputs directory on Windows.
3. Resolve those two outputs and run the copied refresher. `--repo-dir` remains the session repository for `recipients.json` and `SKILL.local.md`; `--windows-repo-dir` is the trusted Windows root used for every Windows-path placeholder:

```bash
REFRESH_OUT_DIR=$(ls -d /sessions/*/mnt/outputs 2>/dev/null | head -1)
[ -n "$REFRESH_OUT_DIR" ] || { echo "ERROR: Session outputs directory not found."; exit 1; }
REFRESH_SCRIPT_OUT="$REFRESH_OUT_DIR/refresh_local_skill.py"
TEMPLATE_OUT="$REFRESH_OUT_DIR/SKILL.md"
python3 "$REFRESH_SCRIPT_OUT" --repo-dir "$NR_DIR" \
  --template-path "$TEMPLATE_OUT" \
  --windows-repo-dir "{{NR_DIR_WINDOWS}}" \
  || { echo "ERROR: Failed to refresh SKILL.local.md; stop before reading report data."; exit 1; }
```

After the command succeeds, re-read the current `SKILL.local.md` and continue at Step 1. Do not execute Step 0 again during this run.

---

## Step 1 — Read pre-fetched data

The file at `$DATA_FILE` is written by `run_fetch.bat` (Windows Task Scheduler, 07:00 AM) before this task runs.

```bash
# Verify the file exists and covers yesterday (run_fetch.bat collects the previous day's PRs)
python3 << 'PYEOF'
import json, os, datetime, sys
f = os.environ.get('DATA_FILE', '')
if not os.path.exists(f):
    print("ERROR: nightly-report-data.json not found. run_fetch.bat may not have run.", file=sys.stderr)
    sys.exit(1)
data = json.load(open(f, encoding='utf-8'))
date = data.get('date', '')
yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
if date != yesterday:
    print(f"WARN: data is from {date}, not yesterday ({yesterday}). Proceeding anyway.")
print(f"OK: {data.get('pr_count', 0)} PR(s) for {date}")
PYEOF
```

Read the full contents of `$DATA_FILE`.

If `pr_count` is 0: skip to Step 5 (send a one-line "No PR activity today — <date>" email), then STOP.

---

## Step 2 — Generate HTML skeleton

**Do NOT use bash `cp` or read the script directly from `$SCRIPTS` in bash — the Linux mount can serve a stale cached version of the file.**

Instead, use the **Read tool** to read the script at its Windows path, then use the **Write tool** to write it to the outputs directory. This ensures you always get the latest version from Windows.

1. Use the Read tool on `{{SCRIPT_SOURCE_WINDOWS}}`
2. Use the Write tool to write the content to the current session outputs directory on Windows.
   - Example target path: `%APPDATA%\Claude\local-agent-mode-sessions\<session-id>\...\outputs\new_pr_report_html.py`
   - Resolve the outputs path dynamically in bash: `SCRIPT_OUT=$(ls -d /sessions/*/mnt/outputs 2>/dev/null | head -1)/new_pr_report_html.py`
3. Compile-check and run from the outputs path:

```bash
SCRIPT_OUT=$(ls -d /sessions/*/mnt/outputs 2>/dev/null | head -1)/new_pr_report_html.py
python3 -m py_compile $SCRIPT_OUT || { echo "ERROR: new_pr_report_html.py has a syntax error."; exit 1; }
python3 $SCRIPT_OUT --data $DATA_FILE --out $HTML_FILE
```

This writes the HTML report to `$HTML_FILE` with a `<!-- AUTHOR_SUMMARY -->` placeholder.

---

## Step 3 — Synthesise per-author summaries (Haiku sub-agent)

First, prepare a slim JSON payload containing only the fields the sub-agent needs:

```bash
python3 << 'PYEOF'
import json, os
data = json.load(open(os.environ['DATA_FILE'], encoding='utf-8'))
slim = []
for pr in data.get('prs', []):
    s = pr.get('summary') or {}
    slim.append({
        'author':          s.get('author', ''),
        'pr_number':       s.get('pr_number'),
        'run_url':         s.get('run_url', ''),
        'title':           s.get('title', ''),
        'outcome':         s.get('outcome', ''),
        'commit_message':  pr.get('head_commit_message') or None,
        'review_markdown': pr.get('review_markdown') or None,
    })

rft = data.get('rebuild_failed_tests') or {}
rebuild_failures = []
for t in rft.get('failed_tests', []):
    a = t.get('author') or {}
    raw = a.get('name') or ''
    name = raw.split('\\')[-1].split('/')[-1] if ('\\' in raw or '/' in raw) else raw
    rebuild_failures.append({
        'test_path':    t.get('path', ''),
        'author_name':  name,
        'author_email': a.get('email', ''),
    })

payload = {'prs': slim, 'rebuild_failures': rebuild_failures}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PYEOF
```

Take the printed JSON as `SLIM_JSON`. Then use the **Agent tool** with `model: "haiku"` and the following prompt, substituting the actual JSON for `SLIM_JSON`:

---
You are generating the Author Notes section for a nightly PR report (rendered as PDF).

Here is the data (JSON object with two keys — `prs` and `rebuild_failures`):
```
SLIM_JSON
```

`prs` is an array of PR entries. `rebuild_failures` is the list of test files that failed the nightly rebuild, each with the name and email of the developer who last touched that file.

Group all PRs by author. For each unique author, produce a card that:
1. Shows the author name as a header (no pass/fail/skip labels or symbols — those are already in the PR table above).
2. Lists ALL their PRs for the day. For each reviewed PR, use `review_markdown` as the primary evidence and concisely paraphrase the reviewed behaviour and impact. Use `title` and `commit_message` only as supporting context; never make either one the whole summary and never merely restate the PR title.
3. For every finding explicitly marked `[P1]` or `[P2]` in `review_markdown`, write a separate 1–2 sentence summary whose first content is the matching label: `<span class="priority-label priority-p1">P1</span>` or `<span class="priority-label priority-p2">P2</span>`. State the reviewed impact concisely after the label. Do NOT infer a priority from words such as "high-risk" or "dangerous", and do NOT invent risks.
4. If a reviewed PR has no explicit P1/P2 finding, summarise the behaviour the review examined or state that the review found no actionable regression. If `review_markdown` is null, summarise from the title and commit context and add a short italic note "review unavailable".
5. If any entry in `rebuild_failures` matches this author (match `author_name` to GitHub username, or `author_email` username part to GitHub handle — best effort), append a warning callout listing the affected test file(s). Use the label "Nightly rebuild failure". Only mention files that actually match this author; omit entirely for authors with no rebuild failures.

Generate HTML for ALL authors combined using ONLY this structure (modern div-based, no Outlook constraints):

```html
<!-- ═══ Repeat once per author ═══ -->
<div class="author-card">
  <div class="author-card-header">
    <span class="name">AUTHOR_NAME</span>
  </div>
  <div class="author-card-body">

    <!-- ── Repeat per PR ── -->
    <div class="pr-entry">
      <div class="pr-link">
        <a href="RUN_URL" style="color:#1565c0;font-weight:700;text-decoration:none">#PR_NUMBER</a>
        &nbsp;—&nbsp;PR_TITLE
      </div>
      <!-- Repeat this paragraph once per explicit P1/P2 finding. Use priority-p2 for P2. -->
      <p><span class="priority-label priority-p1">P1</span> The review found ...</p>
      <!-- With no explicit P1/P2 finding, use one unlabeled review-led summary paragraph. -->
      <p>REVIEWED_BEHAVIOUR_OR_NO_ACTIONABLE_REGRESSION</p>
    </div>
    <!-- ── End per-PR repeat ── -->

    <!-- Nightly rebuild failure callout: ONLY include if this author matches rebuild_failures -->
    <div class="risk-callout" style="margin-top:4px">
      <div class="bar" style="background:#c62828"></div>
      <div class="content" style="background:#fff5f5">
        <span class="label" style="color:#c62828">Nightly rebuild failure: </span>
        <span style="color:#5f6368;font-family:monospace;font-size:10px">TEST_FILE_PATH</span>
      </div>
    </div>

    <!-- Review unavailable: ONLY include when review_markdown is null -->
    <p class="review-unavailable">review unavailable</p>

  </div>
</div>
<!-- ═══ End author block ═══ -->
```

Rules:
- Return ONLY the raw HTML — no markdown fences, no explanation.
- Do NOT include any pass / fail / skip labels or symbols anywhere in the author notes.
- HTML-escape all user-sourced strings (PR titles, author names, commit summaries, test file paths).
- The CSS classes (author-card, author-card-header, pr-entry, etc.) are defined in the report's stylesheet — use them exactly as shown.
- All PRs by the same author go inside one author block as multiple pr-entry divs.
- Every explicit `[P1]` or `[P2]` finding must appear in its PR's `pr-entry`, and the matching compact label must be the first content in that finding's summary paragraph.
- Never add a priority label or risk claim unless it is explicitly supported by `review_markdown`.
- A reviewed PR summary must paraphrase review evidence; a title-only or commit-only restatement is invalid. With no explicit findings, state reviewed behaviour or that there was no actionable regression.
- Omit review-unavailable if review IS available.
- Omit the rebuild failure callout if this author has no matching entry in `rebuild_failures`.
- Keep each PR summary to 1–2 sentences.
---

The agent's response is the complete `author_html`. Save the raw response as `$NR_DIR/author-summary.html`, then validate it before inserting it into the report:

```bash
export AUTHOR_HTML_FILE=$NR_DIR/author-summary.html
python3 "$NR_DIR/scripts/validate_author_notes.py" --data "$DATA_FILE" --html "$AUTHOR_HTML_FILE" \
  || { echo "ERROR: Author Notes validation failed; do not render the PDF."; exit 1; }
echo "Author Notes validation passed"
```

Only after validation succeeds, write it to the HTML file using Python inline:

```python
python3 << 'PYEOF'
import os
placeholder = '<!-- AUTHOR_SUMMARY -->'
html_file = os.environ.get('HTML_FILE', '')
author_html_file = os.environ.get('AUTHOR_HTML_FILE', '')
author_html = open(author_html_file, encoding='utf-8').read()
html = open(html_file, encoding='utf-8').read()
before_count = html.count(placeholder)
if before_count != 1:
    raise RuntimeError(f"Expected exactly one Author Notes placeholder, found {before_count}")
result = html.replace(placeholder, author_html, 1)
after_count = result.count(placeholder)
assert after_count == 0, f"Author Notes placeholder remains after replacement: {after_count}"
open(html_file, 'w', encoding='utf-8').write(result)
print("Placeholder replaced:", after_count == 0)
PYEOF
```

Verify the output prints `Placeholder replaced: True` before continuing.

---

## Step 4 — Convert HTML to PDF

Install weasyprint if needed and convert the HTML report to PDF:

```bash
pip install weasyprint --break-system-packages -q 2>&1 | tail -3
PDF_FILE=$NR_DIR/nightly-report.pdf
python3 -c "
from weasyprint import HTML
HTML(filename='$HTML_FILE').write_pdf('$PDF_FILE')
print('PDF written:', '$PDF_FILE')
"
echo "PDF size: $(wc -c < $PDF_FILE) bytes"
```

If weasyprint fails (import error, font issue, etc.), fall back to:
```bash
# Fallback: chromium headless print
chromium --headless --disable-gpu --print-to-pdf="$PDF_FILE" \
  --print-to-pdf-no-header "file://$HTML_FILE" 2>/dev/null
```

Validate the local output after either renderer:
```bash
test -s "$PDF_FILE" || { echo "ERROR: local PDF is empty or missing."; exit 1; }
```

Store the path as `PDF_FILE=$NR_DIR/nightly-report.pdf` for use in Step 5, then continue to Step 5 and send the report. Sending the email is a required part of this task.

---

## Step 5 — Send via Outlook Web (Claude in Chrome)

Compute from the data file:
- `DATE`        = `data.date`
- `PR_COUNT`    = `data.pr_count`
- `FAIL_COUNT`  = count of prs where summary.outcome == "fail"
- `PASS_COUNT`  = count of prs where summary.outcome == "pass"
- `SKIP_COUNT`  = count of prs where summary.outcome == "skipped"
- Subject line: `PR Daily Report — <DATE> (<PR_COUNT> PRs, <FAIL_COUNT> failed)`

### 5.0 Chrome and attachment preflight (required)

Use the user's **Chrome** profile for Outlook so its existing Microsoft sign-in can be reused. Do not assume the in-app browser is signed in.

- Before opening or composing in Outlook, confirm that a browser-control extension is reachable. Whichever agent runs this task, accept either the **ChatGPT Chrome Extension** or **Claude in Chrome** — use whichever one is available and do not require a specific vendor. If neither is available, wait 2 seconds and retry once. If neither is still available, stop and report the browser-connection problem; do not create an email and do not write `run-status.json`.
- Open Outlook using the user-provided Chrome bookmark when available, or navigate to `https://outlook.office.com` in the same Chrome profile. If the page shows a Microsoft sign-in screen, stop and ask the user to sign in in Chrome; do not switch browsers.
- Do **not** navigate to `chrome://extensions` or any other Chrome-internal settings page. Browser control may block internal URLs, and that block does not mean the **Allow access to file URLs** setting is disabled.
- Verify file-URL access only through the normal attachment flow in Step 5e: a general attachment chooser that accepts the local PDF is the success signal. If the chooser is blocked or the upload fails, stop immediately without sending or writing `run-status.json`. Tell the user to manually check **Extensions → Manage Extensions → (ChatGPT Chrome Extension *or* Claude in Chrome, whichever this run used) → Details → Allow access to file URLs**, then rerun the task. Do not retry by attaching an image-only input or by using a native file picker.

### 5a. Open Outlook Web

Use the Chrome browser-control workflow from Step 5.0 to open **https://outlook.office.com** (or reuse the matching Chrome tab). Take a screenshot to confirm it loaded and is already signed in before composing.

### 5b. Open a new compose window

Find the "New mail" / "新郵件" button and click it. Wait for the compose pane to appear.

### 5c. Fill in To and Subject

- Use the **Read tool** to read the local recipient file at `{{RECIPIENTS_PATH_WINDOWS}}`. It is a JSON object with a `recipients` array of email addresses.
- Verify that the array is non-empty. If it is missing, invalid, or empty, stop and report the error; do not create an email.
- Click the **To / 收件者** field, enter every address from `recipients` (semicolon-separated), then press Tab.
- Click the **Subject / 新增主旨** field, type the subject computed above.

### 5d. Type a brief plain-text body

Click into the message body area. Type (do NOT inject HTML — just plain text):

```
PR Daily Report — <DATE>

✅ <PASS_COUNT> passed   ❌ <FAIL_COUNT> failed   ⏭ <SKIP_COUNT> skipped

Full report attached as PDF.
```

### 5e. Attach the PDF

Confirm `PDF_FILE` exists and has a non-zero size before opening the chooser. Use the browser's file-chooser flow with the visible **Attach file / 附加檔案** control, then select the local PDF path. This lets Outlook choose its active compose control and avoids stale or duplicate file inputs.

Outlook Web has **multiple file inputs** — one is image-only (`accept="image/*"`), while general attachment inputs have an empty or missing `accept` attribute. Inspect them before any fallback attempt:

```javascript
Array.from(document.querySelectorAll('input[type="file"]')).map((el, i) => ({ index: i, accept: el.accept }))
```

Never upload through the `accept="image/*"` input. If the general attachment control cannot open a chooser or the upload reports an error, stop and give the manual file-URL permission remediation from Step 5.0 rather than guessing among duplicate inputs.

Upload `{{PDF_PATH_WINDOWS}}`, then wait for the attachment chip to show its filename.

Take a screenshot to confirm the attachment chip appeared in the compose window before sending. If it does not appear, stop; do not send and do not write `run-status.json`.

### 5f. Send

Click the **Send / 傳送** button. Use the `wait` action to wait **8 seconds**, then take a screenshot.

**Send is confirmed if the compose pane is no longer visible.** The toast notification may appear and disappear quickly — its absence does NOT indicate failure; ignore it.

If the compose pane is still open after 8 seconds, wait 5 more seconds and take another screenshot. If still open after 13 seconds total, log the error and stop. Do NOT proceed to cleanup.

If the compose pane is closed, **always proceed to Step 6**.

---

## Step 6 — Write run status (ONLY after confirmed send)

Do NOT delete any files — they are left in place so the user can open and verify them:
- `nightly-report-data.json` — raw data (overwritten next run by run_fetch.bat)
- `nightly-report.html` — full HTML report (overwritten next run)
- `nightly-report.pdf` — the sent PDF (overwritten next run)

Write a status file so the user can see at a glance whether the task succeeded:

```bash
python3 << 'PYEOF'
import json, os, datetime
NR_DIR = os.environ.get('NR_DIR', '')
DATA_FILE = os.environ.get('DATA_FILE', '')

data = {}
if os.path.exists(DATA_FILE):
    try:
        data = json.load(open(DATA_FILE, encoding='utf-8'))
    except Exception:
        pass

prs = data.get('prs', [])
status = {
    'last_run':    datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'date':        data.get('date', ''),
    'pr_count':    data.get('pr_count', len(prs)),
    'fail_count':  sum(1 for p in prs if (p.get('summary') or {}).get('outcome') == 'fail'),
    'pass_count':  sum(1 for p in prs if (p.get('summary') or {}).get('outcome') == 'pass'),
    'skip_count':  sum(1 for p in prs if (p.get('summary') or {}).get('outcome') == 'skipped'),
    'email_sent':  True,
    'pdf_path':    os.path.join(NR_DIR, 'nightly-report.pdf'),
}
out = os.path.join(NR_DIR, 'run-status.json')
json.dump(status, open(out, 'w', encoding='utf-8'), indent=2)
print('Status written:', out)
print(json.dumps(status, indent=2))
PYEOF
```

---

## Guardrails

- **Email-first ordering is mandatory.** Write run-status.json only after send is confirmed.
- **Do not fabricate risk findings.** Only surface what `review_markdown` explicitly flags as high-risk or dangerous. When in doubt, omit.
- **Null-safe.** `review_markdown`, `head_commit_message` may be null. Handle gracefully; never crash.
- If Outlook Web is unreachable or PDF attachment fails, stop. Do NOT write run-status.json.
- **Branch cleanup is NOT done here.** `run_cleanup.bat` (Windows Task Scheduler, 08:30) handles removing old pr-runs/ dirs from the data branch.
