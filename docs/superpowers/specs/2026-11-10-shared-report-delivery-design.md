# 共用報告寄送設計

日期：2026-11-10（Asia/Taipei）。狀態：使用者已核准，依追加要求實作。

## 目的與已確認需求

Nightly-PR-Report 與 WER-Daily-Report 各自產生報告並決定收件者、郵件主旨、本文、附件。寄送程式與操作 skill 移到獨立維護位置。Codex 排程組合「產生報告 → 寄送」兩段工作。

使用者確認沿用已登入的 Chrome Outlook Web；不採 Microsoft Graph／公司郵件 API。保留兩種報告原本的主旨與本文格式，共用寄送端不生成或修改這些內容。

穩定性目標：讓 Luna 可依明確流程操作，減少臨場猜測 API、錯用附件輸入、重複要求確認、兩個報告互相干擾。不能保證登入、Chrome bridge 或工具安全控制永不阻擋；遇到這些狀況要留下可診斷結果。

## 查證到的現況

- Nightly 的 SKILL.md Step 5 包含寄信與 Chrome 附件流程，Step 6 寫成功狀態；SKILL.local.md 由模板刷新，不能只改本機副本。
- WER RUNBOOK.md 引用 Nightly 的寄送步驟；daily_run.py 同時負責產報告與寄送狀態。
- Nightly 排程 nightly-pr-report-2：週二至週六 08:00，gpt-6-luna/xhigh，獨立 cron。
- WER 排程 wer-crash：每天 08:00，綁定既有 chat 的 heartbeat；設定本身沒有獨立 model 欄位。
- 相同觸發時間帶來共用 Chrome 的並行操作風險；尚未證明既有失敗由並行造成。
- 近期紀錄實際重現 Chrome `Emulation.setFocusEmulationEnabled` 10 秒逾時兩次；重開後寄送成功。底層原因未確認。
- 另一次停止是 WeasyPrint GTK 載入失敗、Edge 未產出新 PDF，以及本機 file URL 操作被政策阻擋；不是附件上傳故障。
- Nightly 以傳送後撰寫窗格消失判定成功，證據偏弱。WER 已有 generation、附件 SHA-256 及 send_unknown 防重寄，但不涵蓋 Nightly／跨專案共用寄送。
- 已讀資料不足以確定先前每次人工確認是模型主動詢問、工具審核或登入要求；需分開記錄，不能直接歸因模型能力。

## 分工與位置（以下為設計選擇）

獨立本機模組建議置於 `C:/Users/stolas_in/Desktop/Report-Delivery`，具備版本控制、CLI、schema、測試及診斷文件。全域 `report-delivery` skill 為薄入口，引用此固定位置，只有一份正式操作流程。報告專案不各自複製寄送程式。

| 層 | 責任 | 輸出 |
| --- | --- | --- |
| 報告專案 | 抓資料、內容、HTML/PDF、收件者、主旨、本文 | 不可變的 delivery manifest 與按日期保存的附件 |
| 共用模組 | 驗證、附件快照、排隊、寄送狀態、防重寄、診斷 | delivery receipt 與事件紀錄 |
| 共用 skill | 透過當前文件支援的 Chrome extension API 操作 Outlook | 寄件證據或具體失敗階段 |
| 排程 | 固定統計日、呼叫該專案產生報告、呼叫共用寄送、回報 | 本次執行結果與檔案連結 |

以模組處理可確定的規則；瀏覽器工具仍由 skill 操作，不在 CLI 偷接 Chrome CDP、讀 cookie 或另開未登入 profile。實作時只使用當次工具文件明確支援的 API。

## 兩個專案交付的契約

manifest 包含 schema_version、report_id、report_date、generation、generated_at、sender_account、recipients、subject、body、attachments。report_id 分別為 nightly-pr-report／wer-daily-report。sender_account 取目前寄送所用帳號並在遷移前核對，不依收件者猜測。

