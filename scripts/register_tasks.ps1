<#
.SYNOPSIS
    Register NightlyPR-Fetch and NightlyPR-Cleanup as Windows Scheduled Tasks.
    Run once on any new machine. Requires Administrator privileges.
    Both tasks only fire Tuesday through Saturday, matching the Cowork
    report task, since the report covers the previous day's PRs and only
    Monday-Friday activity needs to be reported (Tue = Mon's PRs, ...,
    Sat = Fri's PRs).

.PARAMETER FetchTime
    Tuesday-Friday run time for run_fetch.bat (default: 07:30).

.PARAMETER SaturdayFetchTime
    Saturday run time for run_fetch.bat (default: 19:30).

.PARAMETER FetchOnly
    Update only the existing fetch task's triggers. Preserve its settings,
    actions and principal, and leave cleanup untouched.

.PARAMETER CleanupTime
    Tuesday-Saturday run time for run_cleanup.bat (default: 09:00).

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
    [string]$FetchTime   = "07:30",
    [string]$CleanupTime = "09:00",
    [string]$SaturdayFetchTime = "19:30",
    [switch]$FetchOnly
)

$RunDays = @("Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

$ErrorActionPreference = "Stop"

# Nightly-PR-Report root is the parent of scripts/
$NRDir      = Split-Path -Parent $PSScriptRoot
$FetchBat   = Join-Path $NRDir "scripts\run_fetch.bat"
$CleanupBat = Join-Path $NRDir "scripts\run_cleanup.bat"

$fetchTrigger = @(
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek @("Tuesday", "Wednesday", "Thursday", "Friday") -At $FetchTime
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At $SaturdayFetchTime
)

if ($FetchOnly) {
    Get-ScheduledTask -TaskName "NightlyPR-Fetch" -ErrorAction Stop | Out-Null
    Set-ScheduledTask -TaskName "NightlyPR-Fetch" -Trigger $fetchTrigger | Out-Null
    Write-Host "[OK] Updated NightlyPR-Fetch @ $FetchTime (Tue-Fri), $SaturdayFetchTime (Sat); cleanup unchanged"
    return
}

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

Register-ScheduledTask `
    -TaskName    "NightlyPR-Fetch" `
    -Description "Fetch PR data at $FetchTime Tue-Fri and $SaturdayFetchTime Sat; Friday full rebuild publication required" `
    -Action      $fetchAction `
    -Trigger     $fetchTrigger `
    -Settings    $settings `
    -RunLevel    Highest `
    -Force | Out-Null

Write-Host "[OK] Registered NightlyPR-Fetch   @ $FetchTime (Tue-Fri), $SaturdayFetchTime (Sat)"

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
