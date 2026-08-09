param(
    [switch]$Apply,
    [switch]$KeepPriorTasks,
    [string]$Python = "python",
    [string]$TaskName = "ControlCenter-HANRI-R27"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR27\app"
$StateRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR27\state"
$LogRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR27\logs"
$MigrationRoot = Join-Path $StateRoot "migration"
$PriorTasks = @("ControlCenter-HANRI-R24", "ControlCenter-HANRI-R25", "ControlCenter-HANRI-R26")

if (-not $Apply) {
    Write-Host "DRY RUN"
    Write-Host "Source: $SourceRoot"
    Write-Host "Install: $InstallRoot"
    Write-Host "Task: $TaskName"
    Write-Host "Prior HANRI tasks will be exported and disabled after a successful R27 initial run unless -KeepPriorTasks is used."
    Write-Host "R23 Return Sync is not changed."
    Write-Host "Re-run with -Apply to install."
    exit 0
}

New-Item -ItemType Directory -Force -Path $StateRoot, $LogRoot, $MigrationRoot | Out-Null
$Backup = "$InstallRoot.backup.$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
if (Test-Path $InstallRoot) {
    $existing = Get-ChildItem -Force $InstallRoot -ErrorAction SilentlyContinue
    if ($existing) { Copy-Item -Recurse -Force $InstallRoot $Backup }
    Remove-Item -Recurse -Force $InstallRoot
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r27.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"

# Fail closed: verify the copied payload before altering Scheduled Tasks.
Set-Location $InstallRoot
$env:PYTHONPATH = $PythonPath
& $Python -m compileall -q (Join-Path $InstallRoot "src")
if ($LASTEXITCODE -ne 0) { throw "R27 compile check failed with exit code $LASTEXITCODE" }
& $Python -m hanri once --config $Config
if ($LASTEXITCODE -ne 0) { throw "Initial HANRI R27 run failed with exit code $LASTEXITCODE" }

$Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$TriggerMinute = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerMinute) -Settings $Settings -Description "HANRI R27 truth-kernel causal bounded recursive improvement supervisor" -Force | Out-Null

if (-not $KeepPriorTasks) {
    foreach ($PriorTask in $PriorTasks) {
        $Task = Get-ScheduledTask -TaskName $PriorTask -ErrorAction SilentlyContinue
        if ($Task) {
            $XmlPath = Join-Path $MigrationRoot "$PriorTask.xml"
            Export-ScheduledTask -TaskName $PriorTask | Set-Content -Encoding UTF8 $XmlPath
            Unregister-ScheduledTask -TaskName $PriorTask -Confirm:$false
            Write-Host "Exported and disabled prior task: $PriorTask"
        }
    }
}

$MigrationReceipt = [ordered]@{
    schema_version = 1
    installed_at_utc = [DateTime]::UtcNow.ToString("o")
    installed_task = $TaskName
    prior_tasks_kept = [bool]$KeepPriorTasks
    prior_task_backups = @(Get-ChildItem -Path $MigrationRoot -Filter "ControlCenter-HANRI-R*.xml" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    r23_return_sync_modified = $false
    self_application = $false
    can_trade = $false
}
$MigrationReceipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $MigrationRoot "INSTALL_MIGRATION_RECEIPT.json")

Write-Host "Installed $TaskName"
Write-Host "State: $StateRoot"
Write-Host "Migration receipts: $MigrationRoot"
if (Test-Path $Backup) { Write-Host "Application backup: $Backup" }
