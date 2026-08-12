param(
  [switch]$Apply,
  [string]$ApprovalCommand = '',
  [string]$TaskName = 'ControlCenter-HANRI-R39-Attention',
  [string]$InstallRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\host_task\app"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$packageRoot = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_package'
$receiptPath = Join-Path $packageRoot 'receipts\R39_3_3_INSTALL_RECEIPT.json'
$uninstallReceipt = Join-Path $packageRoot 'receipts\R39_3_3_UNINSTALL_RECEIPT.json'
if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) { throw 'install receipt missing' }
$r = Get-Content -Raw -Encoding UTF8 $receiptPath | ConvertFrom-Json
if ($r.status -ne 'PASS') { throw 'install receipt not PASS' }

function Get-TextSha([string]$Text) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return ([System.BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text)))).Replace('-', '').ToLowerInvariant()
  }
  finally { $sha.Dispose() }
}

$current = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$currentXml = if ($current) { Export-ScheduledTask -TaskName $TaskName } else { $null }
$currentSha = if ($currentXml) { Get-TextSha $currentXml } else { $null }
$core = [ordered]@{
  operation = 'uninstall_and_restore_attention_scheduler'
  task_name = $TaskName
  current_task_xml_sha256 = $currentSha
  install_action_hash = [string]$r.action_hash
  install_root = $InstallRoot
  prior_task_xml_backup = $r.prior_task_xml_backup
  prior_app_backup = $r.prior_app_backup
  provider_calls = 0
  can_trade = $false
  capital_permission = 'DENY'
}
$hash = Get-TextSha ($core | ConvertTo-Json -Compress -Depth 8)
$expected = "APPROVE_R39_3_3_UNINSTALL:$hash"

if (-not $Apply) {
  Write-Host 'HANRI_R39_3_3_UNINSTALL_PLAN_PASS'
  Write-Host "CURRENT_TASK_EXISTS $([bool]$current)"
  Write-Host "CURRENT_TASK_SHA256 $currentSha"
  Write-Host "APPROVAL_REQUIRED $expected"
  Write-Host 'UNINSTALL_EFFECTS_PERFORMED 0'
  exit 0
}
if ($ApprovalCommand -ne $expected) { throw 'exact uninstall approval command mismatch' }

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$retired = "$InstallRoot.retired.$stamp"
try {
  if ($current) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
  if (Test-Path -LiteralPath $InstallRoot) { Move-Item -LiteralPath $InstallRoot -Destination $retired }
  $restoredPrior = $false
  if ($r.prior_task_xml_backup -and (Test-Path -LiteralPath ([string]$r.prior_task_xml_backup) -PathType Leaf)) {
    $xml = Get-Content -Raw -Encoding UTF8 ([string]$r.prior_task_xml_backup)
    Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force | Out-Null
    $restoredPrior = $true
  }
  [ordered]@{
    schema_version = 1
    status = 'PASS'
    uninstalled_at_utc = [DateTime]::UtcNow.ToString('o')
    uninstall_action_hash = $hash
    task_name = $TaskName
    retired_install_root = if (Test-Path -LiteralPath $retired) { $retired } else { $null }
    prior_task_restored = $restoredPrior
    provider_calls = 0
    can_trade = $false
    capital_permission = 'DENY'
  } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $uninstallReceipt
  Write-Host 'HANRI_R39_3_3_UNINSTALL_PASS'
  Write-Host "PRIOR_TASK_RESTORED $restoredPrior"
  Write-Host "RETIRED_INSTALL_ROOT $retired"
  Write-Host 'PROVIDER_CALLS 0'
  Write-Host "RECEIPT $uninstallReceipt"
}
catch {
  throw "uninstall_or_restore_failed:$($_.Exception.Message)"
}
