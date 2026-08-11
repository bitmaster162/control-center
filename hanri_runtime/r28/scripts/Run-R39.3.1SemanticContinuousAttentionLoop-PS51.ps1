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
$loopPolicy = Join-Path $runtime 'config\r39.3.1.continuous-attention-loop.json'
$decisionReceipt = Join-Path $repoRoot 'receipts\D1_D5_DECISION_RECEIPT.json'

$workRoot = Join-Path $OutputRoot 'continuous_work_v2'
$stateRoot = Join-Path $OutputRoot 'continuous_state_v2'
$loopReceiptRoot = Join-Path $OutputRoot 'continuous_receipts_v2'
$scannedReceiptRoot = Join-Path $OutputRoot 'receipts'
$bundle = Join-Path $workRoot 'R39_3_1_PRODUCER_ENVELOPES.json'
$adapterReceipt = Join-Path $workRoot 'R39_3_1_ADAPTER_RECEIPT.json'
$fabricInput = Join-Path $workRoot 'fabric_input'
$fabricReceipt = Join-Path $workRoot 'R39_3_1_SEMANTIC_ATTENTION_FABRIC_RECEIPT.json'
$loopState = Join-Path $stateRoot 'R39_3_1_CONTINUOUS_ATTENTION_STATE.json'
$loopReceipt = Join-Path $loopReceiptRoot 'R39_3_1_CONTINUOUS_ATTENTION_LOOP_RECEIPT.json'
$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$runId = 'R39.3.1-HOST-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')

if (-not (Test-Path -LiteralPath $decisionReceipt -PathType Leaf)) { throw "authoritative human decision receipt missing: $decisionReceipt" }
foreach ($path in @($workRoot, $stateRoot, $loopReceiptRoot, $fabricInput)) { New-Item -ItemType Directory -Force -Path $path | Out-Null }

if (Test-Path -LiteralPath $scannedReceiptRoot -PathType Container) {
  $scanRoot = (Resolve-Path -LiteralPath $scannedReceiptRoot).Path.TrimEnd('\')
  foreach ($candidate in @($workRoot, $stateRoot, $loopReceiptRoot)) {
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if ($resolved.StartsWith($scanRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'v2_continuous_root_inside_scanned_receipt_root' }
  }
}

python -m pytest -q `
  (Join-Path $runtime 'tests\test_r39_3_1_semantic_delta_repair.py') `
  (Join-Path $runtime 'tests\test_r39_3_continuous_attention_loop.py') `
  (Join-Path $runtime 'tests\test_r39_2_2_human_decision_receipts.py') `
  (Join-Path $runtime 'tests\test_r39_attention_fabric.py')
if ($LASTEXITCODE -ne 0) { throw 'R39.3.1 regression tests failed' }

python -m hanri.producer_adapters_operator_receipts_cli `
  --config $producerConfig --output-bundle $bundle --output-receipt $adapterReceipt --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw 'R39.3.1 producer adapter run failed' }

Get-ChildItem -LiteralPath $fabricInput -Filter '*.json' -File -ErrorAction SilentlyContinue | Remove-Item -Force
Copy-Item -LiteralPath $bundle -Destination (Join-Path $fabricInput 'R39_3_1_PRODUCER_ENVELOPES.json') -Force

python -m hanri.attention_fabric_semantic_cli `
  --input-dir $fabricInput --governor-policy $governorPolicy --fabric-policy $fabricPolicy `
  --run-id $runId --generated-at $generatedAt --output $fabricReceipt | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'R39.3.1 semantic attention fabric run failed' }

python -m hanri.continuous_attention_loop_semantic_cli `
  --producer-bundle $bundle --fabric-receipt $fabricReceipt --policy $loopPolicy `
  --state $loopState --output-receipt $loopReceipt --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw 'R39.3.1 semantic continuous loop failed' }

$a = Get-Content -Raw -Encoding UTF8 $adapterReceipt | ConvertFrom-Json
$f = Get-Content -Raw -Encoding UTF8 $fabricReceipt | ConvertFrom-Json
$s = Get-Content -Raw -Encoding UTF8 $loopState | ConvertFrom-Json
$r = Get-Content -Raw -Encoding UTF8 $loopReceipt | ConvertFrom-Json

if ($r.policy_version -ne '39.3.1-continuous-attention-loop-v2') { throw 'loop_policy_version_mismatch' }
if ($s.policy_version -ne '39.3.1-continuous-attention-loop-v2') { throw 'state_policy_version_mismatch' }
if ($r.evidence_hash_algorithm -ne 'SEMANTIC_ENVELOPE_V2') { throw 'receipt_hash_algorithm_mismatch' }
if ($s.evidence_hash_algorithm -ne 'SEMANTIC_ENVELOPE_V2') { throw 'state_hash_algorithm_mismatch' }
if ($f.envelope_hash_algorithm -ne 'SEMANTIC_ENVELOPE_V2') { throw 'fabric_hash_algorithm_mismatch' }
if ([int]$a.human_decision_receipts_validated -lt 1) { throw 'no_valid_human_decision_receipt' }
if ([int]$a.human_decision_receipts_invalid -ne 0) { throw 'invalid_human_decision_receipt_detected' }
if (-not $f.attention_summary.coverage_complete) { throw 'attention_coverage_not_complete' }
if ([int]$f.attention_summary.domain_counts.OPERATOR -lt 1) { throw 'operator_attention_not_covered' }
if ($r.state_sha256 -ne $s.state_sha256) { throw 'state_receipt_sha_binding_mismatch' }

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

Write-Host 'HANRI_R39_3_1_SEMANTIC_LOOP_PASS'
Write-Host "TRANSITION $($r.transition)"
Write-Host "WAKE_INDEX $($r.wake_index)"
Write-Host "SEMANTIC_CYCLES $($r.semantic_cycle_count)"
Write-Host "NO_DELTA_STREAK $($r.no_delta_streak)"
Write-Host "EVIDENCE_HASH_ALGORITHM $($r.evidence_hash_algorithm)"
Write-Host "EVIDENCE_SET_SHA256 $($r.evidence_set_sha256)"
Write-Host "COVERAGE_COMPLETE $($r.coverage_complete)"
Write-Host "COVERAGE SELF=$($r.domain_counts.SELF) AGENT=$($r.domain_counts.AGENT) SYSTEM=$($r.domain_counts.SYSTEM) OPERATOR=$($r.domain_counts.OPERATOR)"
Write-Host "ACTIVE_PROPOSALS $($r.active_proposal_count)"
Write-Host "TRACKED_PROPOSALS $($r.tracked_proposal_count)"
Write-Host "NEXT_ATTENTION_MODE $($r.next_attention.mode)"
Write-Host "NEXT_ATTENTION_FOCUS $(@($r.next_attention.focus_domains) -join ',')"
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'SCHEDULER_INSTALLED false'
Write-Host 'HUMAN_DECISION_EXECUTION false'
Write-Host 'SELF_APPLY false'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "STATE $loopState"
Write-Host "RECEIPT $loopReceipt"
