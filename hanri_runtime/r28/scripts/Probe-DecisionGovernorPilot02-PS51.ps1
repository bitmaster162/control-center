param(
    [string]$ControlCurrentRoot = "$env:USERPROFILE\My Drive\Control canter\00_CONTROL_CURRENT",
    [string]$ControlRoot = "$env:USERPROFILE\My Drive\Control canter",
    [string[]]$AcceptedDecision = @()
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $SourceRoot "src"
$CurrentPointer = Join-Path $ControlCurrentRoot "CURRENT_POINTER.json"
$CurrentState = Join-Path $ControlCurrentRoot "CURRENT_STATE.json"
$RoleViews = Join-Path $ControlCurrentRoot "ROLE_VIEWS.json"
$DecisionQueue = Join-Path $ControlCurrentRoot "CONTROL_CANTER_R63_CONSOLIDATION_20260730\R63_PENDING_HUMAN_DECISIONS.md"
$P0Receipts = Join-Path $ControlCurrentRoot "CONTROL_CANTER_R63_CONSOLIDATION_20260730\DECISIONS_R63\P0_RECEIPTS"
$R28Digest = Join-Path $ControlRoot "00_CONTROL\HANRI_R28\latest_human_digest.md"

foreach ($Path in @($CurrentPointer, $CurrentState, $RoleViews, $DecisionQueue, $P0Receipts, $R28Digest)) {
    if (-not (Test-Path $Path)) { throw "Decision Governor Pilot 02 prerequisite missing: $Path" }
}

$env:PYTHONPATH = $PythonPath
$env:PYTHONDONTWRITEBYTECODE = "1"
Write-Host "HANRI Decision Governor Pilot 02 - Effect Lifecycle (read-only)"
Write-Host "Reads P0 receipts; no Drive writes, scheduler changes, messages, dispatch, deploy, trading or capital use."

$Args = @(
    "-m", "hanri.decision_governor_effect_lifecycle",
    "--current-pointer", $CurrentPointer,
    "--current-state", $CurrentState,
    "--role-views", $RoleViews,
    "--decision-queue", $DecisionQueue,
    "--r28-digest", $R28Digest,
    "--p0-receipts-dir", $P0Receipts
)
foreach ($Decision in $AcceptedDecision) {
    $Args += @("--accepted-decision", $Decision)
}

& python @Args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
