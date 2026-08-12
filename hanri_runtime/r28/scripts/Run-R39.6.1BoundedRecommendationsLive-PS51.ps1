param(
  [string]$LiveRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2",
  [string]$RecommendationRoot = ""
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

if (-not $RecommendationRoot) {
  $RecommendationRoot = Join-Path $LiveRoot 'bounded_recommendations_v1'
}

$learningRoot = Join-Path $LiveRoot 'improvement_learning_v1'
$learningState = Join-Path $learningRoot 'R39_5_IMPROVEMENT_LEARNING_STATE.json'
$learningReceipt = Join-Path $learningRoot 'R39_5_IMPROVEMENT_LEARNING_RECEIPT.json'
$integrationReceipt = Join-Path $LiveRoot 'heartbeat_receipts\R39_5_1_LEARNING_INTEGRATION_RECEIPT.json'
$policy = Join-Path $runtime 'config\r39.6.bounded-improvement-recommendations.json'
$state = Join-Path $RecommendationRoot 'R39_6_BOUNDED_IMPROVEMENT_RECOMMENDATION_STATE.json'
$receipt = Join-Path $RecommendationRoot 'R39_6_BOUNDED_IMPROVEMENT_RECOMMENDATION_RECEIPT.json'

foreach ($required in @($learningState, $learningReceipt, $integrationReceipt, $policy)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "R39.6.1 required input missing: $required"
  }
}
New-Item -ItemType Directory -Force -Path $RecommendationRoot | Out-Null

function Get-RequiredBoundaryProperty {
  param(
    [Parameter(Mandatory=$true)]$Boundary,
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Context
  )

  if ($null -eq $Boundary) { throw "R39.6.1 $Context effect boundary missing" }
  $property = $Boundary.PSObject.Properties[$Name]
  if ($null -eq $property) { throw "R39.6.1 $Context effect boundary missing key: $Name" }
  return $property.Value
}

function Assert-SafeEffectBoundary {
  param(
    [Parameter(Mandatory=$true)]$Boundary,
    [Parameter(Mandatory=$true)][string]$Context,
    [switch]$RequireProposalState
  )

  if ($RequireProposalState) {
    $proposalOnly = Get-RequiredBoundaryProperty -Boundary $Boundary -Name 'proposal_only' -Context $Context
    if (-not [bool]$proposalOnly) { throw "R39.6.1 $Context proposal_only=false" }
    $localState = Get-RequiredBoundaryProperty -Boundary $Boundary -Name 'local_state_write_only' -Context $Context
    if (-not [bool]$localState) { throw "R39.6.1 $Context local_state_write_only=false" }
  }

  foreach ($name in @('provider_calls','scheduler_install','scheduler_modify','human_decision_execution','self_apply','skill_install','system_write','operator_message','auto_dispatch','external_messages','can_trade')) {
    $value = Get-RequiredBoundaryProperty -Boundary $Boundary -Name $name -Context $Context
    if ([bool]$value) { throw "R39.6.1 $Context unsafe effect boundary: $name=true" }
  }
  $capital = Get-RequiredBoundaryProperty -Boundary $Boundary -Name 'capital_permission' -Context $Context
  if ([string]$capital -ne 'DENY') { throw "R39.6.1 $Context capital_permission must remain DENY" }
}

$integration = Get-Content -Raw -Encoding UTF8 $integrationReceipt | ConvertFrom-Json
$lr = Get-Content -Raw -Encoding UTF8 $learningReceipt | ConvertFrom-Json
$ls = Get-Content -Raw -Encoding UTF8 $learningState | ConvertFrom-Json

if ($integration.policy_version -ne '39.5.1-autonomous-learning-integration-v1') { throw 'R39.6.1 upstream integration policy mismatch' }
if ($integration.status -ne 'PASS') { throw 'R39.6.1 upstream integration is not PASS' }
if ([bool]$integration.learning_pending) { throw 'R39.6.1 upstream learning is pending' }
if ([int]$integration.execution_effects_performed -ne 0) { throw 'R39.6.1 upstream integration effects nonzero' }
Assert-SafeEffectBoundary -Boundary $integration.effect_boundary -Context 'upstream integration' -RequireProposalState

