# Nightly PR Report

產生前一天的 PR 報告、作者審查摘要、PDF 與郵件 manifest。本專案擁有收件者、原有郵件標題、本文及附件；Chrome Outlook 寄送集中維護於 `C:/Users/stolas_in/Desktop/Report-Delivery` 與全域 `report-delivery` skill。

## 正式時程（Asia/Taipei）

| 工作 | 時間 | 負責者 |
| --- | --- | --- |
| 抓前一天資料 | 週二至週六 07:30 | 既有 Windows NightlyPR-Fetch |
| 產報告＋寄送 | 週二至週六 09:00 | Codex Nightly PR report |
| 清理過期 pr-runs | 週二至週六 09:00 | 既有 Windows NightlyPR-Cleanup |

WER 是另一個專案，每天 08:00 觸發。寄信共用 mailbox 鎖，即使執行時間重疊也不並行操作 Outlook。

## 執行分工

1. 排程固定台灣時間昨天為 DATE，讀取 `SKILL.md`，刷新並使用 `SKILL.local.md`。
2. `python scripts/prepare_delivery.py preflight --date DATE` 驗證資料日期、完整性；缺 fetch／舊資料就停止，不寄舊報告。
3. 依 skill 執行 HTML 骨架、作者摘要與 `validate_author_notes.py`。審查摘要內容規則維持原本要求。
4. `python scripts/prepare_delivery.py prepare --date DATE` 透過本機獨立 profile renderer 產生有日期 PDF 與 manifest。零 PR 產生原本一行通知，明確無附件。
5. 排程執行 `python scripts/prepare_delivery.py submit --date DATE`，再呼叫共用寄送 skill 操作已登入的 Chrome Outlook。
6. 只有 shared sent receipt 確認後，`python scripts/prepare_delivery.py sync --date DATE` 才更新相容的 `run-status.json`。延遲寄送依快照統計同步，不讀隔天覆寫資料。

共用模組處理附件快照、跨程序鎖、佇列、防重寄、中斷恢復、寄件備份查證與故障診斷。Luna 6 xhigh 在有界嘗試後仍無法解決寄送問題，委派 gpt-6.1-sol 分析並嘗試恢復；報告內容或 fetch 失敗仍停止。不明寄送結果只查證，不重寄。已寄過日期跳過。

## 郵件內容與輸出

- 收件者：本機 `recipients.json` 的 recipients 陣列；不寫死人數。WER 讀取後加 Elvis，但不改此檔案。
- 原主旨：`PR Daily Report — DATE (N PRs, F failed)`；原本文為 pass/fail/skipped 摘要與 PDF 附件提示。
- 原始資料：`nightly-report-data.json`；報告 HTML：`nightly-report.html`；摘要：`author-summary.html`。
- PDF：`output/DATE/PR-Daily-Report-DATE.pdf`。
- manifest：`output/DATE/delivery-manifest.json`。
- receipt：`output/DATE/delivery-receipt.json`；最新相容狀態：`run-status.json`。
- 寄送權威紀錄與實際寄送附件快照：`Report-Delivery/state/`。

測試信只可寄 `Stolas_In@cyberlink.com`，使用共用模組的 `make_test.py` 建立獨立測試 manifest，不改正式收件人。

## 本機環境與設定

需要 Python 3.11+、Node、Chrome、可用的 playwright-core、Git／gh 及目前已授權的來源 repo。PDF renderer 優先使用 PLAYWRIGHT_MODULE，其次一般 Node 套件與本機 issue tracker skill 已安裝的 playwright-core。不依賴 WeasyPrint／GTK；不控制使用者 Chrome profile 來列印 PDF。

既有新機設定工具：`scripts/setup_nightly_report.py`、`scripts/configure_nightly_report_local.ps1`、`scripts/register_tasks.ps1`。變更 git remote／憑證／Windows 工作前，先讀各工具的參數說明，保留原 fetch／cleanup 分工。不要在聊天或報告中輸出 token。Codex 排程由 app automation 工具維護，不手寫修改 automation.toml。

共用模組需安裝在兄弟目錄 Report-Delivery；sender_account 由其 config.local.json 設定，寄送時必須核對實際 Outlook 帳號。全域 skill 是模組內 skill/report-delivery 的 directory junction，只有一份維護來源。

`SKILL.local.md` 由 `python scripts/refresh_local_skill.py --repo-dir .` 產生，不直接修改。可提交模板與本機設定分離；recipients、輸出、狀態與憑證不提交。

## 驗證與故障排除

`python -m unittest discover -s scripts/tests -v`

報告錯誤：核對 fetch 日期、資料內容與 Author Notes 驗證；PDF 錯誤查本機 renderer。寄送錯誤：依共用 skill 的 connection／chooser／upload／Sent Items 診斷與 Sol 升級流程，不各自維護一套 Outlook 步驟。登入、實際工具審核或安全拒絕無法靠提示詞消除，必須回報具體阻擋。

單次報告參考 `ONE_OFF_REPORT.md`；不安裝新排程。採用共用寄送時仍需保留防重寄紀錄與附件快照，不宣稱寄信後完全不留下紀錄。
