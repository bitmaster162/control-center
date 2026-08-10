param(
    [string]$ControlCurrentRoot = "$env:USERPROFILE\My Drive\Control canter\00_CONTROL_CURRENT",
    [string]$ControlRoot = "$env:USERPROFILE\My Drive\Control canter"
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $SourceRoot "src"
$CurrentPointer = Join-Path $ControlCurrentRoot "CURRENT_POINTER.json"
$CurrentState = Join-Path $ControlCurrentRoot "CURRENT_STATE.json"
$RoleViews = Join-Path $ControlCurrentRoot "ROLE_VIEWS.json"
$DecisionQueue = Join-Path $ControlCurrentRoot "CONTROL_CANTER_R63_CONSOLIDATION_20260730\R63_PENDING_HUMAN_DECISIONS.md"
$R28Digest = Join-Path $ControlRoot "00_CONTROL\HANRI_R28\latest_human_digest.md"

foreach ($Path in @($CurrentPointer, $CurrentState, $RoleViews, $DecisionQueue, $R28Digest)) {
    if (-not (Test-Path $Path)) { throw "Decision Governor Pilot 01 prerequisite missing: $Path" }
}

$env:PYTHONPATH = $PythonPath
$env:PYTHONDONTWRITEBYTECODE = "1"
Write-Host "HANRI Decision Governor Pilot 01 (read-only)"
Write-Host "No Drive writes, no scheduler changes, no external messages, no dispatch, no trading."

& python -m hanri.decision_governor_pilot `
    --current-pointer $CurrentPointer `
    --current-state $CurrentState `
    --role-views $RoleViews `
    --decision-queue $DecisionQueue `
    --r28-digest $R28Digest

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
