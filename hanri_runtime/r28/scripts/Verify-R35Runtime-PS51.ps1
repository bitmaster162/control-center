param(
    [string]$TaskName = "ControlCenter-HANRI-R35",
    [string]$R33TaskName = "ControlCenter-HANRI-R33",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR35"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$Config = Join-Path $InstallRoot "config\r35.windows.json"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ProjectionReceiptPath = Join-Path $StateRoot "latest_projection_receipt.json"
$CausalPath = Join-Path $StateRoot "latest_archive_causal_spine.json"
$ScopePath = Join-Path $StateRoot "latest_archive_scope_certificate.json"
$SeedPath = Join-Path $StateRoot "archive_inventory_cache.json"
$DbPath = Join-Path $StateRoot "archive_inventory_cache.sqlite3"
$InstallReceiptPath = Join-Path $ReceiptRoot "INSTALL_R35_RC1_RECEIPT.json"
$ExpectedIntegrityMode = "STREAMING_SHA256_NO_JSON_PARSE"
$ExpectedIntegrityPolicy = "35.0.0-steady-integrity-inherited-v1"
$ExpectedScanPolicy = "33.0.0-scandir-metadata-cache-v1"
$ExpectedScanEngine = "OS_SCANDIR_SINGLE_STAT_CACHE_REUSE"
$ExpectedInventoryPolicy = "35.0.0-sqlite-bulk-index-v1"
$ExpectedInventoryEngine = "SQLITE_BULK_INDEX_SNAPSHOT_CHANGED_ROW_UPSERT"
$ExpectedProjectionRetryPolicy = "33.0.0-drive-atomic-replace-retry-v1"

$Checks = [ordered]@{}
$Checks.install_root_exists = Test-Path $InstallRoot
$Checks.config_exists = Test-Path $Config
$Checks.run_receipt_exists = Test-Path $RunReceiptPath
$Checks.ai_state_exists = Test-Path $AiStatePath
$Checks.human_digest_exists = Test-Path $DigestPath
$Checks.projection_receipt_exists = Test-Path $ProjectionReceiptPath
$Checks.causal_spine_exists = Test-Path $CausalPath
$Checks.scope_certificate_exists = Test-Path $ScopePath
$Checks.seed_json_exists = Test-Path $SeedPath
$Checks.sqlite_db_exists = Test-Path $DbPath
$Checks.install_receipt_exists = Test-Path $InstallReceiptPath
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Checks.task_exists = [bool]$Task
$Checks.task_enabled = [bool]($Task -and $Task.State -ne "Disabled")
$R33Task = Get-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
$Checks.r33_task_exists = [bool]$R33Task
$Checks.r33_disabled_after_cutover = [bool]($R33Task -and $R33Task.State -eq "Disabled")

if ($Checks.config_exists) {
    $ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
    $Checks.config_program_version = ($ConfigObject.program_version -eq "35.0.0")
    $Checks.config_shadow_only = ($ConfigObject.shadow_only -eq $true)
    $Checks.config_external_model_api_deny = ($ConfigObject.external_model_api -eq "DENY")
    $Checks.config_can_trade_false = ($ConfigObject.can_trade -eq $false)
    $Checks.config_state_isolated = ($ConfigObject.state_root -match "ControlCenterHANRIR35")
    $Checks.config_drive_output_isolated = ($ConfigObject.human_output_root -match "HANRI_R35")
}

$Run = $null
$State = $null
$Projection = $null
if ($Checks.run_receipt_exists) {
    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $Checks.receipt_program_version = ($Run.program_version -eq "35.0.0")
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
    $Checks.state_program_version = ($State.program_version -eq "35.0.0")
    $Checks.state_shadow_only = ($State.shadow_only -eq $true)
    $Checks.state_self_application_false = ($State.invariants.self_application -eq $false)
    $Checks.state_can_trade_false = ($State.invariants.can_trade -eq $false)
    $Checks.state_external_api_zero = ([int]$State.invariants.external_model_api_calls -eq 0)
    $Checks.state_repo_writes_false = ($State.invariants.source_repository_writes -eq $false)
}

if ($Checks.human_digest_exists) {
    $Digest = Get-Content $DigestPath -Raw
    $FirstLine = (($Digest -split "`r?`n", 2)[0])
    $Checks.digest_identifies_r35 = ($FirstLine.Contains("HANRI R35"))
    $Checks.digest_does_not_identify_r33 = (-not $FirstLine.Contains("HANRI R33"))
    if ($Run) { $Checks.digest_run_id_current = ($Digest.Contains("Run: ``$($Run.run_id)``")) }
}

if ($Checks.projection_receipt_exists) {
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $Checks.projection_program_version = ($Projection.program_version -eq "35.0.0")
    $Checks.projection_self_exclusion_true = ($Projection.self_projection_excluded_from_archive -eq $true)
    $Checks.projection_self_application_false = ($Projection.self_application -eq $false)
    $Checks.projection_can_trade_false = ($Projection.can_trade -eq $false)
    $Checks.projection_external_api_zero = ([int]$Projection.external_model_api_calls -eq 0)
    $Checks.projection_fast_path_true = ($Projection.heartbeat_fast_path -eq $true)
    $Checks.projection_material_state_reused = ($Projection.material_state_reused -eq $true)
    $Checks.projection_scan_policy = ($Projection.material_policy.archive_scan_policy_version -eq $ExpectedScanPolicy)
    $Checks.projection_scan_engine = ($Projection.material_policy.archive_scan_engine -eq $ExpectedScanEngine)
    $Checks.projection_inventory_backend = ($Projection.material_policy.archive_inventory_backend -eq "SQLITE")
    $Checks.projection_inventory_policy = ($Projection.material_policy.archive_inventory_policy_version -eq $ExpectedInventoryPolicy)
    $Checks.projection_inventory_engine = ($Projection.material_policy.archive_inventory_engine -eq $ExpectedInventoryEngine)
    $Checks.projection_bulk_snapshot_true = ($Projection.material_policy.archive_inventory_bulk_index_snapshot -eq $true)
    $Checks.projection_changed_row_upsert_true = ($Projection.material_policy.archive_inventory_changed_row_upsert_only -eq $true)
    $Checks.projection_seed_json_preserved = ($Projection.material_policy.archive_inventory_seed_json_preserved -eq $true)
    $Checks.projection_monolithic_json_rewrite_denied = ($Projection.material_policy.archive_inventory_monolithic_json_rewrite -eq $false)
    $Checks.projection_direct_json_fallback_denied = ($Projection.material_policy.archive_inventory_direct_json_fallback -eq $false)
    $Checks.projection_migration_parity_required = ($Projection.material_policy.archive_inventory_migration_requires_logical_sha_parity -eq $true)
    $Checks.projection_sqlite_quick_check_required = ($Projection.material_policy.archive_inventory_sqlite_quick_check_required -eq $true)
    $Checks.projection_retry_policy = ($Projection.material_policy.projection_atomic_replace_policy -eq $ExpectedProjectionRetryPolicy)
    $Checks.projection_retry_bounded = ($Projection.material_policy.projection_atomic_replace_retry_bounded -eq $true)
    $Checks.projection_direct_overwrite_denied = ($Projection.material_policy.projection_atomic_replace_direct_overwrite -eq $false)
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

if ($Checks.causal_spine_exists -and $Checks.scope_certificate_exists) {
    $Causal = Get-Content $CausalPath -Raw | ConvertFrom-Json
    $Scope = Get-Content $ScopePath -Raw | ConvertFrom-Json
    $Checks.scope_complete = ($Scope.status -eq "COMPLETE")
    $Checks.scope_coverage_100 = ([double]$Scope.coverage_percent -eq 100.0)
    $ExpectedDenominator = [int]$Causal.origin_files_seen + [int]$Causal.pivot_files_seen + [int]$Causal.current_files_seen
    $Checks.scope_denominator_consistent = ([int]$Scope.denominator -eq $ExpectedDenominator)
    $Checks.scope_excludes_r35_projection = (@($Scope.files | Where-Object { [string]$_.path -match "HANRI_R35" }).Count -eq 0)
    $Checks.scope_retains_r33_predecessor = (@($Scope.files | Where-Object { [string]$_.path -match "HANRI_R33" }).Count -gt 0)
}

$InventoryVerification = $null
if ($Checks.sqlite_db_exists -and $Checks.seed_json_exists -and $Checks.install_root_exists) {
    $OldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $InstallRoot "src"
        $Text = (& $Python -m hanri.sqlite_inventory_admin --db $DbPath --seed-json $SeedPath | Out-String).Trim()
        $InventoryVerification = $Text | ConvertFrom-Json
        $Checks.sqlite_admin_pass = ($LASTEXITCODE -eq 0 -and $InventoryVerification.status -eq "PASS")
        $Checks.sqlite_quick_check_ok = ($InventoryVerification.quick_check -eq "ok")
        $Checks.sqlite_migration_parity_verified = ($InventoryVerification.migration_parity_verified -eq $true)
        $Checks.sqlite_seed_json_preserved = ($InventoryVerification.seed_json_preserved -eq $true)
    }
    finally {
        $env:PYTHONPATH = $OldPythonPath
    }
}

if ($Checks.install_receipt_exists) {
    $InstallReceipt = Get-Content $InstallReceiptPath -Raw | ConvertFrom-Json
    $Checks.install_receipt_pass = ($InstallReceipt.status -eq "PASS")
    $Checks.install_release_rc1 = ($InstallReceipt.release -eq "HANRI_R35_RC1")
    $Checks.install_scan_engine = ($InstallReceipt.scan_engine -eq $ExpectedScanEngine)
    $Checks.install_scan_policy = ($InstallReceipt.scan_policy -eq $ExpectedScanPolicy)
    $Checks.install_inventory_engine = ($InstallReceipt.inventory_engine -eq $ExpectedInventoryEngine)
    $Checks.install_inventory_policy = ($InstallReceipt.inventory_policy -eq $ExpectedInventoryPolicy)
    $Checks.install_projection_retry_policy = ($InstallReceipt.projection_atomic_replace_policy -eq $ExpectedProjectionRetryPolicy)
    $Checks.install_direct_scan_metrics_present = [bool]$InstallReceipt.direct_scan_metrics
    if ($InstallReceipt.direct_scan_metrics) {
        $Checks.install_direct_scan_files_positive = ([int]$InstallReceipt.direct_scan_metrics.files_seen -gt 0)
        $Checks.install_direct_scan_cache_hits_positive = ([int]$InstallReceipt.direct_scan_metrics.cache_hits -gt 0)
        $Checks.install_direct_scan_scope_matches = ([int]$InstallReceipt.direct_scan_metrics.files_seen -eq [int]$InstallReceipt.direct_scope_denominator)
        $Checks.install_direct_inventory_backend_sqlite = ($InstallReceipt.direct_scan_metrics.inventory_backend -eq "SQLITE")
        $Checks.install_direct_migration_parity = ($InstallReceipt.direct_scan_metrics.sqlite_migration_parity_verified -eq $true)
    }
    if ($Checks.seed_json_exists) {
        $SeedSha = (Get-FileHash $SeedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $Checks.install_seed_sha_preserved = ($SeedSha -eq ([string]$InstallReceipt.seeded_r33_inventory_cache_sha256).ToLowerInvariant())
    }
    $Checks.install_r33_not_modified = ($InstallReceipt.r33_files_modified -eq $false -and $InstallReceipt.r33_state_modified_by_installer -eq $false)
    $Checks.install_cutover_order_proven = ($InstallReceipt.r33_disabled_only_after_r35_full_scope_sqlite_and_fast_readback -eq $true)
    $Checks.install_fast_db_unchanged = ($InstallReceipt.scheduled_sqlite_db_unchanged -eq $true)
}

$Failed = @($Checks.GetEnumerator() | Where-Object { $_.Value -ne $true } | ForEach-Object { $_.Key })
$Status = if ($Failed.Count -eq 0) { "PASS" } else { "FAIL" }
New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$Receipt = [ordered]@{
    schema_version = 1
    status = $Status
    release = "HANRI_R35_RC1"
    verified_at_utc = [DateTime]::UtcNow.ToString("o")
    checks = $Checks
    failed_checks = $Failed
    task_name = $TaskName
    current_run_id = if ($Run) { $Run.run_id } else { $null }
    material_state_run_id = if ($Run) { $Run.material_state_run_id } else { $null }
    sqlite_inventory = $InventoryVerification
    self_application = $false
    can_trade = $false
}
$ReceiptPath = Join-Path $ReceiptRoot "R35_RUNTIME_READBACK_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 16 | Set-Content -Encoding UTF8 $ReceiptPath
$Receipt | ConvertTo-Json -Depth 16
if ($Status -ne "PASS") { exit 2 }
