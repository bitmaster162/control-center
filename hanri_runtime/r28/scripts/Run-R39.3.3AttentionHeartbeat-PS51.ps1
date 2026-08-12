param(
  [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR39\live_attention_r39_3_3"
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
$cadencePolicy = Join-Path $runtime 'config\r39.3.2.attention-cadence.json'

$workRoot = Join-Path $OutputRoot 'work'
$stateRoot = Join-Path $OutputRoot 'state'
$receiptRoot = Join-Path $OutputRoot 'receipts'
$lockRoot = Join-Path $OutputRoot 'lock'
$fabricInput = Join-Path $workRoot 'fabric_input'
$bundle = Join-Path $workRoot 'R39_3_3_PRODUCER_ENVELOPES.json'
$adapterReceipt = Join-Path $workRoot 'R39_3_3_ADAPTER_RECEIPT.json'
$fabricReceipt = Join-Path $workRoot 'R39_3_3_SEMANTIC_FABRIC_RECEIPT.json'
$loopState = Join-Path $stateRoot 'R39_3_1_CONTINUOUS_ATTENTION_STATE.json'
$loopReceipt = Join-Path $stateRoot 'R39_3_1_CONTINUOUS_ATTENTION_LOOP_RECEIPT.json'
$cadenceState = Join-Path $stateRoot 'R39_3_2_CADENCE_STATE.json'
$cadenceReceipt = Join-Path $stateRoot 'R39_3_2_CADENCE_RECEIPT.json'
$latestReceipt = Join-Path $receiptRoot 'R39_3_3_LATEST_HEARTBEAT_RECEIPT.json'
$ledger = Join-Path $receiptRoot 'R39_3_3_HEARTBEAT_LEDGER.jsonl'
$leasePath = Join-Path $lockRoot 'attention_cycle.lock'

foreach ($path in @($workRoot, $stateRoot, $receiptRoot, $lockRoot, $fabricInput)) {
  New-Item -ItemType Directory -Force -Path $path | Out-Null
}

function Invoke-Python {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
  $old = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    & python @Args
    $code = $LASTEXITCODE
  }
  finally {
    $ErrorActionPreference = $old
  }
  if ($code -ne 0) { throw "python failed ($code): $($Args -join ' ')" }
}

function Write-HeartbeatReceipt {
  param(
    [string]$Action,
    [string]$Mode,
    [bool]$FullAttentionPerformed,
    [string]$LoopTransition,
    [int]$SemanticCycles,
    [int]$NoDeltaStreak,
    [string]$EvidenceSha,
    [bool]$CoverageComplete,
    [int]$ActiveProposals,
    [string]$CadenceReceiptSha
  )

  $payload = [ordered]@{
    schema_version = 1
    policy_version = '39.3.3-host-scheduler-package-v1'
    generated_at = [DateTime]::UtcNow.ToString('o')
    status = 'PASS'
    action = $Action
    mode = $Mode
    full_attention_performed = $FullAttentionPerformed
    loop_transition = $LoopTransition
    semantic_cycle_count = $SemanticCycles
    no_delta_streak = $NoDeltaStreak
    evidence_set_sha256 = $EvidenceSha
    coverage_complete = $CoverageComplete
    active_proposal_count = $ActiveProposals
    cadence_receipt_file_sha256 = $CadenceReceiptSha
    execution_effects_performed = 0
    effect_boundary = [ordered]@{
      scheduler_install = $false
      scheduler_modify = $false
      provider_calls = $false
      human_decision_execution = $false
      self_apply = $false
      skill_install = $false
      system_write = $false
      operator_message = $false
      auto_dispatch = $false
      external_messages = $false
      can_trade = $false
      capital_permission = 'DENY'
    }
  }

  $payload | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $latestReceipt
  ($payload | ConvertTo-Json -Depth 10 -Compress) | Add-Content -Encoding UTF8 $ledger
}

$lease = $null
try {
  try {
    $lease = [System.IO.File]::Open($leasePath, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $lease.SetLength(0)
    $leaseText = "pid=$PID started=$([DateTime]::UtcNow.ToString('o'))"
    $leaseBytes = [System.Text.Encoding]::UTF8.GetBytes($leaseText)
    $lease.Write($leaseBytes, 0, $leaseBytes.Length)
    $lease.Flush()
  }
  catch [System.IO.IOException] {
    Write-HeartbeatReceipt -Action 'SKIP_OVERLAP' -Mode 'OVERLAP' -FullAttentionPerformed $false -LoopTransition '' -SemanticCycles 0 -NoDeltaStreak 0 -EvidenceSha '' -CoverageComplete $false -ActiveProposals 0 -CadenceReceiptSha ''
    Write-Host 'HANRI_R39_3_3_HEARTBEAT_PASS'
    Write-Host 'ACTION SKIP_OVERLAP'
    Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
    Write-Host "RECEIPT $latestReceipt"
    exit 0
  }

  if ((Test-Path $cadenceState) -and -not (Test-Path $loopReceipt)) {
    throw 'cadence state exists but loop receipt is missing; refusing ambiguous recovery'
  }

  $now = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
  $runFull = -not (Test-Path $loopReceipt)
  $probeState = Join-Path $workRoot 'R39_3_3_CADENCE_PROBE_STATE.json'
  $probeReceipt = Join-Path $workRoot 'R39_3_3_CADENCE_PROBE_RECEIPT.json'

  if (-not $runFull) {
    Remove-Item -Force $probeState, $probeReceipt -ErrorAction SilentlyContinue
    if (Test-Path $cadenceState) { Copy-Item -LiteralPath $cadenceState -Destination $probeState -Force }
    Invoke-Python '-m' 'hanri.attention_cadence_cli' '--loop-receipt' $loopReceipt '--policy' $cadencePolicy '--state' $probeState '--output-receipt' $probeReceipt '--now' $now
    $probe = Get-Content -Raw -Encoding UTF8 $probeReceipt | ConvertFrom-Json
    if ($probe.action -eq 'SKIP_NOT_DUE') {
      Copy-Item -LiteralPath $probeState -Destination $cadenceState -Force
      Copy-Item -LiteralPath $probeReceipt -Destination $cadenceReceipt -Force
      $loop = Get-Content -Raw -Encoding UTF8 $loopReceipt | ConvertFrom-Json
      $cadenceSha = (Get-FileHash -Algorithm SHA256 $cadenceReceipt).Hash.ToLowerInvariant()
      Write-HeartbeatReceipt -Action 'SKIP_NOT_DUE' -Mode ([string]$probe.mode) -FullAttentionPerformed $false -LoopTransition ([string]$loop.transition) -SemanticCycles ([int]$loop.semantic_cycle_count) -NoDeltaStreak ([int]$loop.no_delta_streak) -EvidenceSha ([string]$loop.evidence_set_sha256) -CoverageComplete ([bool]$loop.coverage_complete) -ActiveProposals ([int]$loop.active_proposal_count) -CadenceReceiptSha $cadenceSha
      Write-Host 'HANRI_R39_3_3_HEARTBEAT_PASS'
      Write-Host 'ACTION SKIP_NOT_DUE'
      Write-Host "MODE $($probe.mode)"
      Write-Host 'FULL_ATTENTION_PERFORMED false'
      Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
      Write-Host "RECEIPT $latestReceipt"
      exit 0
    }
    if ($probe.action -ne 'RUN_FULL_ATTENTION') { throw "unexpected cadence probe action: $($probe.action)" }
    $runFull = $true
  }

  if ($runFull) {
    $generatedAt = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $runId = 'R39.3.3-SCHEDULED-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')

    Invoke-Python '-m' 'hanri.producer_adapters_operator_receipts_cli' '--config' $producerConfig '--output-bundle' $bundle '--output-receipt' $adapterReceipt '--generated-at' $generatedAt

    Get-ChildItem -LiteralPath $fabricInput -Filter '*.json' -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Copy-Item -LiteralPath $bundle -Destination (Join-Path $fabricInput 'R39_3_3_PRODUCER_ENVELOPES.json') -Force

    Invoke-Python '-m' 'hanri.attention_fabric_semantic_cli' '--input-dir' $fabricInput '--governor-policy' $governorPolicy '--fabric-policy' $fabricPolicy '--run-id' $runId '--generated-at' $generatedAt '--output' $fabricReceipt
    Invoke-Python '-m' 'hanri.continuous_attention_loop_semantic_cli' '--producer-bundle' $bundle '--fabric-receipt' $fabricReceipt '--policy' $loopPolicy '--state' $loopState '--output-receipt' $loopReceipt '--generated-at' $generatedAt

    $adapter = Get-Content -Raw -Encoding UTF8 $adapterReceipt | ConvertFrom-Json
    $fabric = Get-Content -Raw -Encoding UTF8 $fabricReceipt | ConvertFrom-Json
    $loop = Get-Content -Raw -Encoding UTF8 $loopReceipt | ConvertFrom-Json

    if ([int]$adapter.human_decision_receipts_validated -lt 1) { throw 'no valid human decision receipt' }
    if ([int]$adapter.human_decision_receipts_invalid -ne 0) { throw 'invalid human decision receipt detected' }
    if (-not $fabric.attention_summary.coverage_complete) { throw 'attention coverage incomplete' }
    if ([int]$fabric.attention_summary.domain_counts.OPERATOR -lt 1) { throw 'operator attention not covered' }
    if ($loop.evidence_hash_algorithm -ne 'SEMANTIC_ENVELOPE_V2') { throw 'semantic hash algorithm mismatch' }
    if ($loop.effect_boundary.can_trade) { throw 'can_trade=true' }
    if ($loop.effect_boundary.capital_permission -ne 'DENY') { throw 'capital_permission_not_DENY' }

    Invoke-Python '-m' 'hanri.attention_cadence_cli' '--loop-receipt' $loopReceipt '--policy' $cadencePolicy '--state' $cadenceState '--output-receipt' $cadenceReceipt '--now' $now
    $cadence = Get-Content -Raw -Encoding UTF8 $cadenceReceipt | ConvertFrom-Json
    if ($cadence.action -ne 'RUN_FULL_ATTENTION') { throw "cadence commit expected RUN_FULL_ATTENTION actual=$($cadence.action)" }
    $cadenceSha = (Get-FileHash -Algorithm SHA256 $cadenceReceipt).Hash.ToLowerInvariant()

    Write-HeartbeatReceipt -Action 'RUN_FULL_ATTENTION' -Mode ([string]$cadence.mode) -FullAttentionPerformed $true -LoopTransition ([string]$loop.transition) -SemanticCycles ([int]$loop.semantic_cycle_count) -NoDeltaStreak ([int]$loop.no_delta_streak) -EvidenceSha ([string]$loop.evidence_set_sha256) -CoverageComplete ([bool]$loop.coverage_complete) -ActiveProposals ([int]$loop.active_proposal_count) -CadenceReceiptSha $cadenceSha

    Write-Host 'HANRI_R39_3_3_HEARTBEAT_PASS'
    Write-Host 'ACTION RUN_FULL_ATTENTION'
    Write-Host "MODE $($cadence.mode)"
    Write-Host "LOOP_TRANSITION $($loop.transition)"
    Write-Host "SEMANTIC_CYCLES $($loop.semantic_cycle_count)"
    Write-Host "NO_DELTA_STREAK $($loop.no_delta_streak)"
    Write-Host "COVERAGE_COMPLETE $($loop.coverage_complete)"
    Write-Host 'FULL_ATTENTION_PERFORMED true'
    Write-Host 'PROVIDER_CALLS 0'
    Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
    Write-Host "RECEIPT $latestReceipt"
  }
}
finally {
  if ($lease) { $lease.Dispose() }
}
