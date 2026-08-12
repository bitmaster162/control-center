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
$policyPath = Join-Path $runtime 'config\r39.3.3.host-scheduler.json'
$decisionReceipt = Join-Path $repoRoot 'receipts\D1_D5_DECISION_RECEIPT.json'
$packageRoot = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_package'
$backupRoot = Join-Path $packageRoot 'backups'
$receiptRoot = Join-Path $packageRoot 'receipts'
$planPath = Join-Path $packageRoot 'R39_3_3_INSTALL_PLAN.json'
$installReceiptPath = Join-Path $receiptRoot 'R39_3_3_INSTALL_RECEIPT.json'

foreach ($path in @($packageRoot, $backupRoot, $receiptRoot)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }
if (-not (Test-Path -LiteralPath $policyPath -PathType Leaf)) { throw 'scheduler policy missing' }
if (-not (Test-Path -LiteralPath $decisionReceipt -PathType Leaf)) { throw 'authoritative human decision receipt missing' }

$policy = Get-Content -Raw -Encoding UTF8 $policyPath | ConvertFrom-Json
if ($policy.policy_version -ne '39.3.3-host-scheduler-package-v1') { throw 'scheduler policy version mismatch' }
if ([int]$policy.heartbeat_minutes -ne 5) { throw 'scheduler heartbeat must be 5 minutes' }
if ($policy.effect_boundary.install_authorized) { throw 'policy install_authorized must remain false' }

