param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $runtime)
$env:HANRI_REPO_ROOT = $repoRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$loopRunner = Join-Path $runtime 'scripts\Run-R39.3.3ProductionAttentionLoop-PS51.ps1'
$cadencePolicy = Join-Path $runtime 'config\r39.3.2.attention-cadence.json'
$loopOutput = Join-Path $OutputRoot 'loop'
$loopReceipt = Join-Path $loopOutput 'continuous_receipts_v2\R39_3_1_CONTINUOUS_ATTENTION_LOOP_RECEIPT.json'
$cadenceRoot = Join-Path $OutputRoot 'cadence'
$cadenceState = Join-Path $cadenceRoot 'R39_3_3_CADENCE_STATE.json'
$cadenceReceipt = Join-Path $cadenceRoot 'R39_3_3_CADENCE_RECEIPT.json'
$heartbeatRoot = Join-Path $OutputRoot 'heartbeat_receipts'
$heartbeatReceipt = Join-Path $heartbeatRoot 'R39_3_3_HEARTBEAT_RECEIPT.json'
$leasePath = Join-Path $OutputRoot 'R39_3_3_ATTENTION.lease'
$leaseMinutes = 10

foreach ($path in @($OutputRoot, $cadenceRoot, $heartbeatRoot)) {
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}

