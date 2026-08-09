param(
    [switch]$Apply,
    [string]$Python = "python",
    [string]$TaskName = "ControlCenter-HANRI-R24"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR24\app"
$StateRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR24\state"
$LogRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR24\logs"

if (-not $Apply) {
    Write-Host "DRY RUN"
    Write-Host "Source: $SourceRoot"
    Write-Host "Install: $InstallRoot"
    Write-Host "Task: $TaskName"
    Write-Host "Re-run with -Apply to install."
    exit 0
}

New-Item -ItemType Directory -Force -Path $StateRoot, $LogRoot | Out-Null
$Backup = "$InstallRoot.backup.$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
if (Test-Path $InstallRoot) {
    $existing = Get-ChildItem -Force $InstallRoot -ErrorAction SilentlyContinue
    if ($existing) {
        Copy-Item -Recurse -Force $InstallRoot $Backup
    }
    Remove-Item -Recurse -Force $InstallRoot
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r24.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"
$Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$TriggerMinute = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerMinute) -Settings $Settings -Description "HANRI R24 bounded recursive improvement supervisor" -Force | Out-Null

Set-Location $InstallRoot
$env:PYTHONPATH = $PythonPath
& $Python -m hanri once --config $Config
if ($LASTEXITCODE -ne 0) { throw "Initial HANRI run failed with exit code $LASTEXITCODE" }
Write-Host "Installed $TaskName"
Write-Host "State: $StateRoot"
if (Test-Path $Backup) { Write-Host "Backup: $Backup" }
