@echo off
:: ============================================================
:: run_fetch.bat - Windows Task Scheduler, 09:00, Tuesday-Saturday
:: Fetches PR data from the data/test-mapping branch and writes
:: nightly-report-data.json for the 10:00 Cowork task to read.
:: Log -> Nightly-PR-Report\fetch.log
:: ============================================================
setlocal

set "NR_DIR=%~dp0.."
set "LOG=%NR_DIR%\fetch.log"

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo [%DATE% %TIME%] run_fetch START >> "%LOG%"
echo. >> "%LOG%"

cd /d "%NR_DIR%"
for /f "tokens=*" %%d in ('powershell -c "(Get-Date).AddDays(-1).ToString('yyyy-MM-dd')"') do set YESTERDAY=%%d
python scripts\get_nightly_report_data.py --date %YESTERDAY% --out "%NR_DIR%\nightly-report-data.json" >> "%LOG%" 2>&1
set "EC=%ERRORLEVEL%"

echo. >> "%LOG%"
if %EC% neq 0 (
    echo [%DATE% %TIME%] FAILED  exit code=%EC% >> "%LOG%"
    echo ============================================================ >> "%LOG%"
    exit /b %EC%
)

echo [%DATE% %TIME%] SUCCESS >> "%LOG%"
echo ============================================================ >> "%LOG%"
endlocal
