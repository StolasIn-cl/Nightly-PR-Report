<#
.SYNOPSIS
    One-time local setup for the Nightly PR Report.

.DESCRIPTION
    Prompts for a GitHub PAT locally, configures the repository-specific Git
    identity and recipient list, then registers the Windows scheduled tasks.
    Run this script from an elevated PowerShell window.
#>

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an Administrator PowerShell window."
}

$repoDir = Split-Path -Parent $PSScriptRoot
$setupScript = Join-Path $PSScriptRoot "setup_nightly_report.py"
$taskScript = Join-Path $PSScriptRoot "register_tasks.ps1"

$gitName = "CLT\stolas_in"
$gitEmail = "stolas_in@cyberlink.com"
$recipients = @(
    "Alexander_Wang@cyberlink.com",
    "Andrew_Liang@cyberlink.com",
    "Angus_Hung@cyberlink.com",
    "Eddy_Hsu@cyberlink.com",
    "Eleven_Lin@cyberlink.com",
    "HenryCH_Liu@cyberlink.com",
    "Joe_Wu@cyberlink.com",
    "leon_tsai@cyberlink.com",
    "Paxton_Hsu@cyberlink.com",
    "StevenLK_Liu@cyberlink.com",
    "Stolas_In@cyberlink.com",
    "WayneXY_Lin@cyberlink.com",
    "Yihsuan_Hsueh@cyberlink.com"
)
$reportRecipients = $recipients -join "; "

Write-Host "Nightly PR Report local setup"
Write-Host "Repository: $repoDir"
Write-Host "Git author: $gitName <$gitEmail>"
Write-Host "Outlook sender: Stolas_In@cyberlink.com (the account already signed in to Outlook Web)"
Write-Host "Recipients: $($recipients.Count)"

$secureToken = Read-Host "Enter a GitHub PAT with Contents read/write access" -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)

try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    if ([string]::IsNullOrWhiteSpace($token)) {
        throw "A GitHub PAT is required."
    }

    & python.exe $setupScript `
        --token $token `
        --git-name $gitName `
        --git-email $gitEmail `
        --report-email $reportRecipients
    if ($LASTEXITCODE -ne 0) {
        throw "Repository setup failed with exit code $LASTEXITCODE."
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $taskScript
    if ($LASTEXITCODE -ne 0) {
        throw "Windows scheduled-task registration failed with exit code $LASTEXITCODE."
    }

    Get-ScheduledTask -TaskName "NightlyPR-Fetch", "NightlyPR-Cleanup" |
        Select-Object TaskName, State |
        Format-Table -AutoSize
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}
