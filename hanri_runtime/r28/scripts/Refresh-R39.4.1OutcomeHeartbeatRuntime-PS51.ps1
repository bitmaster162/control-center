param(
  [switch]$Apply,
  [string]$ApprovalCommand = '',
  [string]$TaskName = 'ControlCenter-HANRI-R39-Attention',
  [string]$InstallRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\host_task\app",
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $runtime)
$decisionReceipt = Join-Path $repoRoot 'receipts\D1_D5_DECISION_RECEIPT.json'
$packageRoot = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\r39_4_1_runtime_refresh'
$receiptRoot = Join-Path $packageRoot 'receipts'
$backupRoot = Join-Path $packageRoot 'backups'
$planPath = Join-Path $packageRoot 'R39_4_1_RUNTIME_REFRESH_PLAN.json'
$applyReceiptPath = Join-Path $receiptRoot 'R39_4_1_RUNTIME_REFRESH_RECEIPT.json'
$liveLease = Join-Path $OutputRoot 'R39_3_3_ATTENTION.lease'

foreach ($path in @($packageRoot, $receiptRoot, $backupRoot)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
if (-not (Test-Path -LiteralPath $decisionReceipt -PathType Leaf)) { throw 'authoritative human decision receipt missing' }

function Invoke-Git {
  param([Parameter(Mandatory=$true)][string[]]$GitArgs)
  $old = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $out = & git -C $repoRoot @GitArgs 2>&1
    $code = $LASTEXITCODE
  }
  finally { $ErrorActionPreference = $old }
  $text = (($out | ForEach-Object { $_.ToString() }) -join "`n").Trim()
  if ($code -ne 0) { throw "git_failed exit=$code args=$($GitArgs -join ' ') $text" }
  return $text
}

function Get-TextSha([string]$Text) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
  }
  finally { $sha.Dispose() }
}

function Get-TreeManifest([string]$Root) {
  if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    return [ordered]@{ file_count = 0; manifest_sha256 = $null }
  }
  $items = @()
  foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object { $_.Extension -ne '.pyc' -and $_.FullName -notmatch '\\__pycache__\\' }) {
    $rel = $file.FullName.Substring($Root.Length).TrimStart('\')
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    $items += "$rel|$($file.Length)|$hash"
  }
  $lines = @($items | Sort-Object)
  $text = ($lines -join "`n") + "`n"
  return [ordered]@{ file_count = $lines.Count; manifest_sha256 = Get-TextSha $text }
}

function Get-SourceManifest {
  $items = @()
  foreach ($root in @($runtime, $decisionReceipt)) {
    if (Test-Path -LiteralPath $root -PathType Container) {
      $files = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.Extension -ne '.pyc' -and $_.FullName -notmatch '\\__pycache__\\' }
    }
    else { $files = @(Get-Item -LiteralPath $root) }
    foreach ($file in $files) {
      $rel = $file.FullName.Substring($repoRoot.Length).TrimStart('\')
      $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
      $items += "$rel|$($file.Length)|$hash"
    }
  }
  $lines = @($items | Sort-Object)
  return [ordered]@{ file_count = $lines.Count; manifest_sha256 = Get-TextSha (($lines -join "`n") + "`n") }
}

function Get-TaskSnapshot([string]$Name) {
  $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if (-not $task) { return [ordered]@{ exists=$false; xml=$null; xml_sha256=$null; state=$null } }
  $xml = Export-ScheduledTask -TaskName $Name
  return [ordered]@{ exists=$true; xml=$xml; xml_sha256=(Get-TextSha $xml); state=[string]$task.State }
}

