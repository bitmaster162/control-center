param(
    [string]$R31TaskName = "ControlCenter-HANRI-R31",
    [string]$R32TaskName = "ControlCenter-HANRI-R32"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR32\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$R31 = Get-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
$R32 = Get-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue
if (-not $R31) { throw "Rollback gate: accepted R31 task not found: $R31TaskName" }

if ($R32) {
    Disable-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue
}
Enable-ScheduledTask -TaskName $R31TaskName | Out-Null
Start-ScheduledTask -TaskName $R31TaskName

$Receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    restored_at_utc = [DateTime]::UtcNow.ToString("o")
    restored_task = $R31TaskName
    disabled_task = if ($R32) { $R32TaskName } else { $null }
    r31_files_deleted = $false
    r31_state_deleted = $false
    r32_files_deleted = $false
    r32_state_deleted = $false
    self_application = $false
    can_trade = $false
}
$Path = Join-Path $ReceiptRoot "ROLLBACK_R32_TO_R31_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $Path
$Receipt | ConvertTo-Json -Depth 8
