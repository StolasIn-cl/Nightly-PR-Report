@echo off
:: ============================================================
:: run_cleanup.bat - Windows Task Scheduler, 08:30 every day
:: Removes pr-runs/ date dirs older than 2 days from the
:: data/test-mapping branch. Keeps today + yesterday visible.
:: Log -> Nightly-PR-Report\cleanup.log
:: ============================================================
setlocal

set "NR_DIR=%~dp0.."
set "LOG=%NR_DIR%\cleanup.log"

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo [%DATE% %TIME%] run_cleanup START >> "%LOG%"
echo. >> "%LOG%"

cd /d "%NR_DIR%"
python scripts\remove_nightly_report_data.py --keep-days 2 >> "%LOG%" 2>&1
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
