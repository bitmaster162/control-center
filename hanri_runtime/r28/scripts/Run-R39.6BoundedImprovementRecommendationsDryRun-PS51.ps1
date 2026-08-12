param(
  [string]$LearningState = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2\improvement_learning_v1\R39_5_IMPROVEMENT_LEARNING_STATE.json",
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\r39_6_shadow"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$policy = Join-Path $runtime 'config\r39.6.bounded-improvement-recommendations.json'
$state = Join-Path $OutputRoot 'R39_6_BOUNDED_IMPROVEMENT_RECOMMENDATION_STATE.json'
$receipt = Join-Path $OutputRoot 'R39_6_BOUNDED_IMPROVEMENT_RECOMMENDATION_RECEIPT.json'

foreach ($required in @($LearningState, $policy)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
    throw "required R39.6 input missing: $required"
  }
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$generatedAt = [DateTime]::UtcNow.ToString('o')

python -m hanri.improvement_recommendations_cli `
  --learning-state $LearningState `
  --policy $policy `
  --state $state `
  --output-receipt $receipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) {
  throw "R39.6 bounded recommendation compiler failed exit=$LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $receipt -PathType Leaf)) {
  throw 'R39.6 receipt missing'
}
$r = Get-Content -Raw -Encoding UTF8 $receipt | ConvertFrom-Json

if ($r.policy_version -ne '39.6.0-bounded-improvement-recommendations-v1') { throw 'R39.6 policy mismatch' }
if ($r.status -ne 'PASS') { throw "R39.6 status=$($r.status)" }
if ([int]$r.execution_effects_performed -ne 0) { throw 'R39.6 execution effects nonzero' }
if (-not [bool]$r.effect_boundary.proposal_only) { throw 'R39.6 proposal_only=false' }
if (-not [bool]$r.effect_boundary.local_state_write_only) { throw 'R39.6 local_state_write_only=false' }
if ([bool]$r.effect_boundary.provider_calls) { throw 'R39.6 provider_calls=true' }
if ([bool]$r.effect_boundary.scheduler_install -or [bool]$r.effect_boundary.scheduler_modify) { throw 'R39.6 scheduler effect true' }
if ([bool]$r.effect_boundary.self_apply) { throw 'R39.6 self_apply=true' }
if ([bool]$r.effect_boundary.skill_install) { throw 'R39.6 skill_install=true' }
if ([bool]$r.effect_boundary.system_write) { throw 'R39.6 system_write=true' }
if ([bool]$r.effect_boundary.operator_message) { throw 'R39.6 operator_message=true' }
if ([bool]$r.effect_boundary.can_trade) { throw 'R39.6 can_trade=true' }
if ($r.effect_boundary.capital_permission -ne 'DENY') { throw 'R39.6 capital_permission not DENY' }

$s = $r.recommendation_summary
Write-Host 'HANRI_R39_6_BOUNDED_RECOMMENDATIONS_DRY_RUN_PASS'
Write-Host "SOURCE_SEMANTIC_CYCLE $($r.source_semantic_cycle)"
Write-Host "TRANSITION $($r.transition)"
Write-Host "RECOMMENDATION_COUNT $($r.recommendation_count)"
Write-Host "RECOMMENDATION_STATUS $($s.recommendation_status)"
Write-Host "CORRECTIVE_REVIEW_PACKETS $($s.corrective_review_packets)"
Write-Host "EVIDENCE_COLLECTION_PACKETS $($s.evidence_collection_packets)"
Write-Host "REINFORCEMENT_REVIEW_PACKETS $($s.reinforcement_review_packets)"
Write-Host "NEXT_ATTENTION_MODE $($r.next_attention.mode)"
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
