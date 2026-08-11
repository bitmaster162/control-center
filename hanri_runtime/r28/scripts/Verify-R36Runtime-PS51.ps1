param(
    [string]$Python = "python",
    [string]$R35TaskName = "ControlCenter-HANRI-R35",
    [string]$R36TaskName = "ControlCenter-HANRI-R36"
)

$ErrorActionPreference = "Stop"
$Base = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR36"
$App = Join-Path $Base "app"
$State = Join-Path $Base "state"
$Receipts = Join-Path $Base "receipts"
$Config = Join-Path $App "config\r36.windows.json"
$ExpectedProgramVersion = "36.0.0"
$ExpectedIntegrityPolicy = "36.0.0-heartbeat-integrity-fast-gate-v1"
$ExpectedCachedMode = "CACHED_STAT_GUARD"

function Invoke-Native([string]$FilePath, [string[]]$Arguments) {
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $FilePath @Arguments
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    if ($code -ne 0) { throw "native command failed ($code): $FilePath $($Arguments -join ' ')" }
}

foreach ($path in @($App, $State, $Config)) {
    if (-not (Test-Path $path)) { throw "R36 verify missing: $path" }
}
$r36Task = Get-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue
$r35Task = Get-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
if (-not $r36Task -or $r36Task.State -eq "Disabled") { throw "R36 task is not enabled" }
if ($r35Task -and $r35Task.State -ne "Disabled") { throw "R35 task should be disabled after R36 cutover" }

$oldPythonPath = $env:PYTHONPATH
$oldLocation = Get-Location
try {
    $env:PYTHONPATH = Join-Path $App "src"
    Set-Location $App
    Invoke-Native $Python @("-m", "pytest", "-q", (Join-Path $App "tests\test_r36_integrity_fast_gate.py"), (Join-Path $App "tests\test_r36_release_gate.py"))
    Invoke-Native $Python @("-m", "hanri", "once", "--config", $Config)
    Invoke-Native $Python @("-m", "hanri", "once", "--config", $Config)
} finally {
    Set-Location $oldLocation
    $env:PYTHONPATH = $oldPythonPath
}

$run = Get-Content (Join-Path $State "latest_run_receipt.json") -Raw | ConvertFrom-Json
$projection = Get-Content (Join-Path $State "latest_projection_receipt.json") -Raw | ConvertFrom-Json
$aiState = Get-Content (Join-Path $State "latest_ai_state.json") -Raw | ConvertFrom-Json

if ($run.program_version -ne $ExpectedProgramVersion) { throw "R36 verify run version mismatch" }
if ($projection.program_version -ne $ExpectedProgramVersion) { throw "R36 verify projection version mismatch" }
if ($aiState.program_version -ne $ExpectedProgramVersion) { throw "R36 verify state version mismatch" }
if ($run.heartbeat_fast_path -ne $true) { throw "R36 verify latest run is not fast path" }
if ($run.can_trade -ne $false -or $run.self_application -ne $false) { throw "R36 verify effect invariant failed" }
if ([int]$run.external_model_api_calls -ne 0) { throw "R36 verify external model API invariant failed" }
if ($projection.integrity_policy_version -ne $ExpectedIntegrityPolicy) { throw "R36 verify integrity policy mismatch" }
if ($projection.heavy_snapshot_integrity_mode -ne $ExpectedCachedMode) { throw "R36 verify cached mode mismatch" }
if ($projection.heavy_snapshot_full_sha_performed -ne $false) { throw "R36 verify cached run performed full SHA" }
if ([int64]$projection.heavy_snapshot_bytes_hashed -ne 0) { throw "R36 verify cached run hashed heavy bytes" }

foreach ($name in @("latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json")) {
    $path = Join-Path $State $name
    $expected = [string]$projection.heavy_snapshot_raw_sha256.$name
    $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected.ToLowerInvariant()) { throw "R36 independent full SHA readback failed: $name" }
}

$installReceiptPath = Join-Path $Receipts "INSTALL_R36_RC1_RECEIPT.json"
if (-not (Test-Path $installReceiptPath)) { throw "R36 install receipt missing" }
$installReceipt = Get-Content $installReceiptPath -Raw | ConvertFrom-Json
if ($installReceipt.status -ne "PASS") { throw "R36 install receipt is not PASS" }

$verifyReceipt = [ordered]@{
    schema_version = 1
    status = "PASS"
    verified_at_utc = [DateTime]::UtcNow.ToString("o")
    program_version = $ExpectedProgramVersion
    integrity_policy = $ExpectedIntegrityPolicy
    cached_mode = $ExpectedCachedMode
    cached_bytes_hashed = [int64]$projection.heavy_snapshot_bytes_hashed
    independent_full_sha_readback = "PASS"
    regression_tests = "PASS"
    r36_task_enabled = $true
    r35_task_disabled = $true
    can_trade = $false
    capital_permission = "DENY"
}
$verifyReceiptPath = Join-Path $Receipts "VERIFY_R36_RUNTIME_RECEIPT.json"
$verifyReceipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $verifyReceiptPath
Write-Host "HANRI_R36_RUNTIME_VERIFY_PASS"
Write-Host "FAST_PATH_TOTAL_MS $($run.fast_path_total_observed_ms)"
Write-Host "RECEIPT $verifyReceiptPath"