function Stage-Runtime([string]$Destination) {
  if (Test-Path -LiteralPath $Destination) { Remove-Item -Recurse -Force -LiteralPath $Destination }
  New-Item -ItemType Directory -Force -Path (Join-Path $Destination 'hanri_runtime') | Out-Null
  Copy-Item -Recurse -Force -LiteralPath $runtime -Destination (Join-Path $Destination 'hanri_runtime\r28')
  New-Item -ItemType Directory -Force -Path (Join-Path $Destination 'receipts') | Out-Null
  Copy-Item -Force -LiteralPath $decisionReceipt -Destination (Join-Path $Destination 'receipts\D1_D5_DECISION_RECEIPT.json')

  $scripts = Join-Path $Destination 'hanri_runtime\r28\scripts'
  $taskPath = Join-Path $scripts 'Invoke-R39.3.3AttentionHeartbeat-PS51.ps1'
  $corePath = Join-Path $scripts 'Invoke-R39.3.3AttentionHeartbeat-Core-PS51.ps1'
  $wrapperPath = Join-Path $scripts 'Invoke-R39.4.1AttentionHeartbeat-Wrapper-PS51.ps1'
  if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) { throw 'staged R39.3.3 heartbeat missing' }
  if (-not (Test-Path -LiteralPath $wrapperPath -PathType Leaf)) { throw 'staged R39.4.1 wrapper missing' }
  Move-Item -Force -LiteralPath $taskPath -Destination $corePath
  Copy-Item -Force -LiteralPath $wrapperPath -Destination $taskPath
}

$status = Invoke-Git -GitArgs @('status','--porcelain')
if ($status) { throw 'source worktree must be clean' }
$head = Invoke-Git -GitArgs @('rev-parse','HEAD')
$tree = Invoke-Git -GitArgs @('show','-s','--format=%T','HEAD')
$sourceManifest = Get-SourceManifest
$beforeTask = Get-TaskSnapshot $TaskName
if (-not $beforeTask.exists) { throw 'target attention task missing' }

[xml]$taskXml = $beforeTask.xml
$taskArgs = [string]$taskXml.Task.Actions.Exec.Arguments
$expectedTaskHeartbeat = Join-Path $InstallRoot 'hanri_runtime\r28\scripts\Invoke-R39.3.3AttentionHeartbeat-PS51.ps1'
if ($taskArgs -notlike "*$expectedTaskHeartbeat*") { throw 'task action path does not target stable heartbeat path' }
if ([string]$taskXml.Task.Settings.MultipleInstancesPolicy -ne 'IgnoreNew') { throw 'task overlap policy is not IgnoreNew' }

$beforeInstalledManifest = Get-TreeManifest $InstallRoot
if (-not $beforeInstalledManifest.manifest_sha256) { throw 'installed runtime root missing or empty' }

$preview = Join-Path $packageRoot 'plan_preview'
Stage-Runtime $preview
$targetManifest = Get-TreeManifest $preview
Remove-Item -Recurse -Force -LiteralPath $preview

$principal = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$planCore = [ordered]@{
  schema_version = 1
  policy_version = '39.4.1-live-heartbeat-integration-v1'
  operation = 'refresh_staged_attention_runtime_without_scheduler_xml_change'
  task_name = $TaskName
  source_head = $head
  source_tree = $tree
  source_manifest_sha256 = $sourceManifest.manifest_sha256
  source_file_count = $sourceManifest.file_count
  before_task_xml_sha256 = $beforeTask.xml_sha256
  before_installed_runtime_manifest_sha256 = $beforeInstalledManifest.manifest_sha256
  target_installed_runtime_manifest_sha256 = $targetManifest.manifest_sha256
  target_installed_runtime_file_count = $targetManifest.file_count
  install_root = $InstallRoot
  output_root = $OutputRoot
  principal = $principal
  stable_task_action_path = $expectedTaskHeartbeat
  heartbeat_minutes = 5
  multiple_instances = 'IgnoreNew'
  live_lease_path = $liveLease
  scheduler_xml_change_authorized = $false
  provider_calls = 0
  can_trade = $false
  capital_permission = 'DENY'
}
$actionHash = Get-TextSha ($planCore | ConvertTo-Json -Compress -Depth 12)
$approvalExpected = "APPROVE_R39_4_1_RUNTIME_REFRESH:$actionHash"

$plan = [ordered]@{}
foreach ($p in $planCore.GetEnumerator()) { $plan[$p.Key] = $p.Value }
$plan['action_hash'] = $actionHash
$plan['approval_command'] = $approvalExpected
$plan['apply_requested'] = [bool]$Apply
$plan['runtime_refresh_effects_performed'] = 0
$plan | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $planPath

