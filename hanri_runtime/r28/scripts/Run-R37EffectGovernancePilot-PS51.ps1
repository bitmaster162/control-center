param(
    [string]$Python = "python",
    [string]$OutputRoot = "$env:LOCALAPPDATA\ControlCenterHANRIR37\receipts"
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Policy = Join-Path $AppRoot "config\r37.effect-policy.json"
$Fixture = Join-Path $AppRoot "data\r37_control_center_effect_candidates.json"
$Receipt = Join-Path $OutputRoot "R37_CONTROL_CENTER_EFFECT_GOVERNANCE_SHADOW_RECEIPT.json"

foreach ($path in @($Policy, $Fixture)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "R37 pilot input missing: $path" }
}

New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$oldPythonPath = $env:PYTHONPATH
$oldLocation = Get-Location
try {
    $env:PYTHONPATH = Join-Path $AppRoot "src"
    Set-Location $AppRoot
    & $Python -m pytest -q (Join-Path $AppRoot "tests\test_r37_effect_governance.py")
    if ($LASTEXITCODE -ne 0) { throw "R37 regression tests failed" }

    & $Python -m hanri.effect_governance_cli --policy $Policy --input $Fixture --output $Receipt
    if ($LASTEXITCODE -ne 0) { throw "R37 effect governance CLI failed" }
}
finally {
    Set-Location $oldLocation
    $env:PYTHONPATH = $oldPythonPath
}

if (-not (Test-Path -LiteralPath $Receipt)) { throw "R37 receipt missing: $Receipt" }
$payload = Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json
if ($payload.enforcement_mode -ne "SHADOW_ONLY") { throw "R37 enforcement mode mismatch" }
if ([int]$payload.execution_effects_performed -ne 0) { throw "R37 shadow pilot performed effects" }
if ([int]$payload.decision_count -ne 5) { throw "R37 decision count mismatch" }
if ([int]$payload.verdict_counts.ALLOW -ne 1) { throw "R37 ALLOW count mismatch" }
if ([int]$payload.verdict_counts.HUMAN_APPROVAL -ne 2) { throw "R37 HUMAN_APPROVAL count mismatch" }
if ([int]$payload.verdict_counts.DENY -ne 2) { throw "R37 DENY count mismatch" }

foreach ($decision in $payload.decisions) {
    if ($decision.execution_authorized -ne $false) { throw "R37 decision unexpectedly authorized execution" }
    if ($decision.invariants.can_trade -ne $false) { throw "R37 can_trade invariant failed" }
    if ($decision.invariants.capital_permission -ne "DENY") { throw "R37 capital_permission invariant failed" }
}

Write-Host "HANRI_R37_CONTROL_CENTER_SHADOW_PASS"
Write-Host "POLICY_VERSION $($payload.policy_version)"
Write-Host "ALLOW $($payload.verdict_counts.ALLOW)"
Write-Host "HUMAN_APPROVAL $($payload.verdict_counts.HUMAN_APPROVAL)"
Write-Host "DENY $($payload.verdict_counts.DENY)"
Write-Host "EXECUTION_EFFECTS_PERFORMED $($payload.execution_effects_performed)"
Write-Host "RECEIPT $Receipt"
