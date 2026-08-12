param(
  [string]$LiveRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2",
  [string]$LearningRoot = ""
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

if (-not $LearningRoot) { $LearningRoot = Join-Path $LiveRoot 'improvement_learning_v1' }

$outcomeState = Join-Path $LiveRoot 'outcome_intelligence_v1\R39_4_0_1_OUTCOME_INTELLIGENCE_STATE.json'
$outcomeReceipt = Join-Path $LiveRoot 'outcome_intelligence_v1\R39_4_0_1_OUTCOME_INTELLIGENCE_RECEIPT.json'
$integrationReceipt = Join-Path $LiveRoot 'heartbeat_receipts\R39_4_1_OUTCOME_INTEGRATION_RECEIPT.json'
$policy = Join-Path $runtime 'config\r39.5.improvement-learning.json'
$state = Join-Path $LearningRoot 'R39_5_IMPROVEMENT_LEARNING_STATE.json'
$receipt = Join-Path $LearningRoot 'R39_5_IMPROVEMENT_LEARNING_RECEIPT.json'

foreach ($required in @($outcomeState, $outcomeReceipt, $integrationReceipt, $policy)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "R39.5.1 required input missing: $required"
  }
}
New-Item -ItemType Directory -Force -Path $LearningRoot | Out-Null

function Get-RequiredBoundaryProperty {
  param(
    [Parameter(Mandatory=$true)]$Boundary,
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Context
  )

  if ($null -eq $Boundary) { throw "R39.5.1 $Context effect boundary missing" }
  $property = $Boundary.PSObject.Properties[$Name]
  if ($null -eq $property) { throw "R39.5.1 $Context effect boundary missing key: $Name" }
  return $property.Value
}

function Assert-SafeEffectBoundary {
  param(
    [Parameter(Mandatory=$true)]$Boundary,
    [Parameter(Mandatory=$true)][string]$Context,
    [switch]$RequireProposalState
  )

  if ($null -eq $Boundary) { throw "R39.5.1 $Context effect boundary missing" }

  if ($RequireProposalState) {
    $proposalOnly = Get-RequiredBoundaryProperty -Boundary $Boundary -Name 'proposal_only' -Context $Context
    if (-not [bool]$proposalOnly) { throw "R39.5.1 $Context proposal_only=false" }

    $localStateWriteOnly = Get-RequiredBoundaryProperty -Boundary $Boundary -Name 'local_state_write_only' -Context $Context
    if (-not [bool]$localStateWriteOnly) { throw "R39.5.1 $Context local_state_write_only=false" }
  }

  foreach ($name in @('provider_calls','scheduler_install','scheduler_modify','human_decision_execution','self_apply','skill_install','system_write','operator_message','auto_dispatch','external_messages','can_trade')) {
    $value = Get-RequiredBoundaryProperty -Boundary $Boundary -Name $name -Context $Context
    if ([bool]$value) { throw "R39.5.1 $Context unsafe effect boundary: $name=true" }
  }

  $capitalPermission = Get-RequiredBoundaryProperty -Boundary $Boundary -Name 'capital_permission' -Context $Context
  if ([string]$capitalPermission -ne 'DENY') { throw "R39.5.1 $Context capital_permission must remain DENY" }
}

$integration = Get-Content -Raw -Encoding UTF8 $integrationReceipt | ConvertFrom-Json
if ($integration.policy_version -ne '39.4.1-live-heartbeat-integration-v1') { throw 'R39.5.1 upstream integration policy mismatch' }
if ($integration.status -ne 'PASS') { throw 'R39.5.1 upstream integration is not PASS' }
if ([bool]$integration.outcome_pending) { throw 'R39.5.1 upstream outcome is pending' }
if ([int]$integration.execution_effects_performed -ne 0) { throw 'R39.5.1 upstream integration effects nonzero' }
Assert-SafeEffectBoundary -Boundary $integration.effect_boundary -Context 'upstream integration'

$outcome = Get-Content -Raw -Encoding UTF8 $outcomeReceipt | ConvertFrom-Json
$outcomeStateObj = Get-Content -Raw -Encoding UTF8 $outcomeState | ConvertFrom-Json
if ($outcome.policy_version -ne '39.4.0.1-outcome-intelligence-metric-semantics-v1') { throw 'R39.5.1 outcome receipt policy mismatch' }
if ($outcomeStateObj.policy_version -ne '39.4.0.1-outcome-intelligence-metric-semantics-v1') { throw 'R39.5.1 outcome state policy mismatch' }
if ([int]$outcome.execution_effects_performed -ne 0) { throw 'R39.5.1 outcome receipt effects nonzero' }
Assert-SafeEffectBoundary -Boundary $outcome.effect_boundary -Context 'outcome receipt' -RequireProposalState
Assert-SafeEffectBoundary -Boundary $outcomeStateObj.effect_boundary -Context 'outcome state' -RequireProposalState