if (-not $Apply) {
  Write-Host 'HANRI_R39_4_1_RUNTIME_REFRESH_PLAN_PASS'
  Write-Host "HEAD $head"
  Write-Host "TREE $tree"
  Write-Host "SOURCE_MANIFEST_SHA256 $($sourceManifest.manifest_sha256)"
  Write-Host "BEFORE_TASK_XML_SHA256 $($beforeTask.xml_sha256)"
  Write-Host "BEFORE_RUNTIME_MANIFEST_SHA256 $($beforeInstalledManifest.manifest_sha256)"
  Write-Host "TARGET_RUNTIME_MANIFEST_SHA256 $($targetManifest.manifest_sha256)"
  Write-Host "TARGET_RUNTIME_FILE_COUNT $($targetManifest.file_count)"
  Write-Host 'SCHEDULER_MODIFIED false'
  Write-Host 'RUNTIME_REFRESH_APPLIED false'
  Write-Host "APPROVAL_REQUIRED $approvalExpected"
  Write-Host "PLAN $planPath"
  exit 0
}

if ($ApprovalCommand -ne $approvalExpected) { throw 'exact runtime refresh approval command mismatch' }

$freshTask = Get-TaskSnapshot $TaskName
$freshInstalled = Get-TreeManifest $InstallRoot
$freshSource = Get-SourceManifest
if ($freshTask.xml_sha256 -ne $beforeTask.xml_sha256) { throw 'task XML changed after approval plan' }
if ($freshInstalled.manifest_sha256 -ne $beforeInstalledManifest.manifest_sha256) { throw 'installed runtime changed after approval plan' }
if ($freshSource.manifest_sha256 -ne $sourceManifest.manifest_sha256) { throw 'source manifest changed after approval plan' }
if ((Invoke-Git -GitArgs @('rev-parse','HEAD')) -ne $head) { throw 'source HEAD changed after approval plan' }
if ((Invoke-Git -GitArgs @('show','-s','--format=%T','HEAD')) -ne $tree) { throw 'source tree changed after approval plan' }

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$staging = "$InstallRoot.staging.$stamp"
$backup = "$InstallRoot.backup.$stamp"
$leaseHandle = $null
$rollbackPerformed = $false
$swapStarted = $false