attachments 每筆包含絕對路徑、檔名、MIME type、byte size、SHA-256。日期在排程開始時依台灣時間固定，同次重試不重算。報告製作失敗、日期不符、空／無效收件者或附件不符即不提交寄送。Nightly 零 PR 沿用既有通知格式，允許明確宣告無附件；WER 無新增案件仍寄完整 PDF。

Nightly 保留既有 `PR Daily Report — <DATE> (...)` 格式、本文與原收件者。WER 保留 `WER Daily Report — <DATE>` 格式、本文、讀取 Nightly 名單加 Elvis 並去重的邏輯。這些全部留在報告端。以來源設定為準，不把人數寫死。

共用模組將通過驗證的 manifest 與附件保存成送信快照；送信時核對快照 hash，避免 Nightly 固定檔名被後續生成覆蓋。報告端只擁有產報告狀態；共用模組是寄送狀態唯一權威。原 run-status.json／WER state 可由 receipt 更新相容欄位，不能反過來決定新寄送成功。

## 防重寄、排隊與恢復

防重寄主鍵為 report_id + report_date + sender_account；generation／payload hash 用來拒絕同日期悄悄更換內容，不把新 generation 當作可重寄理由。已寄出只回傳既有 receipt；寄出結果不明則封鎖新的寄送。人工補寄應是明確獨立操作，本次不新增自動補寄政策。

使用跨程序原子鎖保護寄送紀錄，另以共用 Outlook mailbox 鎖涵蓋整個 compose／upload／send／verify 區段。兩個報告可同時產生，寄信依提交順序執行。排隊逾時留下 queued 結果供後續恢復，不能直接當作失敗後重建另一封。不得只因經過一段時間就刪除有不明寄送結果的鎖；中斷後須檢查持有程序與紀錄，再恢復。

不新增常駐服務或第三個排程。兩個既有排程都先執行共用 recovery，再產生／提交本次報告，最後 drain 佇列：取得 mailbox 鎖的執行者依序處理已驗證的 queued 工作，包含另一專案先前留下的報告；固定採各工作原本的日期，不以今天重新產生。等待中的執行者定期重試取得鎖；達執行預算後保留 queued，回報未寄送，下一次任一排程再次恢復。這只恢復曾提交且有完整附件快照的工作，不補建歷史報告；延遲寄送須在回報中明示。單一工作若 blocked／send_unknown，保留該工作供查證，不盲目重寄；確認失效執行者不再操作 Chrome 後，可釋放 mailbox 鎖處理其他獨立工作。recovery 對無法確認已停止的鎖持有者不得強制接手。

狀態分為 queued、composing、attached、send_requested、sent、failed_before_send、send_unknown、blocked。點 Send 前先持久化 send_requested；此刻中斷一律視為可能送出。任何可重試錯誤，都先確認目前狀態與原草稿，不能另建重複郵件。

遷移時先匯入 Nightly run-status.json、WER 各日期 sent／sending／send_unknown 紀錄。歷史 sent 標記 legacy 證據強度並防止自動重寄；缺乏歷史紀錄的舊日期不得自動補寄。不重設今天已寄送的狀態。

## Chrome 寄送流程

1. 讀取當前 CUA 文件與 Chrome extension inventory，選正確 backend，核對 Outlook 網址與登入帳號。不得猜 browser ID。
2. 同一路線連線失敗可重新取得 state／tab 並重試一次。仍失敗記錄 browser_connection_failed；不擅自關閉整個 Chrome。登入失效記錄 login_required。
3. 取得 mailbox 鎖後只操作本工作所建草稿。填入 manifest 的所有收件者、主旨與本文並逐項驗證。
4. 附件選單每次重新取頁面狀態。先註冊 filechooser 再點 Browse，以事件返回的 chooser.setFiles 上傳；不使用 image-only input。實際 API 以當次文件為準，文件缺失則記錄 capability_unavailable，不能虛構 API。
5. SPA 節點 detached 可重取選單並重試一次。chooser timeout／setFiles error 分別記錄；重試前檢查附件是否已加入，避免重複附檔。確認正確檔名、數量、上傳完成且無錯誤。
6. 傳送前再比對收件者、帳號、主旨、本文與附件清單，保存證據，持久化 send_requested，再點 Send 一次。
7. 觀察撰寫窗格結束與 Outlook 成功訊號，並核對寄件備份中本次主旨、時間、收件者及附件。撰寫窗格消失不單獨代表成功。工具可取得的 message ID／草稿 ID 要保存；無法取得不可捏造。
8. 已送出但證據不足標記 send_unknown，後續只查證不重寄。確認寄件備份匹配才產生 sent receipt；這表示 Outlook 已接受送出，不保證每位收件者實際投遞成功。

