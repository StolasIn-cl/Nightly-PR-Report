---
name: nightly-pr-report-one-off
description: 在不對本機做任何持久化設定的前提下，產生單次的 PR 報告（可選擇是否寄出）。給只想跑一次的使用者，或不想在自己電腦上留下 git remote / Task Scheduler / SKILL.local.md 的人使用。
---

# 一次性報告產生流程（不落地設定）

這份文件給 **Agent**（Cowork / Claude Code / Codex 任一種）讀取，用來處理下面這種需求：

> 使用者只想產生「這一次」的 PR 報告，不想像 [README.md](README.md) 的「首次設定」那樣，在自己電腦上留下：
> - `scripts\setup_nightly_report.py` 寫入的 git remote / 這個 repo 專用的 `user.name` / `user.email`
> - `register_tasks.ps1` 註冊的 Windows Task Scheduler 排程
> - 提交在 repo 目錄下、不會被清掉的 `SKILL.local.md` / `recipients.json`

如果使用者要的是**每天自動跑**，請改用 [README.md](README.md) 的首次設定流程，不要用這份文件。

---

## 與正式流程的差異

| 項目 | 正式流程（README.md） | 一次性流程（本文件） |
|---|---|---|
| git remote / 本機 git 身分 | `setup_nightly_report.py` 寫入並持久化 | 不建立；優先重用使用者既有的 `promeo-pc-promeo` clone |
| 排程 | `register_tasks.ps1` 註冊 Task Scheduler | 不註冊，Agent 手動跑一次 |
| `SKILL.local.md` / `recipients.json` | 寫在 repo 根目錄，長期存在 | 只寫在一個暫存資料夾，跑完即刪 |
| `nightly-report-data.json` / `.html` / `.pdf` | 寫在 repo 根目錄，下次覆蓋 | 寫在暫存資料夾，跑完即刪 |
| Data branch 清理（`remove_nightly_report_data.py`） | 由排程負責 | **不要執行** — 見下方「禁止事項」 |

---

## Step 0 — 跟使用者確認三件事

在動手前，先跟使用者確認（不要用預設值硬猜）：

1. **要出哪一天的報告？** 預設為「昨天」（沿用 `get_nightly_report_data.py` 的 `--date` 預設）。
2. **要不要真的寄出？**
   - 要寄：跟使用者要這次的收件信箱（一個或多個）。
   - 不寄：只產生 PDF 給使用者自己看，完全跳過 Outlook 相關步驟。
3. **這台機器上有沒有已經在用的 `promeo-pc-promeo` clone？**（平常開發用的那一份就可以）
   - 有：直接重用，完全不需要新增任何 git remote 或身分設定。
   - 沒有：需要使用者提供一個**一次性**的 GitHub PAT，只在這次的指令環境變數中使用，絕不寫進任何 `.git/config` 或檔案。

---

## Step 1 — 建立暫存工作資料夾

所有一次性產物都寫在系統暫存目錄底下的獨立資料夾，**不要**寫進 `Nightly-PR-Report` repo 目錄：

```powershell
$SCRATCH = Join-Path $env:TEMP ("nightly-pr-report-oneoff-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $SCRATCH | Out-Null
echo $SCRATCH
```

後續所有輸出檔案都放在 `$SCRATCH` 底下。記下這個路徑，Step 6 結束時要整個刪掉。

---

## Step 2 — 取得 PR 資料（不建立新的 git 設定）

### 2a. 使用者已有 `promeo-pc-promeo` clone（優先選這條路）

`scripts\get_nightly_report_data.py` 只需要「在一個已設好 `origin` 且能 fetch `data/test-mapping` 的 git repo裡執行」，跟哪個資料夾無關。所以直接在使用者既有的 clone 裡執行即可，**不需要**碰 `Nightly-PR-Report` 這個 repo 的 git 設定：

```powershell
cd <使用者既有的 promeo-pc-promeo clone 路徑>
python <Nightly-PR-Report 路徑>\scripts\get_nightly_report_data.py `
  --date <DATE> `
  --out "$SCRATCH\nightly-report-data.json"
```

這樣完全不會動到 `Nightly-PR-Report` repo 的 `.git/config`。

### 2b. 使用者沒有既有 clone（才需要這條路）

用一次性 PAT 在暫存資料夾裡建立一個**用完即丟**的 clone，不要用 `setup_nightly_report.py`（那支腳本會把設定寫回 `Nightly-PR-Report` repo 並持久化）：

```powershell
git clone --filter=blob:none --no-checkout `
  "https://<ONE_OFF_PAT>@github.com/CyberLink-Team/promeo-pc-promeo.git" `
  "$SCRATCH\promeo-scratch-clone"
cd "$SCRATCH\promeo-scratch-clone"
python <Nightly-PR-Report 路徑>\scripts\get_nightly_report_data.py `
  --date <DATE> `
  --out "$SCRATCH\nightly-report-data.json"
```