# R39.4.0.1 outcome state safety is contractually represented by effect_boundary.
# A top-level execution_effects_performed counter is optional on state. If present,
# it must still be zero; if absent, StrictMode must not reject an otherwise valid state.
$outcomeStateEffectProperty = $outcomeStateObj.PSObject.Properties['execution_effects_performed']
if ($null -ne $outcomeStateEffectProperty -and [int]$outcomeStateEffectProperty.Value -ne 0) {
  throw 'R39.5.1 outcome state optional effects counter nonzero'
}

if ([int]$integration.source_semantic_cycle -ne [int]$outcome.source_semantic_cycle) { throw 'R39.5.1 integration/outcome semantic cycle mismatch' }
if ([int]$outcome.source_semantic_cycle -ne [int]$outcomeStateObj.source_semantic_cycle) { throw 'R39.5.1 outcome receipt/state semantic cycle mismatch' }

$outcomeReceiptSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $outcomeReceipt).Hash.ToLowerInvariant()
if ([string]$integration.outcome_receipt_sha256 -ne $outcomeReceiptSha) {
  throw "R39.5.1 upstream outcome receipt SHA mismatch expected=$($integration.outcome_receipt_sha256) actual=$outcomeReceiptSha"
}

$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
python -m hanri.improvement_learning_cli `
  --outcome-state $outcomeState `
  --policy $policy `
  --state $state `
  --output-receipt $receipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw "R39.5.1 improvement learning failed exit=$LASTEXITCODE" }

$r = Get-Content -Raw -Encoding UTF8 $receipt | ConvertFrom-Json
$s = Get-Content -Raw -Encoding UTF8 $state | ConvertFrom-Json
if ($r.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.5.1 learning receipt policy mismatch' }
if ($s.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.5.1 learning state policy mismatch' }
if ($r.state_sha256 -ne $s.state_sha256) { throw 'R39.5.1 learning receipt/state SHA binding mismatch' }
if ([int]$r.source_semantic_cycle -ne [int]$outcome.source_semantic_cycle) { throw 'R39.5.1 learning/outcome semantic cycle mismatch' }
if ([int]$r.execution_effects_performed -ne 0) { throw 'R39.5.1 learning receipt effects nonzero' }
if ([int]$s.execution_effects_performed -ne 0) { throw 'R39.5.1 learning state effects nonzero' }

foreach ($boundary in @($r.effect_boundary, $s.effect_boundary)) {
  Assert-SafeEffectBoundary -Boundary $boundary -Context 'learning output' -RequireProposalState
}

$summary = $r.learning_summary
Write-Host 'HANRI_R39_5_1_LEARNING_LIVE_SIDECAR_PASS'
Write-Host "TRANSITION $($r.transition)"
Write-Host "SOURCE_SEMANTIC_CYCLE $($r.source_semantic_cycle)"
Write-Host "TRACKED_RECOMMENDATIONS $($summary.tracked_recommendations)"
Write-Host "EVALUATED_RECOMMENDATIONS $($summary.evaluated_recommendations)"
Write-Host "RANKED_IMPROVEMENTS $($r.ranked_improvement_count)"
Write-Host "CORRECTIVE_REVIEW_ITEMS $($summary.corrective_review_items)"
Write-Host "REINFORCEMENT_REVIEW_ITEMS $($summary.reinforcement_review_items)"
Write-Host "EVIDENCE_DEBT_ITEMS $($summary.evidence_debt_items)"
Write-Host "EVIDENCE_STATUS $($summary.evidence_status)"
Write-Host "NEXT_ATTENTION_MODE $($r.next_attention.mode)"
Write-Host 'CAUSATION_CLAIMED false'
Write-Host 'GENERALIZATION_AUTHORIZED false'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SCHEDULER_MODIFIED false'
Write-Host 'SELF_APPLY false'
Write-Host 'SKILL_INSTALL false'
Write-Host 'SYSTEM_WRITE false'
Write-Host 'OPERATOR_MESSAGE false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host 'CAN_TRADE false'
Write-Host 'CAPITAL_PERMISSION DENY'
Write-Host "STATE $state"
Write-Host "RECEIPT $receipt"
