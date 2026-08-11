param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39"
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $runtime)
$env:HANRI_REPO_ROOT = $repoRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$producerConfig = Join-Path $runtime 'config\r39.2.2.human-decision-receipts.json'
$governorPolicy = Join-Path $runtime 'config\r39.attention-governor.json'
$fabricPolicy = Join-Path $runtime 'config\r39.1.attention-fabric.json'
$loopPolicy = Join-Path $runtime 'config\r39.3.continuous-attention-loop.json'
$decisionReceipt = Join-Path $repoRoot 'receipts\D1_D5_DECISION_RECEIPT.json'

# These three roots are intentionally outside the R39_HANRI_RECEIPTS producer source
# (%LOCALAPPDATA%\ControlCenterHANRIR39\receipts) to prevent self-generated wake
# receipts from becoming fake new evidence on the next cycle.
$workRoot = Join-Path $OutputRoot 'continuous_work'
$stateRoot = Join-Path $OutputRoot 'continuous_state'
$loopReceiptRoot = Join-Path $OutputRoot 'continuous_receipts'
$scannedReceiptRoot = Join-Path $OutputRoot 'receipts'

$bundle = Join-Path $workRoot 'R39_3_PRODUCER_ENVELOPES.json'
$adapterReceipt = Join-Path $workRoot 'R39_3_ADAPTER_RECEIPT.json'
$fabricInput = Join-Path $workRoot 'fabric_input'
$fabricReceipt = Join-Path $workRoot 'R39_3_ATTENTION_FABRIC_RECEIPT.json'
$loopState = Join-Path $stateRoot 'R39_3_CONTINUOUS_ATTENTION_STATE.json'
$loopReceipt = Join-Path $loopReceiptRoot 'R39_3_CONTINUOUS_ATTENTION_LOOP_RECEIPT.json'
$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$runId = 'R39.3-HOST-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')

if (-not (Test-Path -LiteralPath $decisionReceipt -PathType Leaf)) {
  throw "authoritative human decision receipt missing: $decisionReceipt"
}

foreach ($path in @($workRoot, $stateRoot, $loopReceiptRoot, $fabricInput)) {
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}

