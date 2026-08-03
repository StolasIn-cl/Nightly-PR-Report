# Nightly PR Report

週二至週六早上自動從 `data/test-mapping` branch 收集前一天的 PR 資料，透過 Cowork + Claude in Chrome 產生 PDF 報告並寄送到 Outlook（涵蓋週一至週五的 PR 活動；週日、週一不執行）。

這個 repo 現在採用「**可提交的模板 repo** + **本機產生的設定檔**」模式：

- 版本控制中的 [`SKILL.md`](C:/Users/stolas_in/Desktop/Nightly-PR-Report/SKILL.md) 是模板，不應寫入個人信箱或機器路徑。
- 首次設定時，`scripts\setup_nightly_report.py` 會在本機產生 `SKILL.local.md`。
- `SKILL.local.md` 是給 Cowork / Agent 實際使用的本機檔案，不應提交。

---

## 流程概觀

以下時間均只在**週二至週六**執行（週日、週一不執行，因為報告涵蓋的是週一至週五的 PR 活動）：

```text
09:00  Windows Task Scheduler
       -> scripts\run_fetch.bat
          -> scripts\get_nightly_report_data.py
             -> git fetch data/test-mapping
             -> 輸出 nightly-report-data.json

10:00  Cowork Scheduled Task
       -> 讀取 SKILL.local.md
       -> 產生 nightly-report.html
       -> 產生 nightly-report.pdf
       -> 開 Outlook Web 寄出報告
       -> 寫入 run-status.json

10:30  Windows Task Scheduler
       -> scripts\run_cleanup.bat
          -> scripts\remove_nightly_report_data.py
             -> 清掉 data branch 上超過保留天數（預設 7 天）的 pr-runs/
```

---

## Repo 結構

```text
Nightly-PR-Report/
├── README.md
├── SKILL.md                    # 可提交的模板
├── SKILL.local.md              # setup 產生，本機使用，不提交
├── .gitignore
└── scripts/
    ├── setup_nightly_report.py
    ├── register_tasks.ps1
    ├── run_fetch.bat
    ├── run_cleanup.bat
    ├── get_nightly_report_data.py
    ├── new_pr_report_html.py
    └── remove_nightly_report_data.py
```

執行產物會寫在 repo 根目錄，但都已列入 `.gitignore`：

- `fetch.log`
- `cleanup.log`
- `nightly-report-data.json`
- `nightly-report.html`
- `nightly-report.pdf`
- `run-status.json`

---

## 環境需求

- Python 3.9+
- Git for Windows
- Cowork
- Claude in Chrome
- 已登入 `outlook.office.com`
- 對 `CyberLink-Team/promeo-pc-promeo` 具備 fetch 權限

---

## 模板與本機設定

`SKILL.md` 內保留 placeholders，例如：

- `{{REPORT_EMAIL}}`
- `{{NR_DIR_WINDOWS}}`
- `{{SCRIPT_SOURCE_WINDOWS}}`
- `{{PDF_PATH_WINDOWS}}`

這些值不直接寫回模板。`setup_nightly_report.py` 會根據你目前這台機器的實際路徑與指定的收件信箱，渲染成 `SKILL.local.md`。

這樣做的目的：

- 可以安心把 repo commit 到自己的 repo 上。
- 不會把真實收件信箱寫回模板。
- 不會把你的 Windows 使用者名稱或本機路徑硬編進版本控制。

---

## 首次設定

### Step 1 - 複製 repo

把整個 `Nightly-PR-Report` 資料夾放到新電腦上，例如：

```powershell
cd C:\path\to\Nightly-PR-Report
```

### Step 2 - 執行 setup

```powershell
python scripts\setup_nightly_report.py
```

這個腳本會做幾件事：

- 初始化 / 更新此 repo 的 git remote
- fetch `data/test-mapping`
- 設定此 repo 專用的 `git user.name` / `git user.email`
- 產生 `SKILL.local.md`

可用參數：

- `--git-name`
- `--git-email`
- `--report-email`
- `--token`
- `--remote-url`

範例：

```powershell
python scripts\setup_nightly_report.py `
  --git-name "Your Name" `
  --git-email "you@example.com" `
  --report-email "report@example.com"
```

如果你要使用 PAT 避免互動式憑證視窗：

```powershell
python scripts\setup_nightly_report.py --token <GITHUB_PAT>
```

### Step 2 認證建議

避免直接使用 GitHub 互動式登入視窗，因為 Windows Credential Manager 可能會覆蓋其他 repo 共用的 `github.com` 憑證。

建議二選一：

1. `--token <GITHUB_PAT>`
2. 專用 SSH key + `github-nightly-report` host alias

SSH 方式範例：

```powershell
ssh-keygen -t ed25519 -f ~/.ssh/nightly_pr_report_ed25519 -N "" -C "nightly-pr-report@<hostname>"
type $HOME\.ssh\nightly_pr_report_ed25519.pub
```

把公鑰加到 GitHub 後，在 `~/.ssh/config` 中加入：

```sshconfig
Host github-nightly-report
    HostName github.com
    User git
    IdentityFile ~/.ssh/nightly_pr_report_ed25519
    IdentitiesOnly yes
