param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$upstreamWrapper = Join-Path $runtime 'scripts\Invoke-R39.5.1AttentionHeartbeat-Core-PS51.ps1'
$recommendationRunner = Join-Path $runtime 'scripts\Run-R39.6.1BoundedRecommendationsLive-PS51.ps1'
$upstreamReceipt = Join-Path $OutputRoot 'heartbeat_receipts\R39_5_1_LEARNING_INTEGRATION_RECEIPT.json'
$learningState = Join-Path $OutputRoot 'improvement_learning_v1\R39_5_IMPROVEMENT_LEARNING_STATE.json'
$recommendationRoot = Join-Path $OutputRoot 'bounded_recommendations_v1'
$recommendationReceipt = Join-Path $recommendationRoot 'R39_6_BOUNDED_IMPROVEMENT_RECOMMENDATION_RECEIPT.json'
$integrationReceipt = Join-Path $OutputRoot 'heartbeat_receipts\R39_6_1_RECOMMENDATION_INTEGRATION_RECEIPT.json'
$pendingPath = Join-Path $OutputRoot 'R39_6_1_RECOMMENDATION_PENDING.json'

foreach ($required in @($upstreamWrapper, $recommendationRunner)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "R39.6.1 required script missing: $required"
  }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $integrationReceipt) | Out-Null

