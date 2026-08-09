param(
    [string]$TaskName = "ControlCenter-HANRI-R32"
)

$ErrorActionPreference = "Stop"
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR32"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$Config = Join-Path $InstallRoot "config\r32.windows.json"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ProjectionReceiptPath = Join-Path $StateRoot "latest_projection_receipt.json"
$ExpectedDigestIdentity = "HANRI R32"
$ForbiddenDigestIdentity = "HANRI R31"
$ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"
$ExpectedHeartbeatPolicy = "32.0.0-heartbeat-fast-path-v1"
$ExpectedIntegrityPolicy = "32.0.0-steady-integrity-v1"
$ExpectedIntegrityMode = "STREAMING_SHA256_NO_JSON_PARSE"

$Checks = [ordered]@{}
$Checks.install_root_exists = Test-Path $InstallRoot
$Checks.config_exists = Test-Path $Config
$Checks.run_receipt_exists = Test-Path $RunReceiptPath
$Checks.ai_state_exists = Test-Path $AiStatePath
$Checks.human_digest_exists = Test-Path $DigestPath
$Checks.projection_receipt_exists = Test-Path $ProjectionReceiptPath
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Checks.task_exists = [bool]$Task
$Checks.task_enabled = [bool]($Task -and $Task.State -ne "Disabled")

if ($Checks.config_exists) {
    $ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
    $Checks.config_program_version = ($ConfigObject.program_version -eq "32.0.0")
    $Checks.config_shadow_only = ($ConfigObject.shadow_only -eq $true)
    $Checks.config_external_model_api_deny = ($ConfigObject.external_model_api -eq "DENY")
    $Checks.config_can_trade_false = ($ConfigObject.can_trade -eq $false)
    $Checks.config_state_isolated = ($ConfigObject.state_root -match "ControlCenterHANRIR32")
    $Checks.config_drive_output_isolated = ($ConfigObject.human_output_root -match "HANRI_R32")
}

$Run = $null
$State = $null
$Projection = $null
if ($Checks.run_receipt_exists) {
    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $Checks.receipt_program_version = ($Run.program_version -eq "32.0.0")
    $Checks.receipt_self_application_false = ($Run.self_application -eq $false)
    $Checks.receipt_can_trade_false = ($Run.can_trade -eq $false)
    $Checks.receipt_external_api_zero = ([int]$Run.external_model_api_calls -eq 0)
    $Checks.receipt_fast_path_true = ($Run.heartbeat_fast_path -eq $true)
    $Checks.receipt_integrity_verified = ($Run.fast_path_integrity_verified -eq $true)
    $Checks.receipt_material_state_reused = ($Run.material_state_reused -eq $true)
    $Checks.receipt_material_state_run_id_present = (-not [string]::IsNullOrWhiteSpace([string]$Run.material_state_run_id))
    $Checks.receipt_integrity_mode = ($Run.heavy_snapshot_integrity_mode -eq $ExpectedIntegrityMode)
    $Checks.receipt_heavy_bytes_hashed_positive = ([int64]$Run.heavy_snapshot_bytes_hashed -gt 0)
}

if ($Checks.ai_state_exists) {
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Checks.state_program_version = ($State.program_version -eq "32.0.0")
    $Checks.state_shadow_only = ($State.shadow_only -eq $true)
    $Checks.state_self_application_false = ($State.invariants.self_application -eq $false)
    $Checks.state_can_trade_false = ($State.invariants.can_trade -eq $false)
    $Checks.state_external_api_zero = ([int]$State.invariants.external_model_api_calls -eq 0)
    $Checks.state_repo_writes_false = ($State.invariants.source_repository_writes -eq $false)
}

if ($Checks.human_digest_exists) {
    $Digest = Get-Content $DigestPath -Raw
    $FirstLine = (($Digest -split "`r?`n", 2)[0])
    $Checks.digest_identifies_r32 = ($FirstLine.Contains($ExpectedDigestIdentity))
    $Checks.digest_does_not_identify_r31 = (-not $FirstLine.Contains($ForbiddenDigestIdentity))
    if ($Run) { $Checks.digest_run_id_current = ($Digest.Contains("Run: ``$($Run.run_id)``")) }
}

