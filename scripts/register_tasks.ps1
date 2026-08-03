<#
.SYNOPSIS
    Register NightlyPR-Fetch and NightlyPR-Cleanup as Windows Scheduled Tasks.
    Run once on any new machine. Requires Administrator privileges.
    Both tasks only fire Tuesday through Saturday, matching the Cowork
    report task, since the report covers the previous day's PRs and only
    Monday-Friday activity needs to be reported (Tue = Mon's PRs, ...,
    Sat = Fri's PRs).

.PARAMETER FetchTime
    Tuesday-Saturday run time for run_fetch.bat (default: 09:00).

.PARAMETER CleanupTime
    Tuesday-Saturday run time for run_cleanup.bat (default: 10:30).

.EXAMPLE
    # Default times — run from the Nightly-PR-Report root:
    powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1

    # Custom times:
    powershell -ExecutionPolicy Bypass -File scripts\register_tasks.ps1 -FetchTime "08:30" -CleanupTime "11:00"

.NOTES
    The bat files (scripts\run_fetch.bat / scripts\run_cleanup.bat) are expected
    alongside this script inside the scripts folder.
    Tasks run as the current logged-in user so git credentials are inherited.
#>
param(
    [string]$FetchTime   = "09:45",
    [string]$CleanupTime = "10:30"
)

$RunDays = @("Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

$ErrorActionPreference = "Stop"

# Nightly-PR-Report root is the parent of scripts/
$NRDir      = Split-Path -Parent $PSScriptRoot
$FetchBat   = Join-Path $NRDir "scripts\run_fetch.bat"
$CleanupBat = Join-Path $NRDir "scripts\run_cleanup.bat"

Write-Host ""
Write-Host "Nightly-PR-Report: $NRDir"
Write-Host "Fetch bat        : $FetchBat"
Write-Host "Cleanup bat      : $CleanupBat"
Write-Host ""

# Verify bat files exist
foreach ($f in @($FetchBat, $CleanupBat)) {
    if (-not (Test-Path $f)) {
        Write-Error "File not found: $f`nMake sure run_fetch.bat and run_cleanup.bat are in the Nightly-PR-Report root folder."
        exit 1
    }
}

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances  IgnoreNew

# ── NightlyPR-Fetch ──────────────────────────────────────────────────────────
$fetchAction  = New-ScheduledTaskAction `
    -Execute  "cmd.exe" `
    -Argument "/c `"$FetchBat`""

$fetchTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $RunDays -At $FetchTime

Register-ScheduledTask `
    -TaskName    "NightlyPR-Fetch" `
    -Description "Fetch PR data from data/test-mapping branch at $FetchTime, Tuesday-Saturday, for nightly report" `
    -Action      $fetchAction `
    -Trigger     $fetchTrigger `
    -Settings    $settings `
    -RunLevel    Highest `
    -Force | Out-Null

Write-Host "[OK] Registered NightlyPR-Fetch   @ $FetchTime (Tue-Sat)"

# ── NightlyPR-Cleanup ────────────────────────────────────────────────────────
$cleanupAction  = New-ScheduledTaskAction `
    -Execute  "cmd.exe" `
    -Argument "/c `"$CleanupBat`""

$cleanupTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $RunDays -At $CleanupTime

Register-ScheduledTask `
    -TaskName    "NightlyPR-Cleanup" `
    -Description "Remove stale pr-runs/ dirs older than 7 days at $CleanupTime, Tuesday-Saturday" `
    -Action      $cleanupAction `
    -Trigger     $cleanupTrigger `
    -Settings    $settings `
    -RunLevel    Highest `
    -Force | Out-Null

Write-Host "[OK] Registered NightlyPR-Cleanup @ $CleanupTime (Tue-Sat)"

Write-Host ""
Write-Host "Done. Open Task Scheduler to verify, or test immediately:"
Write-Host "  Start-ScheduledTask -TaskName NightlyPR-Fetch"
