param(
  [switch]$Apply,
  [string]$ExpectedCommit,
  [string]$ExpectedTree,
  [string]$TaskName = 'ControlCenter-HANRI-R39-Attention',
  [string]$R36TaskName = 'ControlCenter-HANRI-R36'
)

$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$RepoRoot = (& git -C $SourceRoot rev-parse --show-toplevel 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RepoRoot)) { throw 'R39.3.3 gate: git top-level resolution failed' }

$PackagePolicy = Join-Path $SourceRoot 'config\r39.3.3.scheduler-package.json'
$DecisionReceiptSource = Join-Path $RepoRoot 'receipts\D1_D5_DECISION_RECEIPT.json'
$InstallBase = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_r39_3_3'
$InstallRepoRoot = Join-Path $InstallBase 'repo'
$InstallRuntime = Join-Path $InstallRepoRoot 'hanri_runtime\r28'
$LiveRoot = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\live_attention_r39_3_3'
$BackupBase = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_backups'
$InstallReceipt = Join-Path $InstallBase 'INSTALL_R39_3_3_SCHEDULER_RECEIPT.json'

function Git-Value([string[]]$Arguments) {
  $old = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $out = & git -C $RepoRoot @Arguments 2>$null
    $code = $LASTEXITCODE
  }
  finally { $ErrorActionPreference = $old }
  if ($code -ne 0) { throw "git failed: $($Arguments -join ' ')" }
  return ($out | Out-String).Trim()
}

function Task-XmlHash([string]$Name) {
  $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if (-not $task) { return $null }
  $xml = Export-ScheduledTask -TaskName $Name
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($xml)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try { return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
  finally { $sha.Dispose() }
}

function Restore-Prior(
  [string]$BackupRoot,
  [bool]$PriorTaskExisted,
  [string]$PriorTaskXml,
  [bool]$HadInstallRepo,
  [bool]$HadLiveRoot
) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  if ($PriorTaskExisted -and (Test-Path $PriorTaskXml)) {
    Register-ScheduledTask -TaskName $TaskName -Xml (Get-Content -Raw -Encoding UTF8 $PriorTaskXml) -Force | Out-Null
  }
  if (Test-Path $InstallRepoRoot) { Remove-Item -Recurse -Force $InstallRepoRoot }
  if (Test-Path $LiveRoot) { Remove-Item -Recurse -Force $LiveRoot }
  if ($HadInstallRepo -and (Test-Path (Join-Path $BackupRoot 'repo'))) {
    Move-Item -Force (Join-Path $BackupRoot 'repo') $InstallRepoRoot
  }
  if ($HadLiveRoot -and (Test-Path (Join-Path $BackupRoot 'live'))) {
    Move-Item -Force (Join-Path $BackupRoot 'live') $LiveRoot
  }
}

$head = Git-Value @('rev-parse', 'HEAD')
$tree = Git-Value @('rev-parse', 'HEAD^{tree}')
$dirty = Git-Value @('status', '--porcelain')
if ($dirty) { throw 'R39.3.3 gate: worktree must be clean' }
if (-not (Test-Path $PackagePolicy)) { throw 'R39.3.3 package policy missing' }
if (-not (Test-Path $DecisionReceiptSource)) { throw 'R39.3.3 human decision receipt missing' }

$policy = Get-Content -Raw -Encoding UTF8 $PackagePolicy | ConvertFrom-Json
if ($policy.policy_version -ne '39.3.3-host-scheduler-package-v1') { throw 'R39.3.3 package policy mismatch' }
if ($policy.task.name -ne $TaskName) { throw 'R39.3.3 task name mismatch' }
if ([int]$policy.task.heartbeat_minutes -ne 5) { throw 'R39.3.3 heartbeat must be 5 minutes' }
if ($policy.effect_boundary.can_trade) { throw 'R39.3.3 can_trade must remain false' }
if ($policy.effect_boundary.capital_permission -ne 'DENY') { throw 'R39.3.3 capital_permission must remain DENY' }
if ($policy.effect_boundary.r36_task_modify) { throw 'R39.3.3 must not modify R36 task' }

$decision = Get-Content -Raw -Encoding UTF8 $DecisionReceiptSource | ConvertFrom-Json
if ($decision.schema -ne 'control_canter.human_decision_receipt.v1') { throw 'human decision schema mismatch' }
if ($decision.generation -ne 'R64') { throw 'human decision generation mismatch' }
if ([string]::IsNullOrWhiteSpace([string]$decision.decider)) { throw 'human decision decider missing' }
if ($decision.boundaries.can_trade) { throw 'human decision can_trade boundary failed' }
if ($decision.boundaries.capital_permission -ne 'DENY') { throw 'human decision capital boundary failed' }