if ($Checks.projection_receipt_exists) {
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $Checks.projection_program_version = ($Projection.program_version -eq "32.0.0")
    $Checks.projection_self_exclusion_true = ($Projection.self_projection_excluded_from_archive -eq $true)
    $Checks.projection_self_application_false = ($Projection.self_application -eq $false)
    $Checks.projection_can_trade_false = ($Projection.can_trade -eq $false)
    $Checks.projection_external_api_zero = ([int]$Projection.external_model_api_calls -eq 0)
    $Checks.projection_fast_path_true = ($Projection.heartbeat_fast_path -eq $true)
    $Checks.projection_material_state_reused = ($Projection.material_state_reused -eq $true)
    $Checks.projection_material_policy = ($Projection.material_policy.version -eq $ExpectedMaterialPolicy)
    $Checks.projection_heartbeat_policy = ($Projection.material_policy.heartbeat_fast_path_policy -eq $ExpectedHeartbeatPolicy)
    $Checks.projection_integrity_policy = ($Projection.integrity_policy_version -eq $ExpectedIntegrityPolicy)
    $Checks.projection_integrity_mode = ($Projection.heavy_snapshot_integrity_mode -eq $ExpectedIntegrityMode)
    $Checks.projection_streaming_integrity_true = ($Projection.material_policy.fast_path_streaming_sha256_integrity -eq $true)
    $Checks.projection_no_heavy_json_parse = ($Projection.material_policy.heavy_json_parse_required_on_fast_path -eq $false)
    $Checks.projection_archive_checkpoint_present = (-not [string]::IsNullOrWhiteSpace([string]$Projection.archive_scan_checkpoint.generated_at))
    $Envelope = $Projection.ai_state_run_envelope
    $Checks.envelope_exists = [bool]$Envelope
    if ($Envelope -and $Run) {
        $Checks.envelope_run_id_current = ($Envelope.run_id -eq $Run.run_id)
        $Checks.envelope_state_sha_matches_run = ($Envelope.source_sha256 -eq $Run.state_sha256)
        $Checks.envelope_material_state_run_id_matches = ($Envelope.material_state_run_id -eq $Run.material_state_run_id)
        $Checks.envelope_shadow_only = ($Envelope.shadow_only -eq $true)
        $Checks.envelope_self_application_false = ($Envelope.self_application -eq $false)
        $Checks.envelope_can_trade_false = ($Envelope.can_trade -eq $false)
        $Checks.envelope_external_api_zero = ([int]$Envelope.external_model_api_calls -eq 0)
        $Checks.envelope_repo_writes_false = ($Envelope.source_repository_writes -eq $false)
    }

    $RawMap = $Projection.heavy_snapshot_raw_sha256
    $Checks.heavy_raw_sha_map_present = [bool]$RawMap
    foreach ($Name in @("latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json")) {
        $Path = Join-Path $StateRoot $Name
        $Key = "heavy_raw_sha_" + ($Name -replace '[^A-Za-z0-9]', '_')
        if ((Test-Path $Path) -and $RawMap) {
            $Expected = $RawMap.$Name
            $Actual = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
            $Checks[$Key] = (-not [string]::IsNullOrWhiteSpace([string]$Expected) -and $Actual -eq ([string]$Expected).ToLowerInvariant())
        } else {
            $Checks[$Key] = $false
        }
    }
}

$Failed = @($Checks.GetEnumerator() | Where-Object { $_.Value -ne $true } | ForEach-Object { $_.Key })
$Status = if ($Failed.Count -eq 0) { "PASS" } else { "FAIL" }
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$Receipt = [ordered]@{
    schema_version = 1
    status = $Status
    release = "HANRI_R32_RC1"
    verified_at_utc = [DateTime]::UtcNow.ToString("o")
    checks = $Checks
    failed_checks = $Failed
    task_name = $TaskName
    current_run_id = if ($Run) { $Run.run_id } else { $null }
    material_state_run_id = if ($Run) { $Run.material_state_run_id } else { $null }
    run_receipt_sha256 = if (Test-Path $RunReceiptPath) { (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    ai_state_sha256 = if (Test-Path $AiStatePath) { (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    human_digest_sha256 = if (Test-Path $DigestPath) { (Get-FileHash $DigestPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    projection_receipt_sha256 = if (Test-Path $ProjectionReceiptPath) { (Get-FileHash $ProjectionReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    self_application = $false
    can_trade = $false
}
$ReceiptPath = Join-Path $ReceiptRoot "R32_RUNTIME_READBACK_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ReceiptPath
$Receipt | ConvertTo-Json -Depth 12
if ($Status -ne "PASS") { exit 2 }
