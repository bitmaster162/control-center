param(
    [string]$R29RC1TaskName = "ControlCenter-HANRI-R29",
    [string]$R29RC2TaskName = "ControlCenter-HANRI-R29-RC2"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR29RC2\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$RC1 = Get-ScheduledTask -TaskName $R29RC1TaskName -ErrorAction SilentlyContinue
$RC2 = Get-ScheduledTask -TaskName $R29RC2TaskName -ErrorAction SilentlyContinue
if (-not $RC1) { throw "Rollback gate: RC1 task not found: $R29RC1TaskName" }

if ($RC2) { Disable-ScheduledTask -TaskName $R29RC2TaskName | Out-Null }
Enable-ScheduledTask -TaskName $R29RC1TaskName | Out-Null
Start-ScheduledTask -TaskName $R29RC1TaskName

$Receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    restored_at_utc = [DateTime]::UtcNow.ToString("o")
    restored_task = $R29RC1TaskName
    disabled_task = if ($RC2) { $R29RC2TaskName } else { $null }
    rc1_files_deleted = $false
    rc1_state_deleted = $false
    rc2_files_deleted = $false
    rc2_state_deleted = $false
    self_application = $false
    can_trade = $false
}
$Path = Join-Path $ReceiptRoot "ROLLBACK_RC2_TO_RC1_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $Path
$Receipt | ConvertTo-Json -Depth 8
