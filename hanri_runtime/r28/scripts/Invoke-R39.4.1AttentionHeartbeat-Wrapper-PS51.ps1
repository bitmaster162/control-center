param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$coreHeartbeat = Join-Path $runtime 'scripts\Invoke-R39.3.3AttentionHeartbeat-Core-PS51.ps1'
$outcomeRunner = Join-Path $runtime 'scripts\Run-R39.4.1OutcomeIntelligenceLive-PS51.ps1'
$heartbeatReceipt = Join-Path $OutputRoot 'heartbeat_receipts\R39_3_3_HEARTBEAT_RECEIPT.json'
$outcomeRoot = Join-Path $OutputRoot 'outcome_intelligence_v1'
$outcomeReceipt = Join-Path $outcomeRoot 'R39_4_0_1_OUTCOME_INTELLIGENCE_RECEIPT.json'
$integrationReceipt = Join-Path $OutputRoot 'heartbeat_receipts\R39_4_1_OUTCOME_INTEGRATION_RECEIPT.json'
$pendingPath = Join-Path $OutputRoot 'R39_4_1_OUTCOME_PENDING.json'

foreach ($required in @($coreHeartbeat, $outcomeRunner)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "R39.4.1 required script missing: $required" }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $integrationReceipt) | Out-Null

