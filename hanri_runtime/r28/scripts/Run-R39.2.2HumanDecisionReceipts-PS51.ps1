param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39"
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $runtime)
$env:HANRI_REPO_ROOT = $repoRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$config = Join-Path $runtime 'config\r39.2.2.human-decision-receipts.json'
$governorPolicy = Join-Path $runtime 'config\r39.attention-governor.json'
$fabricPolicy = Join-Path $runtime 'config\r39.1.attention-fabric.json'
$decisionReceipt = Join-Path $repoRoot 'receipts\D1_D5_DECISION_RECEIPT.json'
$producerDir = Join-Path $OutputRoot 'producer_current'
$receiptDir = Join-Path $OutputRoot 'receipts'
$bundle = Join-Path $producerDir 'R39_2_2_PRODUCER_ENVELOPES.json'
$adapterReceipt = Join-Path $receiptDir 'R39_2_2_HUMAN_DECISION_RECEIPTS_RECEIPT.json'
$fabricReceipt = Join-Path $receiptDir 'R39_2_2_ATTENTION_FABRIC_RECEIPT.json'
$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$runId = 'R39.2.2-HOST-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')

if (-not (Test-Path -LiteralPath $decisionReceipt -PathType Leaf)) {
  throw "authoritative human decision receipt missing: $decisionReceipt"
}

New-Item -ItemType Directory -Force -Path $producerDir | Out-Null
New-Item -ItemType Directory -Force -Path $receiptDir | Out-Null

python -m pytest -q `
  (Join-Path $runtime 'tests\test_r39_2_2_human_decision_receipts.py') `
  (Join-Path $runtime 'tests\test_r39_2_1_attention_coverage_closure.py') `
  (Join-Path $runtime 'tests\test_r39_producer_adapters.py') `
  (Join-Path $runtime 'tests\test_r39_attention_fabric.py') `
  (Join-Path $runtime 'tests\test_r39_attention_governor.py')
if ($LASTEXITCODE -ne 0) { throw "R39.2.2 regression tests failed" }

python -m hanri.producer_adapters_operator_receipts_cli `
  --config $config `
  --output-bundle $bundle `
  --output-receipt $adapterReceipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw "R39.2.2 producer adapter run failed" }

$fabricInput = Join-Path $OutputRoot 'producer_current_r39_2_2'
New-Item -ItemType Directory -Force -Path $fabricInput | Out-Null
Get-ChildItem -LiteralPath $fabricInput -Filter '*.json' -File -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item -LiteralPath $bundle -Destination (Join-Path $fabricInput 'R39_2_2_PRODUCER_ENVELOPES.json') -Force

python -m hanri.attention_fabric_cli `
  --input-dir $fabricInput `
  --governor-policy $governorPolicy `
  --fabric-policy $fabricPolicy `
  --run-id $runId `
  --generated-at $generatedAt `
  --output $fabricReceipt | Out-Null
if ($LASTEXITCODE -ne 0) { throw "R39.2.2 attention fabric run failed" }

$a = Get-Content -Raw -Encoding UTF8 $adapterReceipt | ConvertFrom-Json
$f = Get-Content -Raw -Encoding UTF8 $fabricReceipt | ConvertFrom-Json

