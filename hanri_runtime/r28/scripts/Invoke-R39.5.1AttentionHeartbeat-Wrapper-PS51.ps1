param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$upstreamWrapper = Join-Path $runtime 'scripts\Invoke-R39.4.1AttentionHeartbeat-Core-PS51.ps1'
$learningRunner = Join-Path $runtime 'scripts\Run-R39.5.1ImprovementLearningLive-PS51.ps1'
$upstreamReceipt = Join-Path $OutputRoot 'heartbeat_receipts\R39_4_1_OUTCOME_INTEGRATION_RECEIPT.json'
$learningRoot = Join-Path $OutputRoot 'improvement_learning_v1'
$learningReceipt = Join-Path $learningRoot 'R39_5_IMPROVEMENT_LEARNING_RECEIPT.json'
$integrationReceipt = Join-Path $OutputRoot 'heartbeat_receipts\R39_5_1_LEARNING_INTEGRATION_RECEIPT.json'
$pendingPath = Join-Path $OutputRoot 'R39_5_1_LEARNING_PENDING.json'

foreach ($required in @($upstreamWrapper, $learningRunner)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "R39.5.1 required script missing: $required"
  }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $integrationReceipt) | Out-Null

function Get-FileSha([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-LearningIntegrationReceipt {
  param(
    [string]$Status,
    [bool]$LearningExecuted,
    [string]$ErrorText
  )

  $upstream = $null
  if (Test-Path -LiteralPath $upstreamReceipt -PathType Leaf) {
    $upstream = Get-Content -Raw -Encoding UTF8 $upstreamReceipt | ConvertFrom-Json
  }

  $learning = $null
  if (Test-Path -LiteralPath $learningReceipt -PathType Leaf) {
    $learning = Get-Content -Raw -Encoding UTF8 $learningReceipt | ConvertFrom-Json
  }

  $summary = if ($learning) { $learning.learning_summary } else { $null }

  $obj = [ordered]@{
    schema_version = 1
    policy_version = '39.5.1-autonomous-learning-integration-v1'
    generated_at = [DateTime]::UtcNow.ToString('o')
    status = $Status
    upstream_policy_version = if ($upstream) { [string]$upstream.policy_version } else { $null }
    core_heartbeat_action = if ($upstream) { [string]$upstream.core_heartbeat_action } else { $null }
    full_loop_executed = if ($upstream) { [bool]$upstream.full_loop_executed } else { $false }
    outcome_executed = if ($upstream) { [bool]$upstream.outcome_executed } else { $false }
    outcome_pending = if ($upstream) { [bool]$upstream.outcome_pending } else { $false }
    learning_executed = $LearningExecuted
    learning_pending = (Test-Path -LiteralPath $pendingPath -PathType Leaf)
    source_semantic_cycle = if ($learning) { [int]$learning.source_semantic_cycle } elseif ($upstream -and $null -ne $upstream.source_semantic_cycle) { [int]$upstream.source_semantic_cycle } else { $null }
    learning_transition = if ($learning) { [string]$learning.transition } else { $null }
    tracked_recommendations = if ($summary) { [int]$summary.tracked_recommendations } else { $null }
    evaluated_recommendations = if ($summary) { [int]$summary.evaluated_recommendations } else { $null }
    ranked_improvement_count = if ($learning) { [int]$learning.ranked_improvement_count } else { $null }
    corrective_review_items = if ($summary) { [int]$summary.corrective_review_items } else { $null }
    reinforcement_review_items = if ($summary) { [int]$summary.reinforcement_review_items } else { $null }
    evidence_debt_items = if ($summary) { [int]$summary.evidence_debt_items } else { $null }
    evidence_status = if ($summary) { [string]$summary.evidence_status } else { $null }
    next_attention_mode = if ($learning) { [string]$learning.next_attention.mode } else { $null }
    upstream_integration_receipt_sha256 = Get-FileSha $upstreamReceipt
    learning_receipt_sha256 = Get-FileSha $learningReceipt
    error = if ($ErrorText) { $ErrorText } else { $null }
    effect_boundary = [ordered]@{
      proposal_only = $true
      local_state_write_only = $true
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

& powershell -NoProfile -ExecutionPolicy Bypass -File $upstreamWrapper -OutputRoot $OutputRoot
$upstreamExit = $LASTEXITCODE
if ($upstreamExit -ne 0) {
  Write-LearningIntegrationReceipt -Status 'UPSTREAM_R39_4_1_FAILED' -LearningExecuted $false -ErrorText "R39.4.1 upstream failed exit=$upstreamExit"
  Write-Host 'HANRI_R39_5_1_HEARTBEAT_INTEGRATION_FAIL'
  Write-Host 'UPSTREAM_R39_4_1_FAILED true'
  Write-Host "LEARNING_PENDING $((Test-Path -LiteralPath $pendingPath -PathType Leaf))"
  Write-Host 'PROVIDER_CALLS 0'
  Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
  exit $upstreamExit
}

if (-not (Test-Path -LiteralPath $upstreamReceipt -PathType Leaf)) {
  Write-LearningIntegrationReceipt -Status 'UPSTREAM_RECEIPT_MISSING' -LearningExecuted $false -ErrorText 'R39.4.1 integration receipt missing'
  exit 1
}

$upstream = Get-Content -Raw -Encoding UTF8 $upstreamReceipt | ConvertFrom-Json
if ($upstream.policy_version -ne '39.4.1-live-heartbeat-integration-v1') {
  Write-LearningIntegrationReceipt -Status 'UPSTREAM_POLICY_MISMATCH' -LearningExecuted $false -ErrorText 'R39.4.1 integration policy mismatch'
  exit 1
}
if ($upstream.status -ne 'PASS') {
  Write-LearningIntegrationReceipt -Status 'UPSTREAM_NOT_PASS' -LearningExecuted $false -ErrorText "R39.4.1 status=$($upstream.status)"
  exit 1
}
if ([bool]$upstream.outcome_pending) {
  Write-LearningIntegrationReceipt -Status 'UPSTREAM_OUTCOME_PENDING' -LearningExecuted $false -ErrorText 'R39.4.1 outcome pending; stale outcome ranking denied'
  exit 1
}
if ([int]$upstream.execution_effects_performed -ne 0) {
  Write-LearningIntegrationReceipt -Status 'UPSTREAM_EFFECTS_NONZERO' -LearningExecuted $false -ErrorText 'R39.4.1 execution effects nonzero'
  exit 1
}

$learningMissing = -not (Test-Path -LiteralPath $learningReceipt -PathType Leaf)
$needLearning = [bool]$upstream.outcome_executed -or (Test-Path -LiteralPath $pendingPath -PathType Leaf) -or $learningMissing
$learningExecuted = $false

if ($needLearning) {
  try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $learningRunner -LiveRoot $OutputRoot -LearningRoot $learningRoot
    if ($LASTEXITCODE -ne 0) { throw "R39.5 learning sidecar failed exit=$LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $learningReceipt -PathType Leaf)) { throw 'R39.5 learning receipt missing after sidecar' }

    $learning = Get-Content -Raw -Encoding UTF8 $learningReceipt | ConvertFrom-Json
    if ($learning.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.5 learning receipt policy mismatch' }
    if ($learning.status -ne 'PASS') { throw "R39.5 learning receipt status=$($learning.status)" }
    if ([int]$learning.execution_effects_performed -ne 0) { throw 'R39.5 learning receipt effects nonzero' }

    if (Test-Path -LiteralPath $pendingPath -PathType Leaf) { Remove-Item -Force -LiteralPath $pendingPath }
    $learningExecuted = $true
  }
  catch {
    [ordered]@{
      schema_version = 1
      policy_version = '39.5.1-autonomous-learning-integration-v1'
      generated_at = [DateTime]::UtcNow.ToString('o')
      reason = $_.Exception.Message
      upstream_integration_receipt_sha256 = Get-FileSha $upstreamReceipt
      source_semantic_cycle = if ($null -ne $upstream.source_semantic_cycle) { [int]$upstream.source_semantic_cycle } else { $null }
      retry_on_next_heartbeat = $true
      provider_calls = 0
      self_apply = $false
      skill_install = $false
      system_write = $false
      operator_message = $false
      can_trade = $false
      capital_permission = 'DENY'
    } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $pendingPath

    Write-LearningIntegrationReceipt -Status 'LEARNING_PENDING_RETRY' -LearningExecuted $false -ErrorText $_.Exception.Message
    Write-Host 'HANRI_R39_5_1_HEARTBEAT_INTEGRATION_FAIL'
    Write-Host 'LEARNING_PENDING_RETRY true'
    Write-Host 'PROVIDER_CALLS 0'
    Write-Host 'SELF_APPLY false'
    Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
    exit 1
  }
}

Write-LearningIntegrationReceipt -Status 'PASS' -LearningExecuted $learningExecuted -ErrorText ''

Write-Host 'HANRI_R39_5_1_HEARTBEAT_INTEGRATION_PASS'
Write-Host "CORE_ACTION $($upstream.core_heartbeat_action)"
Write-Host "FULL_LOOP_EXECUTED $($upstream.full_loop_executed)"
Write-Host "OUTCOME_EXECUTED $($upstream.outcome_executed)"
Write-Host "OUTCOME_PENDING $($upstream.outcome_pending)"
Write-Host "LEARNING_EXECUTED $learningExecuted"
Write-Host "LEARNING_PENDING $((Test-Path -LiteralPath $pendingPath -PathType Leaf))"
if (Test-Path -LiteralPath $learningReceipt -PathType Leaf) {
  $learning = Get-Content -Raw -Encoding UTF8 $learningReceipt | ConvertFrom-Json
  $summary = $learning.learning_summary
  Write-Host "LEARNING_TRANSITION $($learning.transition)"
  Write-Host "SOURCE_SEMANTIC_CYCLE $($learning.source_semantic_cycle)"
  Write-Host "RANKED_IMPROVEMENTS $($learning.ranked_improvement_count)"
  Write-Host "EVIDENCE_STATUS $($summary.evidence_status)"
  Write-Host "LEARNING_NEXT_ATTENTION_MODE $($learning.next_attention.mode)"
}
Write-Host 'CAUSATION_CLAIMED false'
Write-Host 'GENERALIZATION_AUTHORIZED false'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SELF_APPLY false'
Write-Host 'SKILL_INSTALL false'
Write-Host 'SYSTEM_WRITE false'
Write-Host 'OPERATOR_MESSAGE false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host 'CAN_TRADE false'
Write-Host 'CAPITAL_PERMISSION DENY'
Write-Host "RECEIPT $integrationReceipt"