if ((Resolve-Path $workRoot).Path.StartsWith((Resolve-Path $scannedReceiptRoot -ErrorAction SilentlyContinue).Path + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  throw 'continuous_work_must_not_be_inside_scanned_receipt_root'
}
if ((Resolve-Path $loopReceiptRoot).Path.StartsWith((Resolve-Path $scannedReceiptRoot -ErrorAction SilentlyContinue).Path + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
  throw 'continuous_receipts_must_not_be_inside_scanned_receipt_root'
}

python -m pytest -q `
  (Join-Path $runtime 'tests\test_r39_3_continuous_attention_loop.py') `
  (Join-Path $runtime 'tests\test_r39_2_2_human_decision_receipts.py') `
  (Join-Path $runtime 'tests\test_r39_2_1_attention_coverage_closure.py') `
  (Join-Path $runtime 'tests\test_r39_producer_adapters.py') `
  (Join-Path $runtime 'tests\test_r39_attention_fabric.py') `
  (Join-Path $runtime 'tests\test_r39_attention_governor.py')
if ($LASTEXITCODE -ne 0) { throw 'R39.3 regression tests failed' }

python -m hanri.producer_adapters_operator_receipts_cli `
  --config $producerConfig `
  --output-bundle $bundle `
  --output-receipt $adapterReceipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw 'R39.3 producer adapter run failed' }

Get-ChildItem -LiteralPath $fabricInput -Filter '*.json' -File -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item -LiteralPath $bundle -Destination (Join-Path $fabricInput 'R39_3_PRODUCER_ENVELOPES.json') -Force

python -m hanri.attention_fabric_cli `
  --input-dir $fabricInput `
  --governor-policy $governorPolicy `
  --fabric-policy $fabricPolicy `
  --run-id $runId `
  --generated-at $generatedAt `
  --output $fabricReceipt | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'R39.3 attention fabric run failed' }

python -m hanri.continuous_attention_loop_cli `
  --producer-bundle $bundle `
  --fabric-receipt $fabricReceipt `
  --policy $loopPolicy `
  --state $loopState `
  --output-receipt $loopReceipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw 'R39.3 continuous attention state transition failed' }

$a = Get-Content -Raw -Encoding UTF8 $adapterReceipt | ConvertFrom-Json
$f = Get-Content -Raw -Encoding UTF8 $fabricReceipt | ConvertFrom-Json
$s = Get-Content -Raw -Encoding UTF8 $loopState | ConvertFrom-Json
$r = Get-Content -Raw -Encoding UTF8 $loopReceipt | ConvertFrom-Json

if ($r.policy_version -ne '39.3.0-continuous-attention-loop-v1') { throw 'loop_policy_version_mismatch' }
if ($s.policy_version -ne '39.3.0-continuous-attention-loop-v1') { throw 'state_policy_version_mismatch' }
if ([int]$a.human_decision_receipts_validated -lt 1) { throw 'no_valid_human_decision_receipt' }
if ([int]$a.human_decision_receipts_invalid -ne 0) { throw 'invalid_human_decision_receipt_detected' }
if (-not $f.attention_summary.coverage_complete) { throw 'attention_coverage_not_complete' }
if ([int]$f.attention_summary.domain_counts.OPERATOR -lt 1) { throw 'operator_attention_not_covered' }

foreach ($boundary in @($s.effect_boundary, $r.effect_boundary)) {
  if (-not $boundary.proposal_only) { throw 'proposal_only=false' }
  if (-not $boundary.local_state_write_only) { throw 'local_state_write_only=false' }
  if ($boundary.provider_calls) { throw 'provider_calls=true' }
  if ($boundary.scheduler_install) { throw 'scheduler_install=true' }
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

$proposalCount = @($f.prioritized_proposals).Count
$blindSpots = @($f.attention_summary.blind_spots)
$negativeOutcomes = @($r.unresolved_negative_outcomes)

Write-Host 'HANRI_R39_3_CONTINUOUS_ATTENTION_LOOP_PASS'
Write-Host "TRANSITION $($r.transition)"
Write-Host "WAKE_INDEX $($r.wake_index)"
Write-Host "SEMANTIC_CYCLES $($r.semantic_cycle_count)"
Write-Host "NO_DELTA_STREAK $($r.no_delta_streak)"
Write-Host "EVIDENCE_SET_SHA256 $($r.evidence_set_sha256)"
Write-Host "COVERAGE_COMPLETE $($r.coverage_complete)"
Write-Host "COVERAGE SELF=$($r.domain_counts.SELF) AGENT=$($r.domain_counts.AGENT) SYSTEM=$($r.domain_counts.SYSTEM) OPERATOR=$($r.domain_counts.OPERATOR)"
Write-Host "BLIND_SPOTS $($blindSpots -join ',')"
Write-Host "ACTIVE_PROPOSALS $($r.active_proposal_count)"
Write-Host "TRACKED_PROPOSALS $($r.tracked_proposal_count)"
Write-Host "UNRESOLVED_NEGATIVE_OUTCOMES $($negativeOutcomes.Count)"
Write-Host "NEXT_ATTENTION_MODE $($r.next_attention.mode)"
Write-Host "NEXT_ATTENTION_FOCUS $(@($r.next_attention.focus_domains) -join ',')"
Write-Host "PRODUCER_SOURCES $($a.processed_sources)"
Write-Host "FABRIC_PROPOSALS $proposalCount"
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SCHEDULER_INSTALLED false'
Write-Host 'HUMAN_DECISION_EXECUTION false'
Write-Host 'SELF_APPLY false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "STATE $loopState"
Write-Host "RECEIPT $loopReceipt"