$r36 = Get-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue
if (-not $r36) { throw 'accepted R36 Scheduled Task is missing' }
if ($r36.State -eq 'Disabled') { throw 'accepted R36 Scheduled Task is disabled' }
$r36HashBefore = Task-XmlHash $R36TaskName

Write-Host 'HANRI R39.3.3 host scheduler package gate'
Write-Host "HEAD $head"
Write-Host "TREE $tree"
Write-Host "TASK $TaskName"
Write-Host 'HEARTBEAT_MINUTES 5'
Write-Host 'MULTIPLE_INSTANCES IgnoreNew'
Write-Host 'EXECUTION_TIME_LIMIT_MINUTES 10'
Write-Host "R36_TASK $R36TaskName"
Write-Host 'R36_MODIFY false'

if (-not $Apply) {
  Write-Host 'DRY_RUN_ONLY true'
  Write-Host 'SCHEDULER_INSTALLED false'
  Write-Host "APPLY_COMMAND .\Install-R39.3.3AttentionScheduler-PS51.ps1 -Apply -ExpectedCommit $head -ExpectedTree $tree"
  exit 0
}

if ([string]::IsNullOrWhiteSpace($ExpectedCommit) -or [string]::IsNullOrWhiteSpace($ExpectedTree)) {
  throw '-ExpectedCommit and -ExpectedTree are required with -Apply'
}
if ($head -ne $ExpectedCommit) { throw "HEAD moved expected=$ExpectedCommit actual=$head" }
if ($tree -ne $ExpectedTree) { throw "TREE moved expected=$ExpectedTree actual=$tree" }

$timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$backupRoot = Join-Path $BackupBase "r39_3_3_$timestamp"
$priorTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$priorTaskExisted = [bool]$priorTask
$priorTaskXml = Join-Path $backupRoot 'previous_task.xml'
$hadInstallRepo = Test-Path $InstallRepoRoot
$hadLiveRoot = Test-Path $LiveRoot

