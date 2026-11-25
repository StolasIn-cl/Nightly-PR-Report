from pathlib import Path
import json
import subprocess
import unittest


class RegisterTasksTests(unittest.TestCase):
    def test_fetch_only_sets_two_triggers_without_touching_cleanup_or_settings(self):
        script = Path(__file__).resolve().parents[1] / 'register_tasks.ps1'
        command = r'''
$ErrorActionPreference = 'Stop'
function New-ScheduledTaskTrigger {
    param([switch]$Weekly, $DaysOfWeek, $At)
    [pscustomobject]@{ Days = @($DaysOfWeek); Time = $At }
}
function Get-ScheduledTask { param($TaskName, $ErrorAction) [pscustomobject]@{TaskName=$TaskName} }
function Set-ScheduledTask {
    param($TaskName, $Trigger)
    $global:result = @{Name=$TaskName; Triggers=@($Trigger)}
}
function Register-ScheduledTask { throw 'Must not re-register tasks' }
function New-ScheduledTaskSettingsSet { throw 'Must preserve settings' }
& 'SCRIPT_PATH' -FetchOnly | Out-Null
$global:result | ConvertTo-Json -Depth 4 -Compress
'''.replace('SCRIPT_PATH', str(script).replace("'", "''"))
        result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(data['Name'], 'NightlyPR-Fetch')
        self.assertEqual(data['Triggers'], [
            {'Days':['Tuesday','Wednesday','Thursday','Friday'], 'Time':'07:30'},
            {'Days':['Saturday'], 'Time':'19:30'},
        ])