PAT 只出現在這一次的指令字串裡，不要把它寫進任何檔案、環境變數設定檔或 `.git/config`（`--filter=blob:none --no-checkout` 這個 clone 本身在 Step 6 會整個被刪掉，含它的 `.git/config`）。

### 驗證

```powershell
Test-Path "$SCRATCH\nightly-report-data.json"
```

若資料的 `pr_count` 為 0，比照 [SKILL.md](SKILL.md) Step 1 的規則：直接跳到「寄出結果」步驟，寄一封「今天沒有 PR 活動」的一行信（或者如果使用者選了不寄，就直接回報沒有 PR 活動並結束）。

---

## Step 3 — 產生 HTML 報告

```powershell
python <Nightly-PR-Report 路徑>\scripts\new_pr_report_html.py `
  --data "$SCRATCH\nightly-report-data.json" `
  --out "$SCRATCH\nightly-report.html"
```

---

## Step 4 — 產生 Author Notes 並驗證

做法與 [SKILL.md](SKILL.md) Step 3 完全相同（slim payload → 依專案提示產生摘要 → 驗證 → 塞回 placeholder），差別只在所有檔案路徑都指向 `$SCRATCH` 而不是 repo 根目錄：

- 產生的 slim JSON 一樣來自 `$SCRATCH\nightly-report-data.json`。
- 產生的 HTML 存成 `$SCRATCH\author-summary.html`。
- 驗證：
  ```powershell
  python <Nightly-PR-Report 路徑>\scripts\validate_author_notes.py `
    --data "$SCRATCH\nightly-report-data.json" `
    --html "$SCRATCH\author-summary.html"
  ```
- 驗證通過後才把內容塞回 `$SCRATCH\nightly-report.html` 的 `<!-- AUTHOR_SUMMARY -->` placeholder。

驗證失敗就停下來回報，不要產生 PDF。

---

## Step 5 — 轉成 PDF

```powershell
node <Nightly-PR-Report 路徑>\scripts\render_report.cjs "$SCRATCH\nightly-report.html" "$SCRATCH\nightly-report.pdf"
```

使用與正式報告相同的獨立 profile renderer；失敗時停止，不使用舊 PDF。

產生後跟使用者確認 PDF 內容（可以先讓使用者看過，不一定要馬上寄）。

---

## Step 6 — 依 Step 0 的選擇決定是否寄出

### 選擇「不寄」

把 `$SCRATCH\nightly-report.pdf` 的路徑或內容交給使用者確認完即可，跳到「Step 7 — 清理」。

### 選擇「要寄」

將這次的暫存收件者、主旨、本文及 PDF 包裝成共用 delivery manifest，依 `C:/Users/stolas_in/.codex/skills/report-delivery/SKILL.md` 提交與寄送；不再引用本專案的 Outlook 步驟。不要修改正式 recipients.json，也不要執行正式報告的 sync。使用獨立 one-off report_id 與指定統計日，沿用同日期防重寄；寄送前確認當次使用者確實要求寄信。若本次是流程測試，收件者只能是 Stolas_In@cyberlink.com。

共用模組會保存防重寄紀錄與附件快照；這是寄信必要的持久化紀錄，不能聲稱完全不留痕跡。要求完全不留寄送紀錄的單次執行只能產報告、不寄信。

---

## Step 7 — 清理（一定要做）

報告完成或共用寄送已取得獨立快照後，只清理本次確認過的暫存資料夾；不得刪除共用寄送紀錄／spool 或未知寄送結果所需證據。刪除前核對 SCRATCH 的絕對路徑確實是本次暫存目錄：

```powershell
Remove-Item -Recurse -Force $SCRATCH
```

跟使用者回報：本次是一次性執行，沒有在這台機器上新增 git remote、沒有註冊排程、沒有留下正式 `SKILL.local.md` / `recipients.json` 設定；若曾寄送，共用模組仍保留防重寄紀錄與附件快照。

---

## 禁止事項

- **不要**執行 `scripts\setup_nightly_report.py` — 它會把 git remote 與 `user.name` / `user.email` 寫進 `Nightly-PR-Report` repo 的 `.git/config` 並持久化。
- **不要**執行 `scripts\register_tasks.ps1` — 一次性任務不需要 Windows Task Scheduler。
- **不要**執行 `scripts\remove_nightly_report_data.py` — 這支腳本會修改 GitHub 上共用的 `data/test-mapping` branch（刪除舊的 `pr-runs/` 資料），屬於正式排程機器的職責，一次性使用者不應該動到共用的遠端資料。
- **不要**把一次性 PAT 寫進任何檔案（`.git/config`、腳本、`recipients.json` 等）；只在單次指令的字串中使用，並於 Step 7 隨暫存 clone 一併刪除。
- **不要**把 `$SCRATCH` 底下的任何檔案複製回 `Nightly-PR-Report` repo 根目錄。
