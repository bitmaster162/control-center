param(
    [string]$R32TaskName = "ControlCenter-HANRI-R32",
    [string]$R33TaskName = "ControlCenter-HANRI-R33"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR33\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$R32 = Get-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue
$R33 = Get-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
if (-not $R32) { throw "Rollback gate: accepted R32 task not found: $R32TaskName" }

if ($R33) {
    Disable-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
}
Enable-ScheduledTask -TaskName $R32TaskName | Out-Null
Start-ScheduledTask -TaskName $R32TaskName

$Receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    restored_at_utc = [DateTime]::UtcNow.ToString("o")
    restored_task = $R32TaskName
    disabled_task = if ($R33) { $R33TaskName } else { $null }
    r32_files_deleted = $false
    r32_state_deleted = $false
    r33_files_deleted = $false
    r33_state_deleted = $false
    self_application = $false
    can_trade = $false
}
$Path = Join-Path $ReceiptRoot "ROLLBACK_R33_TO_R32_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $Path
$Receipt | ConvertTo-Json -Depth 8