function Get-FileSha([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-IntegrationReceipt {
  param(
    [string]$Status,
    [bool]$OutcomeExecuted,
    [string]$ErrorText
  )

  $core = $null
  if (Test-Path -LiteralPath $heartbeatReceipt -PathType Leaf) {
    $core = Get-Content -Raw -Encoding UTF8 $heartbeatReceipt | ConvertFrom-Json
  }
  $outcome = $null
  if (Test-Path -LiteralPath $outcomeReceipt -PathType Leaf) {
    $outcome = Get-Content -Raw -Encoding UTF8 $outcomeReceipt | ConvertFrom-Json
  }

  $coverageDisplay = $null
  if ($outcome) {
    if ($null -eq $outcome.metrics.outcome_coverage_rate) { $coverageDisplay = 'N/A' }
    else { $coverageDisplay = [string]$outcome.metrics.outcome_coverage_rate }
  }

  $obj = [ordered]@{
    schema_version = 1
    policy_version = '39.4.1-live-heartbeat-integration-v1'
    generated_at = [DateTime]::UtcNow.ToString('o')
    status = $Status
    core_heartbeat_action = if ($core) { [string]$core.action } else { $null }
    full_loop_executed = if ($core) { [bool]$core.full_loop_executed } else { $false }
    outcome_executed = $OutcomeExecuted
    outcome_pending = (Test-Path -LiteralPath $pendingPath -PathType Leaf)
    source_semantic_cycle = if ($outcome) { [int]$outcome.source_semantic_cycle } else { $null }
    outcome_coverage_status = if ($outcome) { [string]$outcome.metrics.outcome_coverage_status } else { $null }
    outcome_coverage_rate = if ($outcome) { $outcome.metrics.outcome_coverage_rate } else { $null }
    outcome_coverage_display = $coverageDisplay
    learning_candidate_count = if ($outcome) { [int]$outcome.learning_candidate_count } else { $null }
    next_attention_mode = if ($outcome) { [string]$outcome.next_attention.mode } else { $null }
    core_heartbeat_receipt_sha256 = Get-FileSha $heartbeatReceipt
    outcome_receipt_sha256 = Get-FileSha $outcomeReceipt
    error = if ($ErrorText) { $ErrorText } else { $null }
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
  $obj | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $integrationReceipt
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $coreHeartbeat -OutputRoot $OutputRoot
if ($LASTEXITCODE -ne 0) {
  Write-IntegrationReceipt -Status 'CORE_HEARTBEAT_FAILED' -OutcomeExecuted $false -ErrorText "core heartbeat failed exit=$LASTEXITCODE"
  exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath $heartbeatReceipt -PathType Leaf)) {
  Write-IntegrationReceipt -Status 'CORE_HEARTBEAT_RECEIPT_MISSING' -OutcomeExecuted $false -ErrorText 'core heartbeat receipt missing'
  exit 1
}

$core = Get-Content -Raw -Encoding UTF8 $heartbeatReceipt | ConvertFrom-Json
$needOutcome = [bool]$core.full_loop_executed -or (Test-Path -LiteralPath $pendingPath -PathType Leaf)
$outcomeExecuted = $false

if ($needOutcome) {
  try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $outcomeRunner -LiveRoot $OutputRoot -OutcomeRoot $outcomeRoot
    if ($LASTEXITCODE -ne 0) { throw "outcome sidecar failed exit=$LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $outcomeReceipt -PathType Leaf)) { throw 'outcome receipt missing after sidecar' }

    $outcome = Get-Content -Raw -Encoding UTF8 $outcomeReceipt | ConvertFrom-Json
    if ($outcome.policy_version -ne '39.4.0.1-outcome-intelligence-metric-semantics-v1') { throw 'outcome receipt policy mismatch' }
    if ([int]$outcome.execution_effects_performed -ne 0) { throw 'outcome receipt effects nonzero' }

    if (Test-Path -LiteralPath $pendingPath -PathType Leaf) { Remove-Item -Force -LiteralPath $pendingPath }
    $outcomeExecuted = $true
  }
  catch {
    [ordered]@{
      schema_version = 1
      policy_version = '39.4.1-live-heartbeat-integration-v1'
      generated_at = [DateTime]::UtcNow.ToString('o')
      reason = $_.Exception.Message
      core_heartbeat_action = [string]$core.action
      full_loop_executed = [bool]$core.full_loop_executed
      loop_receipt_sha256 = [string]$core.loop_receipt_sha256
      retry_on_next_heartbeat = $true
      provider_calls = 0
      self_apply = $false
      can_trade = $false
      capital_permission = 'DENY'
    } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $pendingPath

    Write-IntegrationReceipt -Status 'OUTCOME_PENDING_RETRY' -OutcomeExecuted $false -ErrorText $_.Exception.Message
    Write-Host 'HANRI_R39_4_1_HEARTBEAT_INTEGRATION_FAIL'
    Write-Host 'OUTCOME_PENDING_RETRY true'
    Write-Host 'PROVIDER_CALLS 0'
    Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
    exit 1
  }
}

Write-IntegrationReceipt -Status 'PASS' -OutcomeExecuted $outcomeExecuted -ErrorText ''

Write-Host 'HANRI_R39_4_1_HEARTBEAT_INTEGRATION_PASS'
Write-Host "CORE_ACTION $($core.action)"
Write-Host "FULL_LOOP_EXECUTED $($core.full_loop_executed)"
Write-Host "OUTCOME_EXECUTED $outcomeExecuted"
Write-Host "OUTCOME_PENDING $((Test-Path -LiteralPath $pendingPath -PathType Leaf))"
if (Test-Path -LiteralPath $outcomeReceipt -PathType Leaf) {
  $outcome = Get-Content -Raw -Encoding UTF8 $outcomeReceipt | ConvertFrom-Json
  $coverageDisplay = if ($null -eq $outcome.metrics.outcome_coverage_rate) { 'N/A' } else { [string]$outcome.metrics.outcome_coverage_rate }
  Write-Host "OUTCOME_COVERAGE_STATUS $($outcome.metrics.outcome_coverage_status)"
  Write-Host "OUTCOME_COVERAGE_RATE $coverageDisplay"
  Write-Host "LEARNING_CANDIDATES $($outcome.learning_candidate_count)"
  Write-Host "OUTCOME_NEXT_ATTENTION_MODE $($outcome.next_attention.mode)"
}
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SELF_APPLY false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "RECEIPT $integrationReceipt"