try {
  $oldPy = $env:PYTHONPATH
  try {
    $env:PYTHONPATH = Join-Path $SourceRoot 'src'
    & python -m pytest -q `
      (Join-Path $SourceRoot 'tests\test_r39_3_3_scheduler_package.py') `
      (Join-Path $SourceRoot 'tests\test_r39_3_2_attention_cadence.py') `
      (Join-Path $SourceRoot 'tests\test_r39_3_1_semantic_delta_repair.py')
    if ($LASTEXITCODE -ne 0) { throw 'R39.3.3 install preflight tests failed' }
  }
  finally { $env:PYTHONPATH = $oldPy }

  New-Item -ItemType Directory -Force -Path $backupRoot, $InstallBase | Out-Null
  if ($priorTaskExisted) {
    Export-ScheduledTask -TaskName $TaskName | Set-Content -Encoding UTF8 $priorTaskXml
    Disable-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  }
  if ($hadInstallRepo) { Move-Item -Force $InstallRepoRoot (Join-Path $backupRoot 'repo') }
  if ($hadLiveRoot) { Move-Item -Force $LiveRoot (Join-Path $backupRoot 'live') }

  New-Item -ItemType Directory -Force -Path $InstallRuntime, (Join-Path $InstallRepoRoot 'receipts') | Out-Null
  Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRuntime
  Copy-Item -Force $DecisionReceiptSource (Join-Path $InstallRepoRoot 'receipts\D1_D5_DECISION_RECEIPT.json')

  $decisionSha = (Get-FileHash -Algorithm SHA256 $DecisionReceiptSource).Hash.ToLowerInvariant()
  $installedDecisionSha = (Get-FileHash -Algorithm SHA256 (Join-Path $InstallRepoRoot 'receipts\D1_D5_DECISION_RECEIPT.json')).Hash.ToLowerInvariant()
  if ($decisionSha -ne $installedDecisionSha) { throw 'installed human decision receipt SHA mismatch' }

  $runner = Join-Path $InstallRuntime 'scripts\Run-R39.3.3AttentionHeartbeat-PS51.ps1'
  if (-not (Test-Path $runner)) { throw 'installed heartbeat runner missing' }

  $manifest = [ordered]@{
    schema_version = 1
    policy_version = '39.3.3-host-scheduler-package-v1'
    source_commit = $head
    source_tree = $tree
    installed_at_utc = [DateTime]::UtcNow.ToString('o')
    task_name = $TaskName
    heartbeat_minutes = 5
    multiple_instances = 'IgnoreNew'
    execution_time_limit_minutes = 10
    runner = $runner
    live_root = $LiveRoot
    human_decision_receipt_sha256 = $decisionSha
    r36_task = $R36TaskName
    r36_task_xml_sha256_before = $r36HashBefore
    can_trade = $false
    capital_permission = 'DENY'
  }
  $manifestPath = Join-Path $InstallBase 'INSTALL_MANIFEST.json'
  $manifest | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $manifestPath

  & powershell -NoProfile -ExecutionPolicy Bypass -File $runner -OutputRoot $LiveRoot
  if ($LASTEXITCODE -ne 0) { throw 'R39.3.3 manual preflight heartbeat failed' }
  $latestHeartbeat = Join-Path $LiveRoot 'receipts\R39_3_3_LATEST_HEARTBEAT_RECEIPT.json'
  if (-not (Test-Path $latestHeartbeat)) { throw 'R39.3.3 preflight receipt missing' }
  $preflight = Get-Content -Raw -Encoding UTF8 $latestHeartbeat | ConvertFrom-Json
  if ($preflight.action -ne 'RUN_FULL_ATTENTION') { throw "preflight expected RUN_FULL_ATTENTION actual=$($preflight.action)" }
  if (-not $preflight.coverage_complete) { throw 'preflight coverage incomplete' }
  if ([int]$preflight.execution_effects_performed -ne 0) { throw 'preflight execution effects nonzero' }

  $beforeScheduledWrite = (Get-Item $latestHeartbeat).LastWriteTimeUtc
  $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -OutputRoot `"$LiveRoot`""
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
  $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
  $triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($triggerLogon, $triggerRepeat) -Settings $settings -Description 'HANRI R39 attention-over-attention heartbeat; adaptive 5-60m full scan cadence; proposal-only' -Force | Out-Null
  Enable-ScheduledTask -TaskName $TaskName | Out-Null

  Start-ScheduledTask -TaskName $TaskName
  $deadline = [DateTime]::UtcNow.AddMinutes(2)
  while ([DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Seconds 2
    if ((Get-Item $latestHeartbeat).LastWriteTimeUtc -gt $beforeScheduledWrite -and (Get-ScheduledTask -TaskName $TaskName).State -ne 'Running') { break }
  }
  if ((Get-Item $latestHeartbeat).LastWriteTimeUtc -le $beforeScheduledWrite) { throw 'scheduled heartbeat did not produce fresh receipt' }

  $scheduledReadback = Get-Content -Raw -Encoding UTF8 $latestHeartbeat | ConvertFrom-Json
  if ($scheduledReadback.status -ne 'PASS') { throw 'scheduled heartbeat receipt status not PASS' }
  if ([int]$scheduledReadback.execution_effects_performed -ne 0) { throw 'scheduled heartbeat effects nonzero' }
  if ($scheduledReadback.effect_boundary.can_trade) { throw 'scheduled heartbeat can_trade=true' }
  if ($scheduledReadback.effect_boundary.capital_permission -ne 'DENY') { throw 'scheduled heartbeat capital permission mismatch' }

  $r36HashAfter = Task-XmlHash $R36TaskName
  if ($r36HashAfter -ne $r36HashBefore) { throw 'R36 Scheduled Task XML changed during R39.3.3 install' }

  $receipt = [ordered]@{
    schema_version = 1
    status = 'PASS'
    release = 'HANRI_R39_3_3_ATTENTION_SCHEDULER'
    installed_at_utc = [DateTime]::UtcNow.ToString('o')
    source_commit = $head
    source_tree = $tree
    task_name = $TaskName
    heartbeat_minutes = 5
    multiple_instances = 'IgnoreNew'
    execution_time_limit_minutes = 10
    preflight_action = [string]$preflight.action
    scheduled_readback_action = [string]$scheduledReadback.action
    backup_root = $backupRoot
    prior_task_existed = $priorTaskExisted
    human_decision_receipt_sha256 = $decisionSha
    r36_task = $R36TaskName
    r36_task_xml_sha256_before = $r36HashBefore
    r36_task_xml_sha256_after = $r36HashAfter
    r36_task_unchanged = $true
    scheduler_installed = $true
    provider_calls = 0
    human_decision_execution = $false
    self_apply = $false
    auto_dispatch = $false
    execution_effects_performed = 0
    stable_roots_modified = $false
    can_trade = $false
    capital_permission = 'DENY'
  }
  $receipt | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $InstallReceipt

  Write-Host 'HANRI_R39_3_3_SCHEDULER_INSTALL_PASS'
  Write-Host "HEAD $head"
  Write-Host "TREE $tree"
  Write-Host "TASK $TaskName"
  Write-Host 'HEARTBEAT_MINUTES 5'
  Write-Host "SCHEDULED_READBACK_ACTION $($scheduledReadback.action)"
  Write-Host 'R36_TASK_UNCHANGED true'
  Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
  Write-Host "RECEIPT $InstallReceipt"
}
catch {
  Restore-Prior -BackupRoot $backupRoot -PriorTaskExisted $priorTaskExisted -PriorTaskXml $priorTaskXml -HadInstallRepo $hadInstallRepo -HadLiveRoot $hadLiveRoot
  throw
}
