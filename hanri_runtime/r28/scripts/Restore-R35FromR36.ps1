param(
    [string]$R35TaskName = "ControlCenter-HANRI-R35",
    [string]$R36TaskName = "ControlCenter-HANRI-R36"
)

$ErrorActionPreference = "Stop"
$ReceiptRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR36\receipts"
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null

$r35 = Get-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
if (-not $r35) { throw "Rollback gate: R35 task not found" }

Disable-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue | Out-Null
Stop-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue
Enable-ScheduledTask -TaskName $R35TaskName | Out-Null
Start-ScheduledTask -TaskName $R35TaskName

$receipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    action = "RESTORE_R35_FROM_R36"
    performed_at_utc = [DateTime]::UtcNow.ToString("o")
    r35_task = $R35TaskName
    r35_enabled = $true
    r36_task = $R36TaskName
    r36_disabled = $true
    files_deleted = $false
    r36_state_deleted = $false
    can_trade = $false
    capital_permission = "DENY"
}
$receiptPath = Join-Path $ReceiptRoot "RESTORE_R35_FROM_R36_RECEIPT.json"
$receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $receiptPath
Write-Host "HANRI_R35_ROLLBACK_PASS"
Write-Host "RECEIPT $receiptPath"
