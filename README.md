# Nightly PR Report｜每日 PR 報告

將前一天的 PR 測試結果整理成 HTML、作者審查摘要與 PDF，再交由共用寄送流程發送郵件。

本專案負責**報告內容、收件者、郵件主旨、內文與附件**；Chrome Outlook 的操作與寄送狀態，統一由 [Report-Delivery](https://github.com/StolasIn-cl/Report-Delivery) 維護。

## 專案分工

| 元件 | 負責工作 |
| --- | --- |
| Nightly-PR-Report | 讀取 PR 資料、產生與驗證報告、決定郵件內容與收件者 |
| Report-Delivery | 附件快照、寄送佇列、Chrome Outlook 操作、防重寄與寄件備份查證 |
| Codex 排程 | 串接「產生報告 → 提交寄送工作 → 寄送 → 同步結果」 |

## 執行時程

以下皆為**台灣時間（Asia/Taipei）**。

| 工作 | 執行時間 | 負責排程 |
| --- | --- | --- |
| 擷取前一天的資料 | 週二至週六 07:30 | Windows `NightlyPR-Fetch` |
| 產生報告並寄送 | 週二至週六 09:00 | Codex `Nightly PR report` |
| 清理過期的 `pr-runs` | 週二至週六 09:00 | Windows `NightlyPR-Cleanup` |

WER 由另一個專案每日 08:00 觸發。兩者共用寄送鎖，即使工作重疊，也不會同時操作 Outlook。以上是觸發時間，實際寄出時間取決於報告產生與寄送耗時。

## 環境與設定

需要 Python 3.11 以上、Node.js、Chrome、`playwright-core`、Git 與已登入的 GitHub CLI（`gh`），並具備來源儲存庫的讀取權限。

將三個專案放在同一層目錄：

```text
Desktop/
├─ Nightly-PR-Report/
├─ WER-Daily-Report/
└─ Report-Delivery/
```

| 設定檔 | 用途 |
| --- | --- |
| `recipients.json` | 正式收件者，使用 `recipients` 陣列 |
| `SKILL.md` | 可提交的報告產生流程範本 |
| `SKILL.local.md` | 依本機路徑產生的流程，不直接修改 |
| `../Report-Delivery/config.local.json` | 寄件帳號；必須與實際 Outlook 帳號一致 |

更新本機流程：

```powershell
python scripts/refresh_local_skill.py --repo-dir .
```

新機設定可參考 `scripts/setup_nightly_report.py`、`scripts/configure_nightly_report_local.ps1` 與 `scripts/register_tasks.ps1`。執行前先閱讀各工具的參數說明，保留既有資料擷取與清理分工。Codex 排程透過應用程式的自動化工具維護。

PDF 使用獨立的 Chrome 執行環境，不使用已登入郵件的瀏覽器設定檔。渲染器依序尋找 `PLAYWRIGHT_MODULE`、一般 Node.js 套件，以及本機 issue tracker skill 已安裝的 `playwright-core`；不依賴 WeasyPrint 或 GTK。

## 報告與寄送流程

排程開始時固定前一天為統計日。下列 `2026-11-09` 為範例，執行時請換成該次統計日。

1. 讀取 [SKILL.md](SKILL.md)，更新並依 `SKILL.local.md` 執行。
2. 驗證資料日期與完整性：

   ```powershell
   python scripts/prepare_delivery.py preflight --date 2026-11-09
   ```

3. 依專案流程產生 HTML 與作者審查摘要（Author Notes），執行 `validate_author_notes.py`，通過後才將摘要放入報告。
4. 產生有日期的 PDF 與寄送清單（manifest），再提交共用佇列：

   ```powershell
   python scripts/prepare_delivery.py prepare --date 2026-11-09
   python scripts/prepare_delivery.py submit --date 2026-11-09
   ```

5. 排程依共用寄送 skill 操作 Chrome Outlook，核對收件者與附件、寄出並查證寄件備份。
6. 共用端確認 `sent` 後，才同步回本專案：

   ```powershell
   python scripts/prepare_delivery.py sync --date 2026-11-09
   ```

**產生報告不代表已寄送。** 延遲完成的工作依原統計日與附件快照同步，不讀取隔天覆寫的資料。零 PR 時沿用原本的一行通知，明確標示不附 PDF。

## 郵件與輸出檔案

正式主旨維持 `PR Daily Report — DATE (N PRs, F failed)`，內文包含通過、失敗、略過的統計與附件提示。WER 讀取本專案名單並加入 Elvis、去除重複地址，但不修改本專案的名單。

| 路徑 | 內容 |
| --- | --- |
| `nightly-report-data.json` | 原始報告資料 |
| `nightly-report.html` | 報告 HTML |
| `author-summary.html` | 作者審查摘要 |
| `output/DATE/PR-Daily-Report-DATE.pdf` | 該統計日的 PDF |
| `output/DATE/delivery-manifest.json` | 郵件內容、收件者與附件資訊 |
| `output/DATE/delivery-receipt.json` | 已確認的寄送結果 |
| `run-status.json` | 最新的相容狀態紀錄 |
| `../Report-Delivery/state/` | 共用寄送狀態與不可變的附件快照 |

本機收件名單、憑證、報告產物與寄送狀態不應提交至 Git。測試信**只可寄給 `Stolas_In@cyberlink.com`**，使用共用模組的 `make_test.py` 建立獨立測試清單，不修改正式名單。

## 驗證與故障處理

```powershell
python -m unittest discover -s scripts/tests -v
```

| 問題 | 處理方式 |
| --- | --- |
| 資料擷取失敗、日期過期、報告或摘要驗證失敗 | 停止並回報，不寄舊報告 |
| PDF 產生失敗 | 檢查本機渲染器，不改附舊 PDF |
| 瀏覽器連線、選檔、附件上傳或寄送查證失敗 | 依共用 skill 排查；Luna 6 xhigh 無法解決時，委派 `gpt-6.1-sol` 分析並嘗試一次有根據的恢復 |
| 寄送結果不明 | 查證寄件備份，不直接重寄 |
| 已確認寄送過的日期 | 跳過，避免重複寄送 |

實際登入、工具審核或政策阻擋仍須遵守，並回報具體原因。

單次報告請參考 [ONE_OFF_REPORT.md](ONE_OFF_REPORT.md)。單次流程不安裝新排程；若使用共用寄送，仍須保留防重寄紀錄與附件快照。
