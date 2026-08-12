param(
  [string]$LiveRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2",
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\improvement_learning_verification\r39_5"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$outcomeState = Join-Path $LiveRoot 'outcome_intelligence_v1\R39_4_0_1_OUTCOME_INTELLIGENCE_STATE.json'
$integrationReceipt = Join-Path $LiveRoot 'heartbeat_receipts\R39_4_1_OUTCOME_INTEGRATION_RECEIPT.json'
$policy = Join-Path $runtime 'config\r39.5.improvement-learning.json'
$state = Join-Path $OutputRoot 'R39_5_IMPROVEMENT_LEARNING_STATE.json'
$receipt = Join-Path $OutputRoot 'R39_5_IMPROVEMENT_LEARNING_RECEIPT.json'

foreach ($required in @($outcomeState, $integrationReceipt, $policy)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "R39.5 required input missing: $required"
  }
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$integration = Get-Content -Raw -Encoding UTF8 $integrationReceipt | ConvertFrom-Json
if ($integration.policy_version -ne '39.4.1-live-heartbeat-integration-v1') { throw 'R39.4.1 integration receipt policy mismatch' }
if ($integration.status -ne 'PASS') { throw 'R39.4.1 integration receipt is not PASS' }
if ($integration.outcome_pending) { throw 'R39.4.1 outcome is pending; R39.5 must not rank stale/incomplete outcome state' }
if ([int]$integration.execution_effects_performed -ne 0) { throw 'R39.4.1 integration receipt effects nonzero' }

$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
python -m hanri.improvement_learning_cli `
  --outcome-state $outcomeState `
  --policy $policy `
  --state $state `
  --output-receipt $receipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw "R39.5 improvement learning failed exit=$LASTEXITCODE" }

$r = Get-Content -Raw -Encoding UTF8 $receipt | ConvertFrom-Json
$s = Get-Content -Raw -Encoding UTF8 $state | ConvertFrom-Json
if ($r.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.5 receipt policy mismatch' }
if ($s.policy_version -ne '39.5.0-improvement-learning-v1') { throw 'R39.5 state policy mismatch' }
if ($r.state_sha256 -ne $s.state_sha256) { throw 'R39.5 receipt/state SHA binding mismatch' }
if ([int]$r.execution_effects_performed -ne 0) { throw 'R39.5 receipt effects nonzero' }
if ([int]$s.execution_effects_performed -ne 0) { throw 'R39.5 state effects nonzero' }

foreach ($boundary in @($r.effect_boundary, $s.effect_boundary)) {
  if (-not $boundary.proposal_only) { throw 'proposal_only=false' }
  if (-not $boundary.local_state_write_only) { throw 'local_state_write_only=false' }
  if ($boundary.provider_calls) { throw 'provider_calls=true' }
  if ($boundary.scheduler_install) { throw 'scheduler_install=true' }
  if ($boundary.scheduler_modify) { throw 'scheduler_modify=true' }
  if ($boundary.human_decision_execution) { throw 'human_decision_execution=true' }
  if ($boundary.self_apply) { throw 'self_apply=true' }
  if ($boundary.skill_install) { throw 'skill_install=true' }
  if ($boundary.system_write) { throw 'system_write=true' }
  if ($boundary.operator_message) { throw 'operator_message=true' }
  if ($boundary.auto_dispatch) { throw 'auto_dispatch=true' }
  if ($boundary.external_messages) { throw 'external_messages=true' }
  if ($boundary.can_trade) { throw 'can_trade=true' }
  if ($boundary.capital_permission -ne 'DENY') { throw 'capital_permission_not_DENY' }
}

$summary = $r.learning_summary
Write-Host 'HANRI_R39_5_IMPROVEMENT_LEARNING_DRY_RUN_PASS'
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
