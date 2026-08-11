param(
  [string]$InputDir = "$env:LOCALAPPDATA\ControlCenterHANRIR39\attention_inbox",
  [string]$OutputPath = "$env:LOCALAPPDATA\ControlCenterHANRIR39\receipts\R39_1_ATTENTION_FABRIC_RECEIPT.json",
  [string]$RunId = "R39.1-HOST-LIVE"
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'
$governorPolicy = Join-Path $runtime 'config\r39.attention-governor.json'
$fabricPolicy = Join-Path $runtime 'config\r39.1.attention-fabric.json'
$tests = Join-Path $runtime 'tests\test_r39_attention_fabric.py'
New-Item -ItemType Directory -Force -Path $InputDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath) | Out-Null
$files = @(Get-ChildItem -LiteralPath $InputDir -Filter '*.json' -File -ErrorAction Stop)
if ($files.Count -eq 0) {
  throw "ATTENTION_INBOX_EMPTY:$InputDir"
}
python -m pytest -q $tests
$generatedAt = (Get-Date).ToString('o')
python -m hanri.attention_fabric_cli --input-dir $InputDir --governor-policy $governorPolicy --fabric-policy $fabricPolicy --run-id $RunId --generated-at $generatedAt --output $OutputPath | Out-Null
$r = Get-Content -Raw -Encoding UTF8 $OutputPath | ConvertFrom-Json
if ($r.mode -ne 'REAL_ENVELOPE_INGESTION') { throw 'mode_not_real_envelope_ingestion' }
if (-not $r.effect_boundary.proposal_only) { throw 'proposal_only=false' }
if ($r.effect_boundary.self_apply) { throw 'self_apply=true' }
if ($r.effect_boundary.skill_install) { throw 'skill_install=true' }
if ($r.effect_boundary.system_write) { throw 'system_write=true' }
if ($r.effect_boundary.operator_message) { throw 'operator_message=true' }
if ($r.effect_boundary.auto_dispatch) { throw 'auto_dispatch=true' }
if ($r.effect_boundary.external_messages) { throw 'external_messages=true' }
if ($r.effect_boundary.can_trade) { throw 'can_trade=true' }
if ($r.effect_boundary.capital_permission -ne 'DENY') { throw 'capital_permission_not_DENY' }
Write-Host 'HANRI_R39_1_ATTENTION_FABRIC_PASS'
Write-Host "RECEIPT $OutputPath"
Write-Host "INPUT_ENVELOPES $($r.ledger.input_envelopes)"
Write-Host "ACCEPTED_ENVELOPES $($r.ledger.accepted_envelopes)"
Write-Host "DUPLICATE_ENVELOPES $($r.ledger.duplicate_envelopes)"
Write-Host "OBSERVATIONS $($r.ledger.observation_count)"
Write-Host "OUTCOMES $($r.ledger.outcome_count)"
Write-Host "PROPOSALS $(@($r.prioritized_proposals).Count)"
Write-Host "COVERAGE_COMPLETE $($r.attention_summary.coverage_complete)"
Write-Host "BLIND_SPOTS $(@($r.attention_summary.blind_spots) -join ',')"
Write-Host "TOP_PROPOSAL $($r.attention_summary.top_proposal_id)"
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