function Get-FileSha([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-RecommendationIntegrationReceipt {
  param(
    [string]$Status,
    [bool]$RecommendationExecuted,
    [string]$ErrorText
  )

  $upstream = $null
  if (Test-Path -LiteralPath $upstreamReceipt -PathType Leaf) {
    $upstream = Get-Content -Raw -Encoding UTF8 $upstreamReceipt | ConvertFrom-Json
  }

  $learning = $null
  if (Test-Path -LiteralPath $learningState -PathType Leaf) {
    $learning = Get-Content -Raw -Encoding UTF8 $learningState | ConvertFrom-Json
  }

  $recommendation = $null
  if (Test-Path -LiteralPath $recommendationReceipt -PathType Leaf) {
    $recommendation = Get-Content -Raw -Encoding UTF8 $recommendationReceipt | ConvertFrom-Json
  }

  $summary = if ($recommendation) { $recommendation.recommendation_summary } else { $null }

  [ordered]@{
    schema_version = 1
    policy_version = '39.6.1-autonomous-recommendation-integration-v1'
    generated_at = [DateTime]::UtcNow.ToString('o')
    status = $Status
    upstream_policy_version = if ($upstream) { [string]$upstream.policy_version } else { $null }
    core_heartbeat_action = if ($upstream) { [string]$upstream.core_heartbeat_action } else { $null }
    full_loop_executed = if ($upstream) { [bool]$upstream.full_loop_executed } else { $false }
    outcome_executed = if ($upstream) { [bool]$upstream.outcome_executed } else { $false }
    learning_executed = if ($upstream) { [bool]$upstream.learning_executed } else { $false }
    learning_pending = if ($upstream) { [bool]$upstream.learning_pending } else { $false }
    recommendation_executed = $RecommendationExecuted
    recommendation_pending = (Test-Path -LiteralPath $pendingPath -PathType Leaf)
    source_semantic_cycle = if ($recommendation) { [int]$recommendation.source_semantic_cycle } elseif ($learning) { [int]$learning.source_semantic_cycle } else { $null }
    recommendation_transition = if ($recommendation) { [string]$recommendation.transition } else { $null }
    recommendation_count = if ($recommendation) { [int]$recommendation.recommendation_count } else { $null }
    recommendation_status = if ($summary) { [string]$summary.recommendation_status } else { $null }
    corrective_review_packets = if ($summary) { [int]$summary.corrective_review_packets } else { $null }
    evidence_collection_packets = if ($summary) { [int]$summary.evidence_collection_packets } else { $null }
    reinforcement_review_packets = if ($summary) { [int]$summary.reinforcement_review_packets } else { $null }
    next_attention_mode = if ($recommendation) { [string]$recommendation.next_attention.mode } else { $null }
    upstream_integration_receipt_sha256 = Get-FileSha $upstreamReceipt
    learning_state_sha256 = if ($learning) { [string]$learning.state_sha256 } else { $null }
    recommendation_receipt_sha256 = Get-FileSha $recommendationReceipt
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
  } | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $integrationReceipt
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $upstreamWrapper -OutputRoot $OutputRoot
$upstreamExit = $LASTEXITCODE
if ($upstreamExit -ne 0) {
  Write-RecommendationIntegrationReceipt -Status 'UPSTREAM_R39_5_1_FAILED' -RecommendationExecuted $false -ErrorText "R39.5.1 upstream failed exit=$upstreamExit"
  Write-Host 'HANRI_R39_6_1_HEARTBEAT_INTEGRATION_FAIL'
  Write-Host 'UPSTREAM_R39_5_1_FAILED true'
  Write-Host "RECOMMENDATION_PENDING $((Test-Path -LiteralPath $pendingPath -PathType Leaf))"
  Write-Host 'PROVIDER_CALLS 0'
  Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
  exit $upstreamExit
}

if (-not (Test-Path -LiteralPath $upstreamReceipt -PathType Leaf)) {
  Write-RecommendationIntegrationReceipt -Status 'UPSTREAM_RECEIPT_MISSING' -RecommendationExecuted $false -ErrorText 'R39.5.1 integration receipt missing'
  exit 1
}

$upstream = Get-Content -Raw -Encoding UTF8 $upstreamReceipt | ConvertFrom-Json
if ($upstream.policy_version -ne '39.5.1-autonomous-learning-integration-v1') {
  Write-RecommendationIntegrationReceipt -Status 'UPSTREAM_POLICY_MISMATCH' -RecommendationExecuted $false -ErrorText 'R39.5.1 integration policy mismatch'
  exit 1
}
if ($upstream.status -ne 'PASS') {
  Write-RecommendationIntegrationReceipt -Status 'UPSTREAM_NOT_PASS' -RecommendationExecuted $false -ErrorText "R39.5.1 status=$($upstream.status)"
  exit 1
}
if ([bool]$upstream.learning_pending) {
  Write-RecommendationIntegrationReceipt -Status 'UPSTREAM_LEARNING_PENDING' -RecommendationExecuted $false -ErrorText 'R39.5.1 learning pending; stale recommendation compilation denied'
  exit 1
}
if ([int]$upstream.execution_effects_performed -ne 0) {
  Write-RecommendationIntegrationReceipt -Status 'UPSTREAM_EFFECTS_NONZERO' -RecommendationExecuted $false -ErrorText 'R39.5.1 execution effects nonzero'
  exit 1
}
if (-not (Test-Path -LiteralPath $learningState -PathType Leaf)) {
  Write-RecommendationIntegrationReceipt -Status 'LEARNING_STATE_MISSING' -RecommendationExecuted $false -ErrorText 'R39.5 learning state missing'
  exit 1
}

$learning = Get-Content -Raw -Encoding UTF8 $learningState | ConvertFrom-Json
if ($learning.policy_version -ne '39.5.0-improvement-learning-v1') {
  Write-RecommendationIntegrationReceipt -Status 'LEARNING_POLICY_MISMATCH' -RecommendationExecuted $false -ErrorText 'R39.5 learning policy mismatch'
  exit 1
}
if ([int]$learning.execution_effects_performed -ne 0) {
  Write-RecommendationIntegrationReceipt -Status 'LEARNING_EFFECTS_NONZERO' -RecommendationExecuted $false -ErrorText 'R39.5 learning effects nonzero'
  exit 1
}

$recommendationMissing = -not (Test-Path -LiteralPath $recommendationReceipt -PathType Leaf)
$recommendationStale = $false
if (-not $recommendationMissing) {
  try {
    $existing = Get-Content -Raw -Encoding UTF8 $recommendationReceipt | ConvertFrom-Json
    $recommendationStale = (
      $existing.policy_version -ne '39.6.0-bounded-improvement-recommendations-v1' -or
      [string]$existing.source_learning_state_sha256 -ne [string]$learning.state_sha256
    )
  }
  catch {
    $recommendationStale = $true
  }
}

$needRecommendation = [bool]$upstream.learning_executed -or
  (Test-Path -LiteralPath $pendingPath -PathType Leaf) -or
  $recommendationMissing -or
  $recommendationStale

$recommendationExecuted = $false
if ($needRecommendation) {
  try {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $recommendationRunner `
      -LiveRoot $OutputRoot `
      -RecommendationRoot $recommendationRoot
    if ($LASTEXITCODE -ne 0) { throw "R39.6 recommendation sidecar failed exit=$LASTEXITCODE" }
    if (-not (Test-Path -LiteralPath $recommendationReceipt -PathType Leaf)) {
      throw 'R39.6 recommendation receipt missing after sidecar'
    }

    $recommendation = Get-Content -Raw -Encoding UTF8 $recommendationReceipt | ConvertFrom-Json
    if ($recommendation.policy_version -ne '39.6.0-bounded-improvement-recommendations-v1') {
      throw 'R39.6 recommendation receipt policy mismatch'
    }
    if ($recommendation.status -ne 'PASS') { throw "R39.6 recommendation receipt status=$($recommendation.status)" }
    if ([int]$recommendation.execution_effects_performed -ne 0) { throw 'R39.6 recommendation receipt effects nonzero' }
    if ([string]$recommendation.source_learning_state_sha256 -ne [string]$learning.state_sha256) {
      throw 'R39.6 recommendation receipt stale after sidecar'
    }

    if (Test-Path -LiteralPath $pendingPath -PathType Leaf) {
      Remove-Item -Force -LiteralPath $pendingPath
    }
    $recommendationExecuted = $true
  }
  catch {
    [ordered]@{
      schema_version = 1
      policy_version = '39.6.1-autonomous-recommendation-integration-v1'
      generated_at = [DateTime]::UtcNow.ToString('o')
      reason = $_.Exception.Message
      upstream_integration_receipt_sha256 = Get-FileSha $upstreamReceipt
      learning_state_sha256 = [string]$learning.state_sha256
      source_semantic_cycle = [int]$learning.source_semantic_cycle
      retry_on_next_heartbeat = $true
      provider_calls = 0
      self_apply = $false
      skill_install = $false
      system_write = $false
      operator_message = $false
      can_trade = $false
      capital_permission = 'DENY'
    } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $pendingPath

    Write-RecommendationIntegrationReceipt -Status 'RECOMMENDATION_PENDING_RETRY' -RecommendationExecuted $false -ErrorText $_.Exception.Message
    Write-Host 'HANRI_R39_6_1_HEARTBEAT_INTEGRATION_FAIL'
    Write-Host 'RECOMMENDATION_PENDING_RETRY true'
    Write-Host 'PROVIDER_CALLS 0'
    Write-Host 'SELF_APPLY false'
    Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
    exit 1
  }
}

if (-not (Test-Path -LiteralPath $recommendationReceipt -PathType Leaf)) {
  Write-RecommendationIntegrationReceipt -Status 'RECOMMENDATION_RECEIPT_MISSING' -RecommendationExecuted $recommendationExecuted -ErrorText 'R39.6 recommendation receipt missing'
  exit 1
}
$recommendation = Get-Content -Raw -Encoding UTF8 $recommendationReceipt | ConvertFrom-Json
if ($recommendation.policy_version -ne '39.6.0-bounded-improvement-recommendations-v1') {
  Write-RecommendationIntegrationReceipt -Status 'RECOMMENDATION_POLICY_MISMATCH' -RecommendationExecuted $recommendationExecuted -ErrorText 'R39.6 recommendation policy mismatch'
  exit 1
}
if ($recommendation.status -ne 'PASS') {
  Write-RecommendationIntegrationReceipt -Status 'RECOMMENDATION_NOT_PASS' -RecommendationExecuted $recommendationExecuted -ErrorText "R39.6 recommendation status=$($recommendation.status)"
  exit 1
}
if ([string]$recommendation.source_learning_state_sha256 -ne [string]$learning.state_sha256) {
  Write-RecommendationIntegrationReceipt -Status 'RECOMMENDATION_STALE' -RecommendationExecuted $recommendationExecuted -ErrorText 'R39.6 recommendation source learning state SHA mismatch'
  exit 1
}
if ([int]$recommendation.execution_effects_performed -ne 0) {
  Write-RecommendationIntegrationReceipt -Status 'RECOMMENDATION_EFFECTS_NONZERO' -RecommendationExecuted $recommendationExecuted -ErrorText 'R39.6 recommendation execution effects nonzero'
  exit 1
}

Write-RecommendationIntegrationReceipt -Status 'PASS' -RecommendationExecuted $recommendationExecuted -ErrorText ''

$summary = $recommendation.recommendation_summary
Write-Host 'HANRI_R39_6_1_HEARTBEAT_INTEGRATION_PASS'
Write-Host "CORE_ACTION $($upstream.core_heartbeat_action)"
Write-Host "FULL_LOOP_EXECUTED $($upstream.full_loop_executed)"
Write-Host "OUTCOME_EXECUTED $($upstream.outcome_executed)"
Write-Host "LEARNING_EXECUTED $($upstream.learning_executed)"
Write-Host "LEARNING_PENDING $($upstream.learning_pending)"
Write-Host "RECOMMENDATION_EXECUTED $recommendationExecuted"
Write-Host "RECOMMENDATION_PENDING $((Test-Path -LiteralPath $pendingPath -PathType Leaf))"
Write-Host "RECOMMENDATION_TRANSITION $($recommendation.transition)"
Write-Host "SOURCE_SEMANTIC_CYCLE $($recommendation.source_semantic_cycle)"
Write-Host "RECOMMENDATION_COUNT $($recommendation.recommendation_count)"
Write-Host "RECOMMENDATION_STATUS $($summary.recommendation_status)"
Write-Host "RECOMMENDATION_NEXT_ATTENTION_MODE $($recommendation.next_attention.mode)"
Write-Host 'EXECUTION_AUTHORITY NONE'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SELF_APPLY false'
Write-Host 'SKILL_INSTALL false'
Write-Host 'SYSTEM_WRITE false'
Write-Host 'OPERATOR_MESSAGE false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host 'CAN_TRADE false'
Write-Host 'CAPITAL_PERMISSION DENY'
Write-Host "RECEIPT $integrationReceipt"
