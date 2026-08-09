param(
    [switch]$Apply,
    [string]$R28TaskName = "ControlCenter-HANRI-R28",
    [string]$R29TaskName = "ControlCenter-HANRI-R29"
)

$ErrorActionPreference = "Stop"
$R29Base = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR29"
$ReceiptRoot = Join-Path $R29Base "receipts"
$InstallReceiptPath = Join-Path $ReceiptRoot "INSTALL_R29_RC1_RECEIPT.json"

Write-Host "HANRI R29 -> R28 rollback gate"
Write-Host "R29 task: $R29TaskName"
Write-Host "R28 task: $R28TaskName"
Write-Host "No files or state will be deleted."

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply to switch scheduler authority back to R28."
    exit 0
}

$R28Task = Get-ScheduledTask -TaskName $R28TaskName -ErrorAction SilentlyContinue
if (-not $R28Task) { throw "Rollback blocked: R28 scheduled task not found" }

$R29Task = Get-ScheduledTask -TaskName $R29TaskName -ErrorAction SilentlyContinue
if ($R29Task) { Disable-ScheduledTask -TaskName $R29TaskName | Out-Null }
Enable-ScheduledTask -TaskName $R28TaskName | Out-Null

Start-ScheduledTask -TaskName $R28TaskName
Start-Sleep -Seconds 2
$R28Info = Get-ScheduledTaskInfo -TaskName $R28TaskName

New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$PriorInstall = $null
if (Test-Path $InstallReceiptPath) {
    $PriorInstall = Get-Content $InstallReceiptPath -Raw | ConvertFrom-Json
}
$Receipt = [ordered]@{
    schema_version = 1
    status = "ROLLBACK_APPLIED"
    rolled_back_at_utc = [DateTime]::UtcNow.ToString("o")
    from = "HANRI_R29_RC1"
    to = "HANRI_R28"
    r29_task_disabled = [bool]$R29Task
    r28_task_enabled = $true
    r28_last_task_result = $R28Info.LastTaskResult
    r29_files_deleted = $false
    r29_state_deleted = $false
    prior_r29_source_commit = if ($PriorInstall) { $PriorInstall.source_commit } else { $null }
    self_application = $false
    can_trade = $false
}
$ReceiptPath = Join-Path $ReceiptRoot "ROLLBACK_R29_TO_R28_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $ReceiptPath
Write-Host "ROLLBACK_APPLIED: R29 disabled; R28 enabled."
Write-Host "Receipt: $ReceiptPath"