```

然後把 remote 改成：

```powershell
git remote set-url origin git@github-nightly-report:CyberLink-Team/promeo-pc-promeo.git
git fetch origin data/test-mapping
```

### Step 3 - 註冊 Windows Task Scheduler

請用系統管理員 PowerShell（預設會註冊為週二至週六執行，時間為 fetch 09:00 / cleanup 10:30）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1
```

若要自訂時間：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1 -FetchTime "08:30" -CleanupTime "11:00"
```

> 若是更新既有機器上的排程（例如把時間或保留天數從舊版改過來），重新執行一次 `register_tasks.ps1` 即可覆蓋既有的 `NightlyPR-Fetch` / `NightlyPR-Cleanup` 工作定義。

確認任務存在：

```powershell
Get-ScheduledTask -TaskName "NightlyPR-Fetch"
Get-ScheduledTask -TaskName "NightlyPR-Cleanup"
```

### Step 4 - 在 Cowork 連結資料夾

1. 開啟 Cowork
2. 連結 `Nightly-PR-Report` 資料夾
3. 確認側欄能看到這個資料夾

### Step 5 - 建立 Cowork Scheduled Task

請注意：**Cowork 應使用 `SKILL.local.md`，不是 `SKILL.md`。**

每次更新 repo 後，先在 repo 根目錄手動執行一次：

```powershell
python scripts\refresh_local_skill.py
```

這會以最新的 `SKILL.md` 重新產生本機 `SKILL.local.md`。之後 Cowork 仍持續指向 `SKILL.local.md`；每次執行報告前，它也會自動重新整理一次，確保流程與已提交的模板同步。

你可以在 Cowork 建立週二至週六 10:00 的排程（cron: `0 10 * * 2-6`），內容讀取：

```text
C:\path\to\Nightly-PR-Report\SKILL.local.md
```

建議第一次先手動 `Run now`，讓 Cowork / Claude in Chrome 把權限授權完。

---

## 驗證方式

### 手動測試 fetch

```powershell
cd C:\path\to\Nightly-PR-Report
scripts\run_fetch.bat
```

成功後：

- `fetch.log` 最後一行應為 `SUCCESS`
- `nightly-report-data.json` 應存在

### 手動測試 cleanup

```powershell
scripts\run_cleanup.bat
```

成功後：

- `cleanup.log` 最後一行應為 `SUCCESS`

### 確認 Cowork task

執行完畢後應能看到：

- `nightly-report.pdf`
- `run-status.json`

---

## 什麼可以 commit

可以提交：

- `README.md`
- `SKILL.md`
- `scripts/*.py`
- `scripts/*.bat`
- `scripts/*.ps1`
- `.gitignore`

不應提交：

- `SKILL.local.md`
- `fetch.log`
- `cleanup.log`
- `nightly-report-data.json`
- `nightly-report.html`
- `nightly-report.pdf`
- `run-status.json`

也不會被 commit 的本機設定：

- `.git/config`
- remote URL
- `~/.ssh/config`
- SSH private key

---

## 把這個 repo 放到你自己的 repo 上，會不會有風險？

### 1. 會不會把隱私上傳？

在目前這個設計下，只要你不要手動把 `SKILL.local.md` 或輸出檔強制加入版本控制，正常情況下不會。

真正有風險的原本是：

- 真實收件信箱
- 本機 Windows 使用者名稱
- 本機 repo 絕對路徑

現在這些都應該只出現在 `SKILL.local.md`，而不是 `SKILL.md`。

### 2. 會不會影響後續 git fetch？

不會因為你把這份專案 commit 到自己的 repo 就壞掉。

後續 fetch / push 是否正常，取決於：

- 這台機器的 `.git/config`
- 你的 PAT 或 SSH 設定
- `origin` 是否仍指向正確 repo

也就是說：

- 「把模板 repo commit 到你自己的 repo」本身沒問題
- 「把本機專用設定跟憑證流程搞混」才會出問題

---

## 常見問題

### setup 成功了，但 Cowork 寄信還是失敗

優先檢查：

- Cowork 是否真的用 `SKILL.local.md`
- Outlook Web 是否仍登入
- Claude in Chrome 權限是否已授權
- PDF 是否成功產生

### fetch 失敗

先手動試：

```powershell
git fetch origin data/test-mapping
```

如果出現登入視窗，不要直接登入，回頭改用：

- PAT
- 專用 SSH key

### cleanup 失敗

先手動試：

```powershell
python scripts\remove_nightly_report_data.py --keep-days 7
```

如果是權限或認證問題，通常也是 git remote / PAT / SSH 設定沒有對齊。
