param(
    [string]$R33TaskName = "ControlCenter-HANRI-R33",
    [string]$R35TaskName = "ControlCenter-HANRI-R35"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR35\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$R33 = Get-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
$R35 = Get-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
if (-not $R33) { throw "Rollback gate: accepted R33 task not found: $R33TaskName" }

if ($R35) {
    Disable-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
}
Enable-ScheduledTask -TaskName $R33TaskName | Out-Null
Start-ScheduledTask -TaskName $R33TaskName

$Receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    restored_at_utc = [DateTime]::UtcNow.ToString("o")
    restored_task = $R33TaskName
    disabled_task = if ($R35) { $R35TaskName } else { $null }
    r33_files_deleted = $false
    r33_state_deleted = $false
    r35_files_deleted = $false
    r35_state_deleted = $false
    sqlite_state_deleted = $false
    self_application = $false
    can_trade = $false
}
$Path = Join-Path $ReceiptRoot "ROLLBACK_R35_TO_R33_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $Path
$Receipt | ConvertTo-Json -Depth 8
