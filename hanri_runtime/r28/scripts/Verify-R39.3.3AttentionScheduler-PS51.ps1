param(
  [string]$TaskName = 'ControlCenter-HANRI-R39-Attention',
  [string]$R36TaskName = 'ControlCenter-HANRI-R36'
)

$ErrorActionPreference = 'Stop'
$InstallBase = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_r39_3_3'
$InstallReceipt = Join-Path $InstallBase 'INSTALL_R39_3_3_SCHEDULER_RECEIPT.json'
$ManifestPath = Join-Path $InstallBase 'INSTALL_MANIFEST.json'
$LiveRoot = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\live_attention_r39_3_3'
$LatestHeartbeat = Join-Path $LiveRoot 'receipts\R39_3_3_LATEST_HEARTBEAT_RECEIPT.json'

function Task-XmlHash([string]$Name) {
  $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if (-not $task) { return $null }
  $xml = Export-ScheduledTask -TaskName $Name
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($xml)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try { return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
  finally { $sha.Dispose() }
}

foreach ($path in @($InstallReceipt, $ManifestPath, $LatestHeartbeat)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "R39.3.3 verification artifact missing: $path" }
}

$install = Get-Content -Raw -Encoding UTF8 $InstallReceipt | ConvertFrom-Json
$manifest = Get-Content -Raw -Encoding UTF8 $ManifestPath | ConvertFrom-Json
$heartbeat = Get-Content -Raw -Encoding UTF8 $LatestHeartbeat | ConvertFrom-Json

if ($install.status -ne 'PASS') { throw 'install receipt status not PASS' }
if (-not $install.scheduler_installed) { throw 'install receipt scheduler_installed=false' }
if ($install.task_name -ne $TaskName) { throw 'install receipt task name mismatch' }
if ([int]$install.heartbeat_minutes -ne 5) { throw 'install receipt heartbeat mismatch' }
if ($manifest.policy_version -ne '39.3.3-host-scheduler-package-v1') { throw 'manifest policy mismatch' }
if ($manifest.source_commit -ne $install.source_commit) { throw 'manifest/install commit mismatch' }
if ($manifest.source_tree -ne $install.source_tree) { throw 'manifest/install tree mismatch' }
if ($heartbeat.status -ne 'PASS') { throw 'latest heartbeat status not PASS' }
if ([int]$heartbeat.execution_effects_performed -ne 0) { throw 'latest heartbeat execution effects nonzero' }
if ($heartbeat.effect_boundary.can_trade) { throw 'latest heartbeat can_trade=true' }
if ($heartbeat.effect_boundary.capital_permission -ne 'DENY') { throw 'latest heartbeat capital permission mismatch' }

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) { throw 'R39.3.3 Scheduled Task missing' }
if ($task.State -eq 'Disabled') { throw 'R39.3.3 Scheduled Task disabled' }
$xml = Export-ScheduledTask -TaskName $TaskName
if ($xml -notmatch '<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>') { throw 'task MultipleInstancesPolicy is not IgnoreNew' }
if ($xml -notmatch '<Interval>PT5M</Interval>') { throw 'task repetition interval is not PT5M' }
if ($xml -notmatch '<ExecutionTimeLimit>PT10M</ExecutionTimeLimit>') { throw 'task execution time limit is not PT10M' }
if ($xml -notmatch [regex]::Escape('Run-R39.3.3AttentionHeartbeat-PS51.ps1')) { throw 'task action does not target R39.3.3 heartbeat runner' }

$r36 = Get-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue
if (-not $r36) { throw 'R36 Scheduled Task missing during R39.3.3 verification' }
if ($r36.State -eq 'Disabled') { throw 'R36 Scheduled Task disabled during R39.3.3 verification' }
$r36Hash = Task-XmlHash $R36TaskName
if ($r36Hash -ne $install.r36_task_xml_sha256_before) { throw 'R36 Scheduled Task XML no longer matches install baseline' }
if ($install.r36_task_xml_sha256_after -ne $install.r36_task_xml_sha256_before) { throw 'install receipt says R36 task changed' }

Write-Host 'HANRI_R39_3_3_SCHEDULER_VERIFY_PASS'
Write-Host "TASK $TaskName"
Write-Host "TASK_STATE $($task.State)"
Write-Host 'HEARTBEAT_MINUTES 5'
Write-Host 'MULTIPLE_INSTANCES IgnoreNew'
Write-Host 'EXECUTION_TIME_LIMIT_MINUTES 10'
Write-Host "LATEST_ACTION $($heartbeat.action)"
Write-Host "LATEST_MODE $($heartbeat.mode)"
Write-Host "COVERAGE_COMPLETE $($heartbeat.coverage_complete)"
Write-Host 'R36_TASK_UNCHANGED true'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "INSTALL_RECEIPT $InstallReceipt"
Write-Host "HEARTBEAT_RECEIPT $LatestHeartbeat"