if ($a.policy_version -ne '39.2.2-human-decision-receipts-v1') { throw 'policy_version_mismatch' }
if ([int]$a.human_decision_receipts_validated -lt 1) { throw 'no_valid_current_generation_human_decision_receipt' }
if ([int]$a.human_decision_receipts_invalid -ne 0) { throw 'invalid_human_decision_receipt_detected' }
if (-not $a.effect_boundary.producer_reads_only) { throw 'producer_reads_only=false' }
if (-not $a.effect_boundary.attention_inbox_write_only) { throw 'attention_inbox_write_only=false' }
if ($a.effect_boundary.provider_calls) { throw 'provider_calls=true' }
if ($a.effect_boundary.stable_roots_modified) { throw 'stable_roots_modified=true' }
if ($a.effect_boundary.r36_runtime_modified) { throw 'r36_runtime_modified=true' }
if ($a.effect_boundary.human_decision_execution) { throw 'human_decision_execution=true' }
if ($a.effect_boundary.synthetic_operator_events) { throw 'synthetic_operator_events=true' }
if ($a.effect_boundary.self_apply) { throw 'self_apply=true' }
if ($a.effect_boundary.skill_install) { throw 'skill_install=true' }
if ($a.effect_boundary.system_write) { throw 'system_write=true' }
if ($a.effect_boundary.operator_message) { throw 'operator_message=true' }
if ($a.effect_boundary.auto_dispatch) { throw 'auto_dispatch=true' }
if ($a.effect_boundary.external_messages) { throw 'external_messages=true' }
if ($a.effect_boundary.can_trade) { throw 'can_trade=true' }
if ($a.effect_boundary.capital_permission -ne 'DENY') { throw 'capital_permission_not_DENY' }
if ($a.secret_boundary.raw_values_persisted) { throw 'raw_secret_values_persisted=true' }
if ($f.effect_boundary.can_trade) { throw 'fabric_can_trade=true' }
if ($f.effect_boundary.capital_permission -ne 'DENY') { throw 'fabric_capital_permission_not_DENY' }
if ([int]$f.attention_summary.domain_counts.OPERATOR -lt 1) { throw 'operator_attention_not_closed' }

$material = [int]$f.ledger.observation_count
$coverage = [int]$f.ledger.coverage_count
$outcomes = [int]$f.ledger.outcome_count
$proposalCount = @($f.prioritized_proposals).Count
$blindSpots = @($f.attention_summary.blind_spots)
$classification = if ($f.attention_summary.coverage_complete) { 'COVERAGE_CLOSED' } else { 'OPERATOR_CLOSED_OTHER_BLIND_SPOT_REMAINS' }

Write-Host 'HANRI_R39_2_2_HUMAN_DECISION_RECEIPTS_PASS'
Write-Host "HUMAN_DECISION_RECEIPTS_VALIDATED $($a.human_decision_receipts_validated)"
Write-Host "HUMAN_DECISION_RECEIPTS_INVALID $($a.human_decision_receipts_invalid)"
Write-Host "PROCESSED_SOURCES $($a.processed_sources)"
Write-Host "EMITTED_ENVELOPES $($a.emitted_envelopes)"
Write-Host "SCAN_SKIPS $($a.scan_skip_count)"
Write-Host "SCAN_SKIP_REASONS $((($a.scan_skip_reason_counts.PSObject.Properties | Sort-Object Name | ForEach-Object { $_.Name + '=' + $_.Value }) -join ','))"
Write-Host "SCAN_SKIP_SOURCES $((($a.scan_skip_source_counts.PSObject.Properties | Sort-Object Name | ForEach-Object { $_.Name + '=' + $_.Value }) -join ','))"
Write-Host "MATERIAL_OBSERVATIONS $material"
Write-Host "COVERAGE_RECORDS $coverage"
Write-Host "RECOMMENDATION_OUTCOMES $outcomes"
Write-Host "PROPOSALS $proposalCount"
Write-Host "CLOSURE_CLASSIFICATION $classification"
Write-Host "COVERAGE_COMPLETE $($f.attention_summary.coverage_complete)"
Write-Host "COVERAGE SELF=$($f.attention_summary.domain_counts.SELF) AGENT=$($f.attention_summary.domain_counts.AGENT) SYSTEM=$($f.attention_summary.domain_counts.SYSTEM) OPERATOR=$($f.attention_summary.domain_counts.OPERATOR)"
Write-Host "MATERIAL SELF=$($f.attention_summary.material_domain_counts.SELF) AGENT=$($f.attention_summary.material_domain_counts.AGENT) SYSTEM=$($f.attention_summary.material_domain_counts.SYSTEM) OPERATOR=$($f.attention_summary.material_domain_counts.OPERATOR)"
Write-Host "BLIND_SPOTS $($blindSpots -join ',')"
Write-Host "TOP_PROPOSAL $($f.attention_summary.top_proposal_id)"
Write-Host "SECRET_FINDINGS_FINGERPRINTED $($a.secret_boundary.finding_count)"
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'HUMAN_DECISION_EXECUTION false'
Write-Host 'SYNTHETIC_OPERATOR_EVENTS false'
Write-Host 'SCHEDULER_INSTALLED false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "ADAPTER_RECEIPT $adapterReceipt"
Write-Host "FABRIC_RECEIPT $fabricReceipt"