function Invoke-Git {
  param(
    [Parameter(Mandatory=$true)]
    [string[]]$GitArgs
  )

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

function Get-TaskSnapshot([string]$Name) {
  $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if (-not $task) { return [ordered]@{ exists = $false; xml = $null; xml_sha256 = $null; state = $null } }
  $xml = Export-ScheduledTask -TaskName $Name
  return [ordered]@{ exists = $true; xml = $xml; xml_sha256 = Get-TextSha $xml; state = [string]$task.State }
}

function Get-SourceManifest {
  $items = @()
  $roots = @($runtime, $decisionReceipt)
  foreach ($root in $roots) {
    if (Test-Path -LiteralPath $root -PathType Container) {
      $files = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.Extension -ne '.pyc' -and $_.FullName -notmatch '\\__pycache__\\' }
    } else { $files = @(Get-Item -LiteralPath $root) }
    foreach ($file in $files) {
      $rel = $file.FullName.Substring($repoRoot.Length).TrimStart('\')
      $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
      $items += "$rel|$($file.Length)|$hash"
    }
  }
  $lines = @($items | Sort-Object)
  $text = ($lines -join "`n") + "`n"
  return [ordered]@{ file_count = $lines.Count; manifest_sha256 = Get-TextSha $text }
}

$status = Invoke-Git -GitArgs @('status','--porcelain')
if ($status) { throw 'source worktree must be clean' }
$head = Invoke-Git -GitArgs @('rev-parse','HEAD')
$tree = Invoke-Git -GitArgs @('show','-s','--format=%T','HEAD')
$manifest = Get-SourceManifest
$principal = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$before = Get-TaskSnapshot $TaskName

$planCore = [ordered]@{
  schema_version = 1
  policy_version = '39.3.3-host-scheduler-package-v1'
  operation = 'install_or_replace_attention_scheduler'
  task_name = $TaskName
  source_head = $head
  source_tree = $tree
  source_manifest_sha256 = $manifest.manifest_sha256
  source_file_count = $manifest.file_count
  before_task_exists = [bool]$before.exists
  before_task_xml_sha256 = $before.xml_sha256
  install_root = $InstallRoot
  output_root = $OutputRoot
  principal = $principal
  heartbeat_minutes = 5
  multiple_instances = 'IgnoreNew'
  start_when_available = $true
  execution_time_limit_minutes = 10
  dynamic_scheduler_reconfiguration = $false
  provider_calls = 0
  can_trade = $false
  capital_permission = 'DENY'
}
$planJson = $planCore | ConvertTo-Json -Compress -Depth 10
$actionHash = Get-TextSha $planJson
$approvalExpected = "APPROVE_R39_3_3_SCHEDULER:$actionHash"
$plan = [ordered]@{}
foreach ($p in $planCore.GetEnumerator()) { $plan[$p.Key] = $p.Value }
$plan['action_hash'] = $actionHash
$plan['approval_command'] = $approvalExpected
$plan['apply_requested'] = [bool]$Apply
$plan['scheduler_effects_performed'] = 0
$plan | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $planPath

if (-not $Apply) {
  Write-Host 'HANRI_R39_3_3_SCHEDULER_PLAN_PASS'
  Write-Host "HEAD $head"
  Write-Host "TREE $tree"
  Write-Host "SOURCE_MANIFEST_SHA256 $($manifest.manifest_sha256)"
  Write-Host "TASK_NAME $TaskName"
  Write-Host "BEFORE_TASK_EXISTS $($before.exists)"
  Write-Host 'HEARTBEAT_MINUTES 5'
  Write-Host 'MULTIPLE_INSTANCES IgnoreNew'
  Write-Host 'SCHEDULER_INSTALLED false'
  Write-Host 'SCHEDULER_MODIFIED false'
  Write-Host "APPROVAL_REQUIRED $approvalExpected"
  Write-Host "PLAN $planPath"
  exit 0
}

if ($ApprovalCommand -ne $approvalExpected) { throw 'exact scheduler approval command mismatch' }

# Fresh pre-effect checks: task snapshot + git/source manifest must still equal the approved plan.
$freshBefore = Get-TaskSnapshot $TaskName
if ([bool]$freshBefore.exists -ne [bool]$before.exists -or $freshBefore.xml_sha256 -ne $before.xml_sha256) { throw 'task precondition changed after approval plan' }
if ((Invoke-Git -GitArgs @('rev-parse','HEAD')) -ne $head) { throw 'source HEAD changed after approval plan' }
if ((Invoke-Git -GitArgs @('show','-s','--format=%T','HEAD')) -ne $tree) { throw 'source tree changed after approval plan' }
$freshManifest = Get-SourceManifest
if ($freshManifest.manifest_sha256 -ne $manifest.manifest_sha256) { throw 'source manifest changed after approval plan' }

$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$staging = "$InstallRoot.staging.$stamp"
$appBackup = "$InstallRoot.backup.$stamp"
$taskBackup = Join-Path $backupRoot "$TaskName.$stamp.xml"
$rollbackPerformed = $false
$registered = $false

try {
  if (Test-Path -LiteralPath $staging) { Remove-Item -Recurse -Force -LiteralPath $staging }
  New-Item -ItemType Directory -Force -Path (Join-Path $staging 'hanri_runtime') | Out-Null
  Copy-Item -Recurse -Force -LiteralPath $runtime -Destination (Join-Path $staging 'hanri_runtime\r28')
  New-Item -ItemType Directory -Force -Path (Join-Path $staging 'receipts') | Out-Null
  Copy-Item -Force -LiteralPath $decisionReceipt -Destination (Join-Path $staging 'receipts\D1_D5_DECISION_RECEIPT.json')

  $stagedHeartbeat = Join-Path $staging 'hanri_runtime\r28\scripts\Invoke-R39.3.3AttentionHeartbeat-PS51.ps1'
  if (-not (Test-Path -LiteralPath $stagedHeartbeat -PathType Leaf)) { throw 'staged heartbeat missing' }

  # Execute a real local preflight BEFORE touching Scheduled Tasks.
  $preflightRoot = Join-Path $packageRoot "preflight\$stamp"
  & powershell -NoProfile -ExecutionPolicy Bypass -File $stagedHeartbeat -OutputRoot $preflightRoot
  if ($LASTEXITCODE -ne 0) { throw "staged heartbeat preflight failed exit=$LASTEXITCODE" }

  if ($before.exists) { $before.xml | Set-Content -Encoding UTF8 $taskBackup }
  if (Test-Path -LiteralPath $InstallRoot) { Move-Item -LiteralPath $InstallRoot -Destination $appBackup }
  Move-Item -LiteralPath $staging -Destination $InstallRoot

  $installedHeartbeat = Join-Path $InstallRoot 'hanri_runtime\r28\scripts\Invoke-R39.3.3AttentionHeartbeat-PS51.ps1'
  $argument = "-NoProfile -ExecutionPolicy Bypass -File `"$installedHeartbeat`" -OutputRoot `"$OutputRoot`""
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
  $taskPrincipal = New-ScheduledTaskPrincipal -UserId $principal -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $taskPrincipal -Description 'HANRI R39 attention heartbeat; adaptive full scans are decided inside the cadence controller.' -Force | Out-Null
  $registered = $true

  $after = Get-TaskSnapshot $TaskName
  if (-not $after.exists) { throw 'scheduled task missing after register' }
  [xml]$afterXml = $after.xml
  $exec = [string]$afterXml.Task.Actions.Exec.Command
  $args = [string]$afterXml.Task.Actions.Exec.Arguments
  $multiple = [string]$afterXml.Task.Settings.MultipleInstancesPolicy
  if ($exec -notmatch '(?i)powershell\.exe$') { throw 'scheduled task execute mismatch' }
  if ($args -notlike "*$installedHeartbeat*") { throw 'scheduled task action path mismatch' }
  if ($multiple -ne 'IgnoreNew') { throw "scheduled task MultipleInstancesPolicy mismatch:$multiple" }

  $receipt = [ordered]@{
    schema_version = 1
    policy_version = '39.3.3-host-scheduler-package-v1'
    status = 'PASS'
    installed_at_utc = [DateTime]::UtcNow.ToString('o')
    action_hash = $actionHash
    task_name = $TaskName
    source_head = $head
    source_tree = $tree
    source_manifest_sha256 = $manifest.manifest_sha256
    before_task_exists = [bool]$before.exists
    before_task_xml_sha256 = $before.xml_sha256
    after_task_xml_sha256 = $after.xml_sha256
    prior_task_xml_backup = if ($before.exists) { $taskBackup } else { $null }
    prior_app_backup = if (Test-Path -LiteralPath $appBackup) { $appBackup } else { $null }
    install_root = $InstallRoot
    output_root = $OutputRoot
    preflight_root = $preflightRoot
    heartbeat_minutes = 5
    multiple_instances = 'IgnoreNew'
    rollback_performed = $false
    post_write_readback_verified = $true
    provider_calls = 0
    human_decision_execution = $false
    self_apply = $false
    auto_dispatch = $false
    can_trade = $false
    capital_permission = 'DENY'
  }
  $receipt | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $installReceiptPath

  Write-Host 'HANRI_R39_3_3_SCHEDULER_INSTALL_PASS'
  Write-Host "TASK $TaskName"
  Write-Host "HEAD $head"
  Write-Host "TREE $tree"
  Write-Host "ACTION_HASH $actionHash"
  Write-Host "BEFORE_TASK_SHA256 $($before.xml_sha256)"
  Write-Host "AFTER_TASK_SHA256 $($after.xml_sha256)"
  Write-Host 'HEARTBEAT_MINUTES 5'
  Write-Host 'MULTIPLE_INSTANCES IgnoreNew'
  Write-Host 'ROLLBACK_PERFORMED false'
  Write-Host 'PROVIDER_CALLS 0'
  Write-Host "RECEIPT $installReceiptPath"
}
catch {
  $err = $_.Exception.Message
  try {
    if ($registered -or (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
      Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    }
    if ($before.exists -and (Test-Path -LiteralPath $taskBackup -PathType Leaf)) {
      $xml = Get-Content -Raw -Encoding UTF8 $taskBackup
      Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force | Out-Null
    }
    if (Test-Path -LiteralPath $InstallRoot) { Remove-Item -Recurse -Force -LiteralPath $InstallRoot }
    if (Test-Path -LiteralPath $appBackup) { Move-Item -LiteralPath $appBackup -Destination $InstallRoot }
    if (Test-Path -LiteralPath $staging) { Remove-Item -Recurse -Force -LiteralPath $staging }
    $rollbackPerformed = $true
  }
  catch { $err = "$err; rollback_error=$($_.Exception.Message)" }

  [ordered]@{
    schema_version = 1
    policy_version = '39.3.3-host-scheduler-package-v1'
    status = 'FAIL'
    action_hash = $actionHash
    error = $err
    rollback_performed = $rollbackPerformed
    provider_calls = 0
    can_trade = $false
    capital_permission = 'DENY'
  } | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $installReceiptPath
  throw $err
}
