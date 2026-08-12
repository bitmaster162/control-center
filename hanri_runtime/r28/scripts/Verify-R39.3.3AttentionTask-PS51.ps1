param(
  [string]$TaskName = 'ControlCenter-HANRI-R39-Attention',
  [string]$InstallRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\host_task\app"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$receipt = Join-Path $env:LOCALAPPDATA 'ControlCenterHANRIR39\scheduler_package\receipts\R39_3_3_INSTALL_RECEIPT.json'
if (-not (Test-Path -LiteralPath $receipt -PathType Leaf)) { throw 'install receipt missing' }
$r = Get-Content -Raw -Encoding UTF8 $receipt | ConvertFrom-Json
if ($r.status -ne 'PASS') { throw 'install receipt not PASS' }
if ($r.task_name -ne $TaskName) { throw 'task name differs from install receipt' }

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$xml = Export-ScheduledTask -TaskName $TaskName
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($xml)
  $xmlHash = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
}
finally { $sha.Dispose() }

if ($xmlHash -ne $r.after_task_xml_sha256) { throw 'task XML hash differs from install readback' }
[xml]$doc = $xml
$exec = [string]$doc.Task.Actions.Exec.Command
$args = [string]$doc.Task.Actions.Exec.Arguments
$multiple = [string]$doc.Task.Settings.MultipleInstancesPolicy
$heartbeat = Join-Path $InstallRoot 'hanri_runtime\r28\scripts\Invoke-R39.3.3AttentionHeartbeat-PS51.ps1'
if ($exec -notmatch '(?i)powershell\.exe$') { throw 'task execute mismatch' }
if ($args -notlike "*$heartbeat*") { throw 'task heartbeat path mismatch' }
if ($multiple -ne 'IgnoreNew') { throw 'task overlap policy mismatch' }
if (-not (Test-Path -LiteralPath $heartbeat -PathType Leaf)) { throw 'installed heartbeat script missing' }

Write-Host 'HANRI_R39_3_3_SCHEDULER_VERIFY_PASS'
Write-Host "TASK $TaskName"
Write-Host "STATE $($task.State)"
Write-Host "TASK_XML_SHA256 $xmlHash"
Write-Host 'MULTIPLE_INSTANCES IgnoreNew'
Write-Host 'HEARTBEAT_MINUTES 5'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
