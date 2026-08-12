param(
  [string]$LiveRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\continuous_live_v2",
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\outcome_intelligence_v2"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$runtime = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $runtime)
$env:HANRI_REPO_ROOT = $repoRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$policy = Join-Path $runtime 'config\r39.4.0.1.outcome-intelligence.json'
$loopState = Join-Path $LiveRoot 'loop\continuous_state_v2\R39_3_1_CONTINUOUS_ATTENTION_STATE.json'
$producerBundle = Join-Path $LiveRoot 'loop\continuous_work_v2\R39_3_1_PRODUCER_ENVELOPES.json'
$state = Join-Path $OutputRoot 'R39_4_0_1_OUTCOME_INTELLIGENCE_STATE.json'
$receipt = Join-Path $OutputRoot 'R39_4_0_1_OUTCOME_INTELLIGENCE_RECEIPT.json'
$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

foreach ($required in @($policy, $loopState, $producerBundle)) {
  if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "required input missing: $required" }
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

python -m hanri.outcome_intelligence_semantic_cli `
  --loop-state $loopState `
  --producer-bundle $producerBundle `
  --policy $policy `
  --state $state `
  --output-receipt $receipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw "R39.4.0.1 outcome intelligence CLI failed exit=$LASTEXITCODE" }

$r = Get-Content -Raw -Encoding UTF8 $receipt | ConvertFrom-Json
if ($r.policy_version -ne '39.4.0.1-outcome-intelligence-metric-semantics-v1') { throw 'R39.4.0.1 policy_version mismatch' }
if ([int]$r.execution_effects_performed -ne 0) { throw 'R39.4.0.1 execution effects nonzero' }

if ([int]$r.metrics.tracked_recommendations -eq 0) {
  if ($null -ne $r.metrics.outcome_coverage_rate) { throw 'zero tracked recommendations must have null outcome_coverage_rate' }
  if ([bool]$r.metrics.outcome_coverage_applicable) { throw 'zero tracked recommendations must be NOT_APPLICABLE' }
  if ($r.metrics.outcome_coverage_status -ne 'NOT_APPLICABLE') { throw 'zero denominator status mismatch' }
}

$b = $r.effect_boundary
foreach ($name in @('provider_calls','scheduler_install','scheduler_modify','human_decision_execution','self_apply','skill_install','system_write','operator_message','auto_dispatch','external_messages','can_trade')) {
  if ([bool]$b.$name) { throw "R39.4.0.1 unsafe effect boundary: $name=true" }
}
if ($b.capital_permission -ne 'DENY') { throw 'R39.4.0.1 capital_permission must remain DENY' }

$coverageText = if ($null -eq $r.metrics.outcome_coverage_rate) { 'N/A' } else { [string]$r.metrics.outcome_coverage_rate }

Write-Host 'HANRI_R39_4_0_1_OUTCOME_INTELLIGENCE_DRY_RUN_PASS'
Write-Host "SOURCE_SEMANTIC_CYCLE $($r.source_semantic_cycle)"
Write-Host "EXPLICIT_OUTCOMES $($r.explicit_outcome_count)"
Write-Host "TRACKED_RECOMMENDATIONS $($r.metrics.tracked_recommendations)"
Write-Host "EVALUATED_RECOMMENDATIONS $($r.metrics.evaluated_recommendations)"
Write-Host "OUTCOME_COVERAGE_APPLICABLE $($r.metrics.outcome_coverage_applicable)"
Write-Host "OUTCOME_COVERAGE_STATUS $($r.metrics.outcome_coverage_status)"
Write-Host "OUTCOME_COVERAGE_RATE $coverageText"
Write-Host "LEARNING_CANDIDATES $($r.learning_candidate_count)"
Write-Host "NEXT_ATTENTION_MODE $($r.next_attention.mode)"
Write-Host 'SCHEDULER_MODIFIED false'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SELF_APPLY false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "STATE $state"
Write-Host "RECEIPT $receipt"
