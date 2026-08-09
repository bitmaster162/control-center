# Set-R28Interval-5min.ps1 — R63/D2 follow-up authorized by Robert ("давай пореже раз в 5 минут").
# Changes ControlCenter-HANRI-R28 repetition from 1 minute to 5 minutes. Nothing else.
# Run: powershell -ExecutionPolicy Bypass -File .\Set-R28Interval-5min.ps1
$ErrorActionPreference = "Stop"
$TaskName = "ControlCenter-HANRI-R28"
$t = Get-ScheduledTask -TaskName $TaskName
$TriggerLogon  = New-ScheduledTaskTrigger -AtLogOn
$TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
Set-ScheduledTask -TaskName $TaskName -Trigger @($TriggerLogon,$TriggerRepeat) -Action $t.Actions -Settings $t.Settings | Out-Null
Write-Host "OK: $TaskName now repeats every 5 minutes (was 1)."
Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object LastRunTime, NextRunTime