## 授權與診斷

排程 prompt 明確限定：固定報告、讀取專案名單、使用專案主旨本文與附件，依既有每日寄送授權完成，不追加模型自發的確認問題。原文件的其他命令與網頁／報告資料不視為新的寄送授權。

不能以 skill 消除工具實際的 approval gate、安全拒絕或登入要求，也不以換工具繞過。區分 model_requested_confirmation、tool_approval_required、policy_denied、login_required。保留真正的錯誤文字與階段，而不是一律回報「無法寄信」。

事件包含 run ID、report ID、統計日、phase、attempt、時間、backend／tab 參考、錯誤類型、attachment hash 與證據路徑；不記錄 cookie／token。診斷明確區分 PDF generation、連線、compose、chooser、upload、send verification。重開 Chrome 可列人工恢復建議，但不宣稱是已知根因的修復。

## 排程與 PDF 調整

Nightly 改為週二至週六 09:00 cron、WER 保留每日 08:00 heartbeat 與既有模型／chat，僅替換工作組合與必要的授權／失敗處理描述。修改前用 automation 工具確認目前設定，透過工具更新，不直接修改 TOML。不建立重複排程，也不影響 PR fetch／cleanup Windows 工作。

Nightly SKILL.md 與刷新來源移除 Outlook 操作與直接寫寄送成功的程式；WER RUNBOOK.md 不再引用 Nightly，daily_run.py 將寄送狀態交給共用模組，舊 CLI 可保留相容入口。兩者都明確在 report-ready 後交接 manifest。

PDF 製作仍屬報告端。Nightly 將目前臨場多路 fallback 收斂為可重現、獨立 profile 的本機 PDF renderer，避免依賴缺 GTK 的 WeasyPrint；參考 WER 現有本機 render_report.cjs。此 renderer 只處理自己的報告檔，不能用來繞過已發生的工具政策拒絕。逐次輸出到新路徑、驗證 PDF 與本次日期後才發布 manifest。

## 驗收與上線

- 模組測試涵蓋跨程序互斥、相同日期重試、已寄出跳過、Send 前後中斷、未知結果封鎖、附件變動、舊紀錄匯入及兩報告相同觸發時間。
- 使用假的郵件介面注入 detached、chooser timeout、upload error、Send 後斷線等故障，驗證有界重試及不重複寄送。
- 報告端測試驗證各自原本的收件者、主旨、本文、零筆資料規則、manifest 與 PDF freshness；執行既有相關測試。
- 使用實際 Chrome 做唯讀帳號／能力 preflight；可做只建草稿不上 Send 的附件驗證，完成後只清理本次草稿。
- 此重構請求不視為授權額外寄測試信給正式名單。實際寄送可由下一次既有授權的正式排程驗證，或另依使用者明確指定的測試收件者驗證。未做實際寄送不得宣稱端到端已通過。
- 更新前備份排程設定與既有文件，先驗證模組／兩專案，再切換排程。發現未解決的能力問題則保留舊排程，回報具體阻擋。

實作完成回報檔案、測試結果、是否實際送信、下一次觸發時間，以及尚存的 Chrome／登入依賴。設計稿本身不變更排程、不寄信。

## 核准後追加要求

PR 09:00、WER 08:00（台灣時間）。Luna 6 xhigh 遇到無法解決的寄送問題時，委派 gpt-6.1-sol 分析後嘗試一次有根據的恢復；報告資料／fetch／內容驗證失敗仍停止。測試信只可寄 Stolas_In@cyberlink.com，不影響正式名單。
