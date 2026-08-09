param(
    [string]$R29TaskName = "ControlCenter-HANRI-R29-RC2",
    [string]$R30TaskName = "ControlCenter-HANRI-R30"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR30\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$R29 = Get-ScheduledTask -TaskName $R29TaskName -ErrorAction SilentlyContinue
$R30 = Get-ScheduledTask -TaskName $R30TaskName -ErrorAction SilentlyContinue
if (-not $R29) { throw "Rollback gate: accepted R29 task not found: $R29TaskName" }

if ($R30) { Disable-ScheduledTask -TaskName $R30TaskName | Out-Null }
Enable-ScheduledTask -TaskName $R29TaskName | Out-Null
Start-ScheduledTask -TaskName $R29TaskName

$Receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    restored_at_utc = [DateTime]::UtcNow.ToString("o")
    restored_task = $R29TaskName
    disabled_task = if ($R30) { $R30TaskName } else { $null }
    r29_files_deleted = $false
    r29_state_deleted = $false
    r30_files_deleted = $false
    r30_state_deleted = $false
    self_application = $false
    can_trade = $false
}
$Path = Join-Path $ReceiptRoot "ROLLBACK_R30_TO_R29_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $Path
$Receipt | ConvertTo-Json -Depth 8
