param(
    [string]$R30TaskName = "ControlCenter-HANRI-R30",
    [string]$R31TaskName = "ControlCenter-HANRI-R31"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR31\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$R30 = Get-ScheduledTask -TaskName $R30TaskName -ErrorAction SilentlyContinue
$R31 = Get-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
if (-not $R30) { throw "Rollback gate: accepted R30 task not found: $R30TaskName" }

if ($R31) {
    Disable-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
}
Enable-ScheduledTask -TaskName $R30TaskName | Out-Null
Start-ScheduledTask -TaskName $R30TaskName

$Receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    restored_at_utc = [DateTime]::UtcNow.ToString("o")
    restored_task = $R30TaskName
    disabled_task = if ($R31) { $R31TaskName } else { $null }
    r30_files_deleted = $false
    r30_state_deleted = $false
    r31_files_deleted = $false
    r31_state_deleted = $false
    self_application = $false
    can_trade = $false
}
$Path = Join-Path $ReceiptRoot "ROLLBACK_R31_TO_R30_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $Path
$Receipt | ConvertTo-Json -Depth 8