if ($lr.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.6.1 learning receipt policy mismatch' }
if ($ls.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.6.1 learning state policy mismatch' }
if ($lr.status -ne 'PASS') { throw 'R39.6.1 learning receipt is not PASS' }
if ($lr.state_sha256 -ne $ls.state_sha256) { throw 'R39.6.1 learning receipt/state SHA binding mismatch' }
if ([int]$lr.source_semantic_cycle -ne [int]$ls.source_semantic_cycle) { throw 'R39.6.1 learning receipt/state semantic cycle mismatch' }
if ([int]$integration.source_semantic_cycle -ne [int]$ls.source_semantic_cycle) { throw 'R39.6.1 integration/learning semantic cycle mismatch' }
if ([int]$lr.execution_effects_performed -ne 0) { throw 'R39.6.1 learning receipt effects nonzero' }
if ([int]$ls.execution_effects_performed -ne 0) { throw 'R39.6.1 learning state effects nonzero' }
Assert-SafeEffectBoundary -Boundary $lr.effect_boundary -Context 'learning receipt' -RequireProposalState
Assert-SafeEffectBoundary -Boundary $ls.effect_boundary -Context 'learning state' -RequireProposalState

$learningReceiptSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $learningReceipt).Hash.ToLowerInvariant()
if ([string]$integration.learning_receipt_sha256 -ne $learningReceiptSha) {
  throw "R39.6.1 upstream learning receipt SHA mismatch expected=$($integration.learning_receipt_sha256) actual=$learningReceiptSha"
}

$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
python -m hanri.bounded_recommendations_cli `
  --learning-state $learningState `
  --policy $policy `
  --state $state `
  --output-receipt $receipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw "R39.6.1 bounded recommendations failed exit=$LASTEXITCODE" }

$r = Get-Content -Raw -Encoding UTF8 $receipt | ConvertFrom-Json
$s = Get-Content -Raw -Encoding UTF8 $state | ConvertFrom-Json
if ($r.policy_version -ne '39.6.0-bounded-improvement-recommendations-v1') { throw 'R39.6.1 recommendation receipt policy mismatch' }
if ($s.policy_version -ne '39.6.0-bounded-improvement-recommendations-v1') { throw 'R39.6.1 recommendation state policy mismatch' }
if ($r.status -ne 'PASS') { throw 'R39.6.1 recommendation receipt not PASS' }
if ($r.state_sha256 -ne $s.state_sha256) { throw 'R39.6.1 recommendation receipt/state SHA binding mismatch' }
if ($s.source_learning_state_sha256 -ne $ls.state_sha256) { throw 'R39.6.1 recommendation source learning state SHA mismatch' }
if ($r.source_learning_state_sha256 -ne $ls.state_sha256) { throw 'R39.6.1 recommendation receipt source learning state SHA mismatch' }
if ($s.source_learning_digest -ne $ls.learning_digest) { throw 'R39.6.1 recommendation source learning digest mismatch' }
if ($r.source_learning_digest -ne $ls.learning_digest) { throw 'R39.6.1 recommendation receipt source learning digest mismatch' }
if ([int]$s.source_semantic_cycle -ne [int]$ls.source_semantic_cycle) { throw 'R39.6.1 recommendation semantic cycle mismatch' }
if ([int]$r.execution_effects_performed -ne 0 -or [int]$s.execution_effects_performed -ne 0) { throw 'R39.6.1 recommendation effects nonzero' }
Assert-SafeEffectBoundary -Boundary $r.effect_boundary -Context 'recommendation receipt' -RequireProposalState
Assert-SafeEffectBoundary -Boundary $s.effect_boundary -Context 'recommendation state' -RequireProposalState

foreach ($packet in @($s.recommendations)) {
  if (-not [bool]$packet.required_human_decision) { throw 'R39.6.1 recommendation human decision not required' }
  if ([string]$packet.review_status -ne 'PENDING_HUMAN_REVIEW') { throw 'R39.6.1 recommendation review status unsafe' }
  if ([string]$packet.authority -ne 'PROPOSAL_ONLY') { throw 'R39.6.1 recommendation authority unsafe' }
  if ([string]$packet.execution_authority -ne 'NONE') { throw 'R39.6.1 recommendation execution authority unsafe' }
  if ([bool]$packet.self_apply_authorized) { throw 'R39.6.1 recommendation self apply authorized' }
  if ([bool]$packet.install_authorized) { throw 'R39.6.1 recommendation install authorized' }
  if ([bool]$packet.system_write_authorized) { throw 'R39.6.1 recommendation system write authorized' }
  if ([bool]$packet.operator_message_authorized) { throw 'R39.6.1 recommendation operator message authorized' }
  if ([bool]$packet.generalization_authorized) { throw 'R39.6.1 recommendation generalization authorized' }
  if ([bool]$packet.causation_claimed) { throw 'R39.6.1 recommendation causation claimed' }
}

$summary = $r.recommendation_summary
Write-Host 'HANRI_R39_6_1_RECOMMENDATION_LIVE_SIDECAR_PASS'
Write-Host "TRANSITION $($r.transition)"
Write-Host "SOURCE_SEMANTIC_CYCLE $($r.source_semantic_cycle)"
Write-Host "RECOMMENDATION_COUNT $($r.recommendation_count)"
Write-Host "RECOMMENDATION_STATUS $($summary.recommendation_status)"
Write-Host "CORRECTIVE_REVIEW_PACKETS $($summary.corrective_review_packets)"
Write-Host "EVIDENCE_COLLECTION_PACKETS $($summary.evidence_collection_packets)"
Write-Host "REINFORCEMENT_REVIEW_PACKETS $($summary.reinforcement_review_packets)"
Write-Host "NEXT_ATTENTION_MODE $($r.next_attention.mode)"
Write-Host 'EXECUTION_AUTHORITY NONE'
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
