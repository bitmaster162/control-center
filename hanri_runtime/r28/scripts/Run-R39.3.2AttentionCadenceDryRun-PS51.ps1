param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\cadence_dry_run"
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $runtime)
$env:HANRI_REPO_ROOT = $repoRoot
$env:PYTHONPATH = Join-Path $runtime 'src'

$loopRunner = Join-Path $runtime 'scripts\Run-R39.3.1SemanticContinuousAttentionLoop-PS51.ps1'
$policy = Join-Path $runtime 'config\r39.3.2.attention-cadence.json'
$loopOutput = Join-Path $OutputRoot 'loop_source'
$loopReceipt = Join-Path $loopOutput 'continuous_receipts_v2\R39_3_1_CONTINUOUS_ATTENTION_LOOP_RECEIPT.json'
$state = Join-Path $OutputRoot 'R39_3_2_CADENCE_STATE.json'
$receipt1 = Join-Path $OutputRoot 'R39_3_2_CADENCE_RECEIPT_1.json'
$receipt2 = Join-Path $OutputRoot 'R39_3_2_CADENCE_RECEIPT_2.json'

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
if (Test-Path $state) { Remove-Item -Force $state }

python -m pytest -q (Join-Path $runtime 'tests\test_r39_3_2_attention_cadence.py')
if ($LASTEXITCODE -ne 0) { throw 'R39.3.2 cadence regression tests failed' }

& powershell -NoProfile -ExecutionPolicy Bypass -File $loopRunner -OutputRoot $loopOutput
if ($LASTEXITCODE -ne 0) { throw 'R39.3.2 source R39.3.1 loop failed' }
if (-not (Test-Path $loopReceipt)) { throw 'R39.3.1 source loop receipt missing' }

$t0 = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$t1 = (Get-Date).ToUniversalTime().AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:ssZ')
python -m hanri.attention_cadence_cli --loop-receipt $loopReceipt --policy $policy --state $state --output-receipt $receipt1 --now $t0
if ($LASTEXITCODE -ne 0) { throw 'R39.3.2 first cadence decision failed' }
python -m hanri.attention_cadence_cli --loop-receipt $loopReceipt --policy $policy --state $state --output-receipt $receipt2 --now $t1
if ($LASTEXITCODE -ne 0) { throw 'R39.3.2 second cadence decision failed' }

$r1 = Get-Content -Raw -Encoding UTF8 $receipt1 | ConvertFrom-Json
$r2 = Get-Content -Raw -Encoding UTF8 $receipt2 | ConvertFrom-Json
$s = Get-Content -Raw -Encoding UTF8 $state | ConvertFrom-Json

if ($r1.policy_version -ne '39.3.2-attention-cadence-v1') { throw 'cadence policy mismatch' }
if ($r1.action -ne 'RUN_FULL_ATTENTION') { throw "first action expected RUN_FULL_ATTENTION actual=$($r1.action)" }
if ($r2.action -ne 'SKIP_NOT_DUE') { throw "second action expected SKIP_NOT_DUE actual=$($r2.action)" }
if ([int]$r1.heartbeat_minutes -ne 5) { throw 'heartbeat must be 5 minutes' }
if ([int]$r1.interval_minutes -ne 15) { throw 'normal full scan interval must be 15 minutes' }
if ([int]$s.full_attention_run_count -ne 1) { throw 'full attention run count mismatch' }
if ([int]$s.not_due_skip_count -ne 1) { throw 'not-due skip count mismatch' }
foreach ($boundary in @($r1.effect_boundary, $r2.effect_boundary, $s.effect_boundary)) {
  if ($boundary.scheduler_install) { throw 'scheduler_install=true' }
  if ($boundary.scheduler_modify) { throw 'scheduler_modify=true' }
  if ($boundary.provider_calls) { throw 'provider_calls=true' }
  if ($boundary.self_apply) { throw 'self_apply=true' }
  if ($boundary.auto_dispatch) { throw 'auto_dispatch=true' }
  if ($boundary.can_trade) { throw 'can_trade=true' }
  if ($boundary.capital_permission -ne 'DENY') { throw 'capital_permission_not_DENY' }
}

Write-Host 'HANRI_R39_3_2_CADENCE_DRY_RUN_PASS'
Write-Host "SOURCE_LOOP_TRANSITION $((Get-Content -Raw -Encoding UTF8 $loopReceipt | ConvertFrom-Json).transition)"
Write-Host "HEARTBEAT_MINUTES $($r1.heartbeat_minutes)"
Write-Host "FIRST_ACTION $($r1.action)"
Write-Host "FIRST_MODE $($r1.mode)"
Write-Host "FULL_SCAN_INTERVAL_MINUTES $($r1.interval_minutes)"
Write-Host "SECOND_ACTION_AT_PLUS_5M $($r2.action)"
Write-Host "FULL_ATTENTION_RUN_COUNT $($s.full_attention_run_count)"
Write-Host "NOT_DUE_SKIP_COUNT $($s.not_due_skip_count)"
Write-Host 'QUIET_AFTER_NO_DELTA_3 30'
Write-Host 'DEEP_QUIET_AFTER_NO_DELTA_6 60'
Write-Host 'URGENT_COVERAGE_OR_NEGATIVE_OUTCOME 5'
Write-Host 'ACTIVE_PROPOSAL_INTERVAL 10'
Write-Host 'OVERLAP_POLICY SKIP_OVERLAP'
Write-Host 'SCHEDULER_INSTALLED false'
Write-Host 'SCHEDULER_MODIFIED false'
Write-Host 'PROVIDER_CALLS 0'
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
Write-Host "STATE $state"
Write-Host "RECEIPT $receipt2"