function Get-CanonicalFileSha([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-HeartbeatReceipt {
  param(
    [string]$Action,
    [string]$Reason,
    [bool]$FullLoopExecuted,
    [string]$LoopTransition,
    [int]$CadenceIntervalMinutes,
    [string]$NextFullAttentionAt
  )
  $obj = [ordered]@{
    schema_version = 1
    policy_version = '39.3.3-host-heartbeat-v1'
    generated_at = [DateTime]::UtcNow.ToString('o')
    action = $Action
    reason = $Reason
    full_loop_executed = $FullLoopExecuted
    loop_transition = $LoopTransition
    cadence_interval_minutes = $CadenceIntervalMinutes
    next_full_attention_at = $NextFullAttentionAt
    loop_receipt_sha256 = Get-CanonicalFileSha $loopReceipt
    cadence_state_sha256 = Get-CanonicalFileSha $cadenceState
    effect_boundary = [ordered]@{
      scheduler_install = $false
      scheduler_modify = $false
      provider_calls = $false
      human_decision_execution = $false
      self_apply = $false
      skill_install = $false
      system_write = $false
      operator_message = $false
      auto_dispatch = $false
      external_messages = $false
      can_trade = $false
      capital_permission = 'DENY'
    }
    execution_effects_performed = 0
  }
  $obj | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $heartbeatReceipt
}

# Crash-safe local lease. Scheduled Task also uses MultipleInstances=IgnoreNew;
# this lease protects manual/concurrent invocations and is not authority state.
if (Test-Path -LiteralPath $leasePath -PathType Leaf) {
  $age = ((Get-Date).ToUniversalTime() - (Get-Item -LiteralPath $leasePath).LastWriteTimeUtc).TotalMinutes
  if ($age -gt $leaseMinutes) {
    Remove-Item -Force -LiteralPath $leasePath
  }
}

$leaseHandle = $null
try {
  try {
    $leaseHandle = [System.IO.File]::Open($leasePath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $leaseBytes = [System.Text.Encoding]::UTF8.GetBytes("pid=$PID`nutc=$([DateTime]::UtcNow.ToString('o'))`n")
    $leaseHandle.Write($leaseBytes, 0, $leaseBytes.Length)
    $leaseHandle.Flush()
  }
  catch [System.IO.IOException] {
    Write-HeartbeatReceipt -Action 'SKIP_OVERLAP' -Reason 'active local attention lease' -FullLoopExecuted $false -LoopTransition '' -CadenceIntervalMinutes 0 -NextFullAttentionAt ''
    Write-Host 'HANRI_R39_3_3_HEARTBEAT_PASS'
    Write-Host 'ACTION SKIP_OVERLAP'
    Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
    exit 0
  }

  if ((Test-Path -LiteralPath $cadenceState -PathType Leaf) -and -not (Test-Path -LiteralPath $loopReceipt -PathType Leaf)) {
    throw 'cadence_state_exists_but_loop_receipt_missing'
  }

  $now = (Get-Date).ToUniversalTime()
  $runFull = $false
  if (-not (Test-Path -LiteralPath $cadenceState -PathType Leaf)) {
    $runFull = $true
  }
  else {
    $prior = Get-Content -Raw -Encoding UTF8 $cadenceState | ConvertFrom-Json
    if ($prior.policy_version -ne '39.3.2-attention-cadence-v1') { throw 'cadence_state_policy_mismatch' }
    $dueText = [string]$prior.next_full_attention_at
    if (-not $dueText) { $runFull = $true }
    else { $runFull = $now -ge ([DateTimeOffset]::Parse($dueText).UtcDateTime) }
  }

  $fullLoopExecuted = $false
  if ($runFull) {
    # Transaction rule: full loop MUST succeed before cadence state records RUN_FULL_ATTENTION.
    & powershell -NoProfile -ExecutionPolicy Bypass -File $loopRunner -OutputRoot $loopOutput
    if ($LASTEXITCODE -ne 0) { throw "full_attention_loop_failed exit=$LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $loopReceipt -PathType Leaf)) { throw 'full_attention_loop_receipt_missing' }
    $fullLoopExecuted = $true
  }
  elseif (-not (Test-Path -LiteralPath $loopReceipt -PathType Leaf)) {
    throw 'loop_receipt_missing_for_not_due_heartbeat'
  }

  $nowText = $now.ToString('yyyy-MM-ddTHH:mm:ssZ')
  python -m hanri.attention_cadence_cli --loop-receipt $loopReceipt --policy $cadencePolicy --state $cadenceState --output-receipt $cadenceReceipt --now $nowText | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "cadence_commit_failed exit=$LASTEXITCODE" }

  $cadence = Get-Content -Raw -Encoding UTF8 $cadenceReceipt | ConvertFrom-Json
  $loop = Get-Content -Raw -Encoding UTF8 $loopReceipt | ConvertFrom-Json

  if ($runFull -and $cadence.action -ne 'RUN_FULL_ATTENTION') { throw "cadence_commit_not_full_run:$($cadence.action)" }
  if (-not $runFull -and $cadence.action -ne 'SKIP_NOT_DUE') { throw "cadence_commit_not_skip:$($cadence.action)" }
  if ($cadence.effect_boundary.scheduler_install -or $cadence.effect_boundary.scheduler_modify) { throw 'cadence_scheduler_effect_true' }
  if ($cadence.effect_boundary.provider_calls) { throw 'cadence_provider_calls_true' }
  if ($cadence.effect_boundary.can_trade) { throw 'cadence_can_trade_true' }
  if ($cadence.effect_boundary.capital_permission -ne 'DENY') { throw 'cadence_capital_permission_not_DENY' }

  Write-HeartbeatReceipt -Action ([string]$cadence.action) -Reason ([string]$cadence.reason) -FullLoopExecuted $fullLoopExecuted -LoopTransition ([string]$loop.transition) -CadenceIntervalMinutes ([int]$cadence.interval_minutes) -NextFullAttentionAt ([string]$cadence.next_full_attention_at)

  Write-Host 'HANRI_R39_3_3_HEARTBEAT_PASS'
  Write-Host "ACTION $($cadence.action)"
  Write-Host "FULL_LOOP_EXECUTED $fullLoopExecuted"
  Write-Host "LOOP_TRANSITION $($loop.transition)"
  Write-Host "INTERVAL_MINUTES $($cadence.interval_minutes)"
  Write-Host "NEXT_FULL_ATTENTION_AT $($cadence.next_full_attention_at)"
  Write-Host 'PROVIDER_CALLS 0'
  Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
  Write-Host "RECEIPT $heartbeatReceipt"
}
finally {
  if ($leaseHandle) { $leaseHandle.Dispose() }
  if (Test-Path -LiteralPath $leasePath -PathType Leaf) { Remove-Item -Force -LiteralPath $leasePath -ErrorAction SilentlyContinue }
}
