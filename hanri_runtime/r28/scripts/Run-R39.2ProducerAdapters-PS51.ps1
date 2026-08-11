param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39"
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'
$config = Join-Path $runtime 'config\r39.2.producer-adapters.json'
$governorPolicy = Join-Path $runtime 'config\r39.attention-governor.json'
$fabricPolicy = Join-Path $runtime 'config\r39.1.attention-fabric.json'
$producerDir = Join-Path $OutputRoot 'producer_current'
$receiptDir = Join-Path $OutputRoot 'receipts'
$bundle = Join-Path $producerDir 'R39_2_PRODUCER_ENVELOPES.json'
$adapterReceipt = Join-Path $receiptDir 'R39_2_PRODUCER_ADAPTERS_RECEIPT.json'
$fabricReceipt = Join-Path $receiptDir 'R39_2_ATTENTION_FABRIC_RECEIPT.json'
$generatedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$runId = 'R39.2-HOST-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')

New-Item -ItemType Directory -Force -Path $producerDir | Out-Null
New-Item -ItemType Directory -Force -Path $receiptDir | Out-Null

python -m pytest -q `
  (Join-Path $runtime 'tests\test_r39_producer_adapters.py') `
  (Join-Path $runtime 'tests\test_r39_attention_fabric.py') `
  (Join-Path $runtime 'tests\test_r39_attention_governor.py')
if ($LASTEXITCODE -ne 0) { throw "R39.2 regression tests failed" }

python -m hanri.producer_adapters_cli `
  --config $config `
  --output-bundle $bundle `
  --output-receipt $adapterReceipt `
  --generated-at $generatedAt
if ($LASTEXITCODE -ne 0) { throw "R39.2 producer adapter run failed" }

python -m hanri.attention_fabric_cli `
  --input-dir $producerDir `
  --governor-policy $governorPolicy `
  --fabric-policy $fabricPolicy `
  --run-id $runId `
  --generated-at $generatedAt `
  --output $fabricReceipt | Out-Null
if ($LASTEXITCODE -ne 0) { throw "R39.2 attention fabric run failed" }

$a = Get-Content -Raw -Encoding UTF8 $adapterReceipt | ConvertFrom-Json
$f = Get-Content -Raw -Encoding UTF8 $fabricReceipt | ConvertFrom-Json

if (-not $a.effect_boundary.producer_reads_only) { throw 'producer_reads_only=false' }
if (-not $a.effect_boundary.attention_inbox_write_only) { throw 'attention_inbox_write_only=false' }
if ($a.effect_boundary.provider_calls) { throw 'provider_calls=true' }
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

$material = [int]$f.ledger.observation_count
$coverage = [int]$f.ledger.coverage_count
$outcomes = [int]$f.ledger.outcome_count
$proposalCount = @($f.prioritized_proposals).Count
$blindSpots = @($f.attention_summary.blind_spots)

Write-Host 'HANRI_R39_2_PRODUCER_ADAPTERS_PASS'
Write-Host "PROCESSED_SOURCES $($a.processed_sources)"
Write-Host "EMITTED_ENVELOPES $($a.emitted_envelopes)"
Write-Host "SCAN_SKIPS $($a.scan_skip_count)"
Write-Host "MATERIAL_OBSERVATIONS $material"
Write-Host "COVERAGE_RECORDS $coverage"
Write-Host "RECOMMENDATION_OUTCOMES $outcomes"
Write-Host "PROPOSALS $proposalCount"
Write-Host "COVERAGE_COMPLETE $($f.attention_summary.coverage_complete)"
Write-Host "BLIND_SPOTS $($blindSpots -join ',')"
Write-Host "SECRET_FINDINGS_FINGERPRINTED $($a.secret_boundary.finding_count)"
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "ADAPTER_RECEIPT $adapterReceipt"
Write-Host "FABRIC_RECEIPT $fabricReceipt"
