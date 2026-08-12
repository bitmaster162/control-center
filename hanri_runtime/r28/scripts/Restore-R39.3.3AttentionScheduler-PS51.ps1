param(
  [switch]$Apply,
  [string]$TaskName = 'ControlCenter-HANRI-R39-Attention',
  [string]$R36TaskName = 'ControlCenter-HANRI-R36'
)

$ErrorActionPreference = 'Stop'
$InstallBase = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_r39_3_3'
$InstallRepoRoot = Join-Path $InstallBase 'repo'
$LiveRoot = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\live_attention_r39_3_3'
$InstallReceipt = Join-Path $InstallBase 'INSTALL_R39_3_3_SCHEDULER_RECEIPT.json'

if (-not (Test-Path -LiteralPath $InstallReceipt -PathType Leaf)) { throw 'R39.3.3 install receipt missing' }
$install = Get-Content -Raw -Encoding UTF8 $InstallReceipt | ConvertFrom-Json
if ($install.status -ne 'PASS') { throw 'R39.3.3 install receipt status not PASS' }
if ($install.task_name -ne $TaskName) { throw 'R39.3.3 install receipt task mismatch' }
if (-not $install.backup_root) { throw 'R39.3.3 backup root missing from install receipt' }
$backupRoot = [string]$install.backup_root
$priorTaskXml = Join-Path $backupRoot 'previous_task.xml'
$priorTaskExisted = [bool]$install.prior_task_existed

$r36 = Get-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue
if (-not $r36) { throw 'R36 Scheduled Task missing; refusing rollback with unknown baseline' }
$r36XmlBefore = Export-ScheduledTask -TaskName $R36TaskName

Write-Host 'HANRI R39.3.3 scheduler rollback gate'
Write-Host "TASK $TaskName"
Write-Host "BACKUP_ROOT $backupRoot"
Write-Host "PRIOR_TASK_EXISTED $priorTaskExisted"
Write-Host 'R36_MODIFY false'

if (-not $Apply) {
  Write-Host 'DRY_RUN_ONLY true'
  Write-Host 'ROLLBACK_PERFORMED false'
  Write-Host 'Re-run with -Apply to remove R39.3.3 scheduler and restore the recorded predecessor.'
  exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

if (Test-Path $InstallRepoRoot) { Remove-Item -Recurse -Force $InstallRepoRoot }
if (Test-Path $LiveRoot) { Remove-Item -Recurse -Force $LiveRoot }

$backupRepo = Join-Path $backupRoot 'repo'
$backupLive = Join-Path $backupRoot 'live'
if (Test-Path $backupRepo) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InstallRepoRoot) | Out-Null
  Move-Item -Force $backupRepo $InstallRepoRoot
}
if (Test-Path $backupLive) {
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LiveRoot) | Out-Null
  Move-Item -Force $backupLive $LiveRoot
}

if ($priorTaskExisted) {
  if (-not (Test-Path -LiteralPath $priorTaskXml -PathType Leaf)) { throw 'prior R39 task XML backup missing' }
  Register-ScheduledTask -TaskName $TaskName -Xml (Get-Content -Raw -Encoding UTF8 $priorTaskXml) -Force | Out-Null
}

$r36XmlAfter = Export-ScheduledTask -TaskName $R36TaskName
if ($r36XmlBefore -ne $r36XmlAfter) { throw 'R36 Scheduled Task changed during R39.3.3 rollback' }

$rollbackReceipt = [ordered]@{
  schema_version = 1
  status = 'PASS'
  rolled_back_at_utc = [DateTime]::UtcNow.ToString('o')
  task_name = $TaskName
  prior_task_restored = $priorTaskExisted
  backup_root = $backupRoot
  r36_task = $R36TaskName
  r36_task_unchanged = $true
  provider_calls = 0
  execution_effects_performed = 0
  stable_roots_modified = $false
  can_trade = $false
  capital_permission = 'DENY'
}
$rollbackPath = Join-Path $InstallBase 'ROLLBACK_R39_3_3_SCHEDULER_RECEIPT.json'
New-Item -ItemType Directory -Force -Path $InstallBase | Out-Null
$rollbackReceipt | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $rollbackPath

Write-Host 'HANRI_R39_3_3_SCHEDULER_ROLLBACK_PASS'
Write-Host "PRIOR_TASK_RESTORED $priorTaskExisted"
Write-Host 'R36_TASK_UNCHANGED true'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "RECEIPT $rollbackPath"