try {
  Stage-Runtime $staging
  $stagedManifest = Get-TreeManifest $staging
  if ($stagedManifest.manifest_sha256 -ne $targetManifest.manifest_sha256) { throw 'staged runtime manifest differs from approved target' }

  $preflightRoot = Join-Path $packageRoot "preflight\$stamp"
  $stagedHeartbeat = Join-Path $staging 'hanri_runtime\r28\scripts\Invoke-R39.3.3AttentionHeartbeat-PS51.ps1'
  & powershell -NoProfile -ExecutionPolicy Bypass -File $stagedHeartbeat -OutputRoot $preflightRoot
  if ($LASTEXITCODE -ne 0) { throw "R39.4.1 staged heartbeat preflight failed exit=$LASTEXITCODE" }

  try {
    $leaseHandle = [System.IO.File]::Open($liveLease, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $leaseBytes = [System.Text.Encoding]::UTF8.GetBytes("runtime_refresh_pid=$PID`nutc=$([DateTime]::UtcNow.ToString('o'))`n")
    $leaseHandle.Write($leaseBytes, 0, $leaseBytes.Length)
    $leaseHandle.Flush()
  }
  catch [System.IO.IOException] {
    throw 'live_attention_lease_busy'
  }

  $swapTask = Get-TaskSnapshot $TaskName
  $swapInstalled = Get-TreeManifest $InstallRoot
  if ($swapTask.xml_sha256 -ne $beforeTask.xml_sha256) { throw 'task XML changed before runtime swap' }
  if ($swapInstalled.manifest_sha256 -ne $beforeInstalledManifest.manifest_sha256) { throw 'installed runtime changed before runtime swap' }

  Move-Item -LiteralPath $InstallRoot -Destination $backup
  $swapStarted = $true
  Move-Item -LiteralPath $staging -Destination $InstallRoot

  $afterInstalled = Get-TreeManifest $InstallRoot
  $afterTask = Get-TaskSnapshot $TaskName
  if ($afterInstalled.manifest_sha256 -ne $targetManifest.manifest_sha256) { throw 'installed runtime manifest readback mismatch' }
  if ($afterTask.xml_sha256 -ne $beforeTask.xml_sha256) { throw 'scheduler XML changed during runtime refresh' }

  [ordered]@{
    schema_version = 1
    policy_version = '39.4.1-live-heartbeat-integration-v1'
    status = 'PASS'
    applied_at_utc = [DateTime]::UtcNow.ToString('o')
    action_hash = $actionHash
    task_name = $TaskName
    source_head = $head
    source_tree = $tree
    source_manifest_sha256 = $sourceManifest.manifest_sha256
    before_task_xml_sha256 = $beforeTask.xml_sha256
    after_task_xml_sha256 = $afterTask.xml_sha256
    before_runtime_manifest_sha256 = $beforeInstalledManifest.manifest_sha256
    after_runtime_manifest_sha256 = $afterInstalled.manifest_sha256
    target_runtime_manifest_sha256 = $targetManifest.manifest_sha256
    prior_runtime_backup = $backup
    preflight_root = $preflightRoot
    live_lease_used = $true
    scheduler_modified = $false
    scheduler_xml_unchanged = $true
    rollback_performed = $false
    provider_calls = 0
    self_apply = $false
    can_trade = $false
    capital_permission = 'DENY'
  } | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $applyReceiptPath

  Write-Host 'HANRI_R39_4_1_RUNTIME_REFRESH_APPLY_PASS'
  Write-Host "HEAD $head"
  Write-Host "TREE $tree"
  Write-Host "ACTION_HASH $actionHash"
  Write-Host "TASK_XML_SHA256 $($afterTask.xml_sha256)"
  Write-Host "RUNTIME_MANIFEST_SHA256 $($afterInstalled.manifest_sha256)"
  Write-Host 'LIVE_LEASE_USED true'
  Write-Host 'SCHEDULER_MODIFIED false'
  Write-Host 'SCHEDULER_XML_UNCHANGED true'
  Write-Host 'ROLLBACK_PERFORMED false'
  Write-Host 'PROVIDER_CALLS 0'
  Write-Host 'CAN_TRADE false'
  Write-Host 'CAPITAL_PERMISSION DENY'
  Write-Host "RECEIPT $applyReceiptPath"
}
catch {
  $err = $_.Exception.Message
  try {
    if ($swapStarted) {
      if (Test-Path -LiteralPath $InstallRoot -PathType Container) {
        Remove-Item -Recurse -Force -LiteralPath $InstallRoot
      }
      if (-not (Test-Path -LiteralPath $backup -PathType Container)) {
        throw 'runtime backup missing during rollback'
      }
      Move-Item -LiteralPath $backup -Destination $InstallRoot
    }
    if (Test-Path -LiteralPath $staging -PathType Container) { Remove-Item -Recurse -Force -LiteralPath $staging }
    $rollbackPerformed = $true
  }
  catch { $err = "$err; rollback_error=$($_.Exception.Message)" }

  [ordered]@{
    schema_version = 1
    policy_version = '39.4.1-live-heartbeat-integration-v1'
    status = 'FAIL'
    action_hash = $actionHash
    error = $err
    rollback_performed = $rollbackPerformed
    scheduler_modified = $false
    provider_calls = 0
    can_trade = $false
    capital_permission = 'DENY'
  } | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $applyReceiptPath
  throw $err
}
finally {
  if ($leaseHandle) { $leaseHandle.Dispose() }
  if (Test-Path -LiteralPath $liveLease -PathType Leaf) {
    try {
      $text = Get-Content -Raw -ErrorAction SilentlyContinue -LiteralPath $liveLease
      if ($text -like "runtime_refresh_pid=$PID*") { Remove-Item -Force -LiteralPath $liveLease -ErrorAction SilentlyContinue }
    } catch {}
  }
}
