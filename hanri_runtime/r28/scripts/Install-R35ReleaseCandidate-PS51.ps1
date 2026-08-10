param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R33TaskName = "ControlCenter-HANRI-R33",
    [string]$R35TaskName = "ControlCenter-HANRI-R35"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR35"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$R33StateRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR33\state"
$ConfigSource = Join-Path $SourceRoot "config\r35.windows.json"
$ExpectedBranch = "hanri/r35-sqlite-release-candidate"
$ExpectedDigestIdentity = "HANRI R35"
$ForbiddenDigestIdentity = "HANRI R33"
$ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"
$ExpectedHeartbeatPolicy = "32.0.0-heartbeat-fast-path-v1"
$ExpectedIntegrityPolicy = "35.0.0-steady-integrity-inherited-v1"
$ExpectedIntegrityMode = "STREAMING_SHA256_NO_JSON_PARSE"
$ExpectedScanPolicy = "33.0.0-scandir-metadata-cache-v1"
$ExpectedScanEngine = "OS_SCANDIR_SINGLE_STAT_CACHE_REUSE"
$ExpectedInventoryPolicy = "35.0.0-sqlite-bulk-index-v1"
$ExpectedInventoryEngine = "SQLITE_BULK_INDEX_SNAPSHOT_CHANGED_ROW_UPSERT"
$ExpectedProjectionRetryPolicy = "33.0.0-drive-atomic-replace-retry-v1"
$SchedulerRunningResult = 267009
$SchedulerExecutionLimitMinutes = 20
$SchedulerGateTimeoutMinutes = 21

function GitValue([string[]]$Arguments) {
    $value = & git -C $SourceRoot @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
    return ($value | Out-String).Trim()
}

function Wait-TaskStopped([string]$TaskName, [int]$TimeoutSeconds) {
    $Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if (-not $Task -or $Task.State -ne "Running") { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Read-InventoryVerification([string]$DbPath, [string]$SeedPath, [string]$PythonPath) {
    $OldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $PythonPath
        $Text = (& $Python -m hanri.sqlite_inventory_admin --db $DbPath --seed-json $SeedPath | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { throw "R35 SQLite inventory verifier failed" }
        return ($Text | ConvertFrom-Json)
    }
    finally {
        $env:PYTHONPATH = $OldPythonPath
    }
}

function Assert-HeavyRawHashes($Projection, [string]$StateRootPath) {
    foreach ($Name in @("latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json")) {
        $Path = Join-Path $StateRootPath $Name
        if (-not (Test-Path $Path)) { throw "R35 heavy state missing: $Name" }
        $Expected = $Projection.heavy_snapshot_raw_sha256.$Name
        if ([string]::IsNullOrWhiteSpace([string]$Expected)) { throw "R35 heavy SHA checkpoint missing: $Name" }
        $Actual = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Actual -ne ([string]$Expected).ToLowerInvariant()) { throw "R35 heavy SHA mismatch: $Name" }
    }
}

function Assert-BaseSafety($Run, $State, [string]$FirstLine, $Projection) {
    if ($Run.program_version -ne "35.0.0") { throw "R35 run receipt version mismatch" }
    if ($Run.can_trade -ne $false) { throw "R35 run receipt can_trade invariant failed" }
    if ($Run.self_application -ne $false) { throw "R35 run receipt self_application invariant failed" }
    if ([int]$Run.external_model_api_calls -ne 0) { throw "R35 run receipt external API invariant failed" }
    if ($State.program_version -ne "35.0.0") { throw "R35 AI-state version mismatch" }
    if ($State.shadow_only -ne $true) { throw "R35 AI-state shadow_only invariant failed" }
    if ($State.invariants.can_trade -ne $false) { throw "R35 AI-state can_trade invariant failed" }
    if ($State.invariants.self_application -ne $false) { throw "R35 AI-state self_application invariant failed" }
    if ([int]$State.invariants.external_model_api_calls -ne 0) { throw "R35 AI-state external API invariant failed" }
    if ($State.invariants.source_repository_writes -ne $false) { throw "R35 source repository write invariant failed" }
    if (-not $FirstLine.Contains($ExpectedDigestIdentity) -or $FirstLine.Contains($ForbiddenDigestIdentity)) { throw "R35 human digest identity mismatch" }
    if ($Projection.program_version -ne "35.0.0") { throw "R35 projection receipt version mismatch" }
    if ($Projection.self_projection_excluded_from_archive -ne $true) { throw "R35 self-projection exclusion invariant failed" }
    if ($Projection.can_trade -ne $false) { throw "R35 projection can_trade invariant failed" }
    if ($Projection.self_application -ne $false) { throw "R35 projection self_application invariant failed" }
    if ([int]$Projection.external_model_api_calls -ne 0) { throw "R35 projection external API invariant failed" }
    if ($Projection.material_policy.version -ne $ExpectedMaterialPolicy) { throw "R35 inherited material policy mismatch" }
    if ($Projection.material_policy.heartbeat_fast_path_policy -ne $ExpectedHeartbeatPolicy) { throw "R35 heartbeat policy mismatch" }
    if ($Projection.material_policy.archive_scan_policy_version -ne $ExpectedScanPolicy) { throw "R35 scan policy mismatch" }
    if ($Projection.material_policy.archive_scan_engine -ne $ExpectedScanEngine) { throw "R35 scan engine mismatch" }
    if ($Projection.material_policy.archive_inventory_backend -ne "SQLITE") { throw "R35 SQLite inventory backend missing" }
    if ($Projection.material_policy.archive_inventory_policy_version -ne $ExpectedInventoryPolicy) { throw "R35 inventory policy mismatch" }
    if ($Projection.material_policy.archive_inventory_engine -ne $ExpectedInventoryEngine) { throw "R35 inventory engine mismatch" }
    if ($Projection.material_policy.archive_inventory_bulk_index_snapshot -ne $true) { throw "R35 bulk inventory snapshot policy missing" }
    if ($Projection.material_policy.archive_inventory_changed_row_upsert_only -ne $true) { throw "R35 changed-row upsert policy missing" }
    if ($Projection.material_policy.archive_inventory_seed_json_preserved -ne $true) { throw "R35 seed JSON preservation policy missing" }
    if ($Projection.material_policy.archive_inventory_monolithic_json_rewrite -ne $false) { throw "R35 monolithic JSON rewrite denial missing" }
    if ($Projection.material_policy.archive_inventory_direct_json_fallback -ne $false) { throw "R35 direct JSON fallback denial missing" }
    if ($Projection.material_policy.archive_inventory_migration_requires_logical_sha_parity -ne $true) { throw "R35 migration parity policy missing" }
    if ($Projection.material_policy.archive_inventory_sqlite_quick_check_required -ne $true) { throw "R35 SQLite integrity policy missing" }
    if ($Projection.material_policy.projection_atomic_replace_policy -ne $ExpectedProjectionRetryPolicy) { throw "R35 projection atomic-replace retry policy mismatch" }
    if ($Projection.material_policy.projection_atomic_replace_retry_bounded -ne $true) { throw "R35 bounded projection retry invariant missing" }
    if ($Projection.material_policy.projection_atomic_replace_direct_overwrite -ne $false) { throw "R35 projection direct-overwrite denial missing" }
    if ($Projection.material_policy.fast_path_streaming_sha256_integrity -ne $true) { throw "R35 streaming integrity policy missing" }
    if ($Projection.material_policy.heavy_json_parse_required_on_fast_path -ne $false) { throw "R35 fast-path JSON parse policy mismatch" }
    if ($Projection.integrity_policy_version -ne $ExpectedIntegrityPolicy) { throw "R35 integrity policy mismatch" }
    if ($Projection.heavy_snapshot_integrity_mode -ne $ExpectedIntegrityMode) { throw "R35 integrity mode mismatch" }
    if (-not $Projection.heavy_snapshot_raw_sha256) { throw "R35 raw heavy SHA checkpoint missing" }
}

function Read-R35Runtime([string]$RunReceiptPath, [string]$AiStatePath, [string]$DigestPath, [string]$ProjectionReceiptPath) {
    foreach ($Path in @($RunReceiptPath, $AiStatePath, $DigestPath, $ProjectionReceiptPath)) {
        if (-not (Test-Path $Path)) { throw "R35 readback missing: $Path" }
    }
    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Digest = Get-Content $DigestPath -Raw
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $FirstLine = (($Digest -split "`r?`n", 2)[0])
    Assert-BaseSafety $Run $State $FirstLine $Projection
    Assert-HeavyRawHashes $Projection $StateRoot
    return [pscustomobject]@{ Run=$Run; State=$State; Projection=$Projection; FirstLine=$FirstLine }
}

function Assert-FullMaterialReadback($Runtime, [string]$CausalPath, [string]$ScopePath, $InventoryVerification) {
    if ($Runtime.Run.heartbeat_fast_path -eq $true) { throw "R35 first/direct run unexpectedly used heartbeat fast path" }
    if ($Runtime.Projection.heartbeat_fast_path -eq $true) { throw "R35 first/direct projection unexpectedly marked fast path" }
    if ($Runtime.Projection.material_state_reused -eq $true) { throw "R35 first/direct material state unexpectedly marked reused" }
    if ($Runtime.Projection.ai_state_run_envelope.run_id -ne $Runtime.Run.run_id) { throw "R35 full run envelope run_id mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.source_sha256 -ne $Runtime.Run.state_sha256) { throw "R35 full run state SHA mismatch" }
    if (-not $Runtime.Projection.archive_scan_checkpoint.generated_at) { throw "R35 full run archive checkpoint missing" }
    if (-not $Runtime.Projection.archive_scan_runtime_metrics) { throw "R35 full run scan metrics missing" }
    $Metrics = $Runtime.Projection.archive_scan_runtime_metrics
    if ($Metrics.scan_engine -ne $ExpectedScanEngine) { throw "R35 runtime scan engine mismatch" }
    if ($Metrics.scan_policy_version -ne $ExpectedScanPolicy) { throw "R35 runtime scan policy mismatch" }
    if ($Metrics.inventory_backend -ne "SQLITE") { throw "R35 runtime inventory backend mismatch" }
    if ($Metrics.inventory_storage_policy_version -ne $ExpectedInventoryPolicy) { throw "R35 runtime inventory policy mismatch" }
    if ($Metrics.inventory_storage_engine -ne $ExpectedInventoryEngine) { throw "R35 runtime inventory engine mismatch" }
    if ($Metrics.sqlite_bulk_index_snapshot -ne $true) { throw "R35 runtime did not use bulk SQLite index snapshot" }
    if ($Metrics.sqlite_migration_performed -ne $true) { throw "R35 direct run did not perform one-time SQLite migration" }
    if ($Metrics.sqlite_migration_parity_verified -ne $true) { throw "R35 SQLite migration parity was not verified" }
    if ($Metrics.sqlite_seed_json_preserved -ne $true) { throw "R35 SQLite seed JSON preservation missing" }
    if ($Metrics.sqlite_monolithic_json_rewrite -ne $false) { throw "R35 monolithic JSON rewrite occurred" }
    if ($Metrics.sqlite_direct_json_fallback -ne $false) { throw "R35 direct JSON fallback occurred" }
    if ([int]$Metrics.files_seen -le 0) { throw "R35 runtime scan files_seen invalid" }
    if ([int]$Metrics.cache_hits -le 0) { throw "R35 runtime scan did not reuse migrated cache" }

    $Causal = Get-Content $CausalPath -Raw | ConvertFrom-Json
    $Scope = Get-Content $ScopePath -Raw | ConvertFrom-Json
    if ($Scope.status -ne "COMPLETE") { throw "R35 scope certificate is not COMPLETE" }
    if ([double]$Scope.coverage_percent -ne 100.0) { throw "R35 scope coverage is not 100 percent" }
    $ExpectedDenominator = [int]$Causal.origin_files_seen + [int]$Causal.pivot_files_seen + [int]$Causal.current_files_seen
    if ([int]$Scope.denominator -ne $ExpectedDenominator) { throw "R35 scope denominator mismatch" }
    if ([int]$Metrics.files_seen -ne $ExpectedDenominator) { throw "R35 scan metrics/files scope mismatch" }
    if ([int]$InventoryVerification.entry_count -ne $ExpectedDenominator) { throw "R35 SQLite entry count/scope mismatch" }
    $SelfRows = @($Scope.files | Where-Object { [string]$_.path -match "HANRI_R35" })
    if ($SelfRows.Count -ne 0) { throw "R35 self projection leaked into archive scope" }
    $PredecessorRows = @($Scope.files | Where-Object { [string]$_.path -match "HANRI_R33" })
    if ($PredecessorRows.Count -eq 0) { throw "R35 predecessor R33 evidence is missing from narrow archive scope" }
    if ($InventoryVerification.status -ne "PASS") { throw "R35 independent SQLite inventory verification failed" }
    if ($InventoryVerification.quick_check -ne "ok") { throw "R35 SQLite quick_check did not pass" }
    if ($InventoryVerification.migration_parity_verified -ne $true) { throw "R35 migration parity metadata missing" }
    if ($InventoryVerification.seed_json_preserved -ne $true) { throw "R35 seed JSON preservation metadata missing" }
}

function Assert-FastHeartbeatReadback($Runtime, [string]$DirectMaterialRunId) {
    if ($Runtime.Run.heartbeat_fast_path -ne $true) { throw "R35 scheduled run did not use heartbeat fast path" }
    if ($Runtime.Run.fast_path_integrity_verified -ne $true) { throw "R35 scheduled fast-path integrity was not verified" }
    if ($Runtime.Run.material_state_reused -ne $true) { throw "R35 scheduled run did not mark material state reuse" }
    if ($Runtime.Run.material_state_run_id -ne $DirectMaterialRunId) { throw "R35 scheduled heartbeat did not reuse direct material run" }
    if ($Runtime.Projection.heartbeat_fast_path -ne $true) { throw "R35 scheduled projection did not mark fast path" }
    if ($Runtime.Projection.material_state_reused -ne $true) { throw "R35 scheduled projection did not mark material state reuse" }
    if ($Runtime.Projection.ai_state_run_envelope.run_id -ne $Runtime.Run.run_id) { throw "R35 fast envelope run_id mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.source_sha256 -ne $Runtime.Run.state_sha256) { throw "R35 fast envelope state SHA mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.shadow_only -ne $true) { throw "R35 fast envelope shadow_only invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.can_trade -ne $false) { throw "R35 fast envelope can_trade invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.self_application -ne $false) { throw "R35 fast envelope self_application invariant failed" }
    if ([int]$Runtime.Projection.ai_state_run_envelope.external_model_api_calls -ne 0) { throw "R35 fast envelope external API invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.source_repository_writes -ne $false) { throw "R35 fast envelope repository-write invariant failed" }
}

$Head = GitValue @("rev-parse", "HEAD")
$Branch = GitValue @("branch", "--show-current")
$Dirty = GitValue @("status", "--porcelain")
if ($Branch -ne $ExpectedBranch) { throw "Install gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "Install gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "Install gate: -ExpectedCommit is required with -Apply" }
if ($Apply -and $Head -ne $ExpectedCommit) { throw "Install gate: HEAD $Head does not match expected $ExpectedCommit" }

$ConfigObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "35.0.0") { throw "Config gate: program_version must be 35.0.0" }
if ($ConfigObject.shadow_only -ne $true) { throw "Config gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "Config gate: external_model_api must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "Config gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR35") { throw "Config gate: R35 state must be isolated" }
if ($ConfigObject.human_output_root -notmatch "HANRI_R35") { throw "Config gate: R35 Drive output must be isolated" }

$R33Task = Get-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
if (-not $R33Task) { throw "Promotion gate: accepted R33 task not found: $R33TaskName" }
$R33WasEnabled = [bool]($R33Task.State -ne "Disabled")
if (-not $R33WasEnabled) { throw "Promotion gate: accepted R33 task is not enabled" }
$R33CachePath = Join-Path $R33StateRoot "archive_inventory_cache.json"
if (-not (Test-Path $R33CachePath)) { throw "Promotion gate: accepted R33 inventory cache missing" }

Write-Host "HANRI R35 SQLite side-by-side release install gate (PS5.1 safe)"
Write-Host "Source:  $SourceRoot"
Write-Host "HEAD:    $Head"
Write-Host "Install: $InstallRoot"
Write-Host "Accepted R33 remains enabled until R35 migration/full scope/integrity plus fast scheduled readback pass."
if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

$ExistingR35Task = Get-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
if ($ExistingR35Task) {
    Disable-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($ExistingR35Task.State -eq "Running") { Stop-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue }
    if (-not (Wait-TaskStopped $R35TaskName 60)) { throw "Recovery gate: previous R35 task did not stop within 60 seconds" }
}

New-Item -ItemType Directory -Force -Path $InstallBase, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousR35AppBackup = $null
$PreviousR35StateBackup = $null
if (Test-Path $InstallRoot) {
    $PreviousR35AppBackup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousR35AppBackup
}
if (Test-Path $StateRoot) {
    $PreviousR35StateBackup = "$StateRoot.backup.$Timestamp"
    Move-Item -Force $StateRoot $PreviousR35StateBackup
}
New-Item -ItemType Directory -Force -Path $InstallRoot, $StateRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot
$SeedCachePath = Join-Path $StateRoot "archive_inventory_cache.json"
Copy-Item -Force $R33CachePath $SeedCachePath
$SeedCacheSha = (Get-FileHash $SeedCachePath -Algorithm SHA256).Hash.ToLowerInvariant()
$R33SeedSha = (Get-FileHash $R33CachePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($SeedCacheSha -ne $R33SeedSha) { throw "R35 seed copy SHA mismatch" }

$Config = Join-Path $InstallRoot "config\r35.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ProjectionReceiptPath = Join-Path $StateRoot "latest_projection_receipt.json"
$CausalPath = Join-Path $StateRoot "latest_archive_causal_spine.json"
$ScopePath = Join-Path $StateRoot "latest_archive_scope_certificate.json"
$DbPath = Join-Path $StateRoot "archive_inventory_cache.sqlite3"
$env:PYTHONPATH = $PythonPath

try {
    Set-Location $InstallRoot
    & $Python -m compileall -q (Join-Path $InstallRoot "src")
    if ($LASTEXITCODE -ne 0) { throw "R35 compile check failed with exit code $LASTEXITCODE" }

    $DirectStarted = [DateTime]::UtcNow
    & $Python -m hanri once --config $Config
    if ($LASTEXITCODE -ne 0) { throw "R35 direct full one-shot failed with exit code $LASTEXITCODE" }
    if (-not (Test-Path $DbPath)) { throw "R35 SQLite DB was not created by direct run" }
    if ((Get-FileHash $SeedCachePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $SeedCacheSha) { throw "R35 seed JSON changed during direct run" }
    $InventoryVerification = Read-InventoryVerification $DbPath $SeedCachePath $PythonPath
    $DirectRuntime = Read-R35Runtime $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    Assert-FullMaterialReadback $DirectRuntime $CausalPath $ScopePath $InventoryVerification
    $DirectElapsedSeconds = [int]([DateTime]::UtcNow - $DirectStarted).TotalSeconds
    $DirectMaterialRunId = [string]$DirectRuntime.Run.run_id
    $DirectScanMetrics = $DirectRuntime.Projection.archive_scan_runtime_metrics
    $DirectScope = Get-Content $ScopePath -Raw | ConvertFrom-Json
    $DirectDbSha = (Get-FileHash $DbPath -Algorithm SHA256).Hash.ToLowerInvariant()

    $Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
    $TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes $SchedulerExecutionLimitMinutes)
    Register-ScheduledTask -TaskName $R35TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R35 bounded shadow supervisor; SQLite bulk inventory with inherited R33 scandir/integrity" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R35TaskName | Out-Null

    $BeforeRunWrite = (Get-Item $RunReceiptPath).LastWriteTimeUtc
    $BeforeProjectionWrite = (Get-Item $ProjectionReceiptPath).LastWriteTimeUtc
    $SchedulerDeadline = [DateTime]::UtcNow.AddMinutes($SchedulerGateTimeoutMinutes)
    $RunUpdated = $false
    $ProjectionUpdated = $false
    $TaskCompleted = $false
    Start-ScheduledTask -TaskName $R35TaskName
    while ([DateTime]::UtcNow -lt $SchedulerDeadline) {
        Start-Sleep -Seconds 2
        if ((Test-Path $RunReceiptPath) -and ((Get-Item $RunReceiptPath).LastWriteTimeUtc -gt $BeforeRunWrite)) { $RunUpdated = $true }
        if ((Test-Path $ProjectionReceiptPath) -and ((Get-Item $ProjectionReceiptPath).LastWriteTimeUtc -gt $BeforeProjectionWrite)) { $ProjectionUpdated = $true }
        $TaskState = (Get-ScheduledTask -TaskName $R35TaskName -ErrorAction Stop).State
        if ($RunUpdated -and $ProjectionUpdated -and $TaskState -ne "Running") { $TaskCompleted = $true; break }
    }
    if (-not $RunUpdated) { throw "R35 scheduled task did not produce a fresh run receipt within gate window" }
    if (-not $ProjectionUpdated) { throw "R35 scheduled task did not produce a fresh projection receipt within gate window" }
    if (-not $TaskCompleted) { throw "R35 scheduled task did not complete within gate window" }

    $ScheduledRuntime = Read-R35Runtime $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    Assert-FastHeartbeatReadback $ScheduledRuntime $DirectMaterialRunId
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R35TaskName
    if ($TaskInfo.LastTaskResult -eq $SchedulerRunningResult) { throw "R35 scheduler completion race: LastTaskResult still reports SCHED_S_TASK_RUNNING" }
    if ($TaskInfo.LastTaskResult -ne 0) { throw "R35 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }
    if ((Get-FileHash $SeedCachePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $SeedCacheSha) { throw "R35 seed JSON changed during scheduled heartbeat" }
    if ((Get-FileHash $DbPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $DirectDbSha) { throw "R35 fast heartbeat unexpectedly changed SQLite DB" }
    $ScheduledInventoryVerification = Read-InventoryVerification $DbPath $SeedCachePath $PythonPath
    if ($ScheduledInventoryVerification.status -ne "PASS") { throw "R35 scheduled SQLite inventory verification failed" }

    Disable-ScheduledTask -TaskName $R33TaskName | Out-Null

    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R35_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        r35_task = $R35TaskName
        r35_last_task_result = $TaskInfo.LastTaskResult
        direct_full_material_run_id = $DirectMaterialRunId
        direct_full_elapsed_seconds = $DirectElapsedSeconds
        direct_scan_metrics = $DirectScanMetrics
        direct_scope_denominator = [int]$DirectScope.denominator
        direct_scope_manifest_sha256 = [string]$DirectScope.scope_manifest_sha256
        seeded_r33_inventory_cache_sha256 = $SeedCacheSha
        sqlite_db_sha256_after_direct = $DirectDbSha
        sqlite_inventory_verification = $InventoryVerification
        scheduled_fast_run_id = [string]$ScheduledRuntime.Run.run_id
        scheduled_fast_path_verified = $true
        scheduled_fast_integrity_verified = $true
        scheduled_fast_path_elapsed_ms = $ScheduledRuntime.Run.fast_path_elapsed_ms
        scheduled_heavy_snapshot_bytes_hashed = $ScheduledRuntime.Run.heavy_snapshot_bytes_hashed
        scheduled_sqlite_db_unchanged = $true
        r33_task = $R33TaskName
        r33_was_enabled = $R33WasEnabled
        r33_disabled_only_after_r35_full_scope_sqlite_and_fast_readback = $true
        r33_files_modified = $false
        r33_state_modified_by_installer = $false
        previous_r35_app_backup = $PreviousR35AppBackup
        previous_r35_state_backup = $PreviousR35StateBackup
        digest_identity = "HANRI R35"
        scan_policy = $ExpectedScanPolicy
        scan_engine = $ExpectedScanEngine
        inventory_policy = $ExpectedInventoryPolicy
        inventory_engine = $ExpectedInventoryEngine
        projection_atomic_replace_policy = $ExpectedProjectionRetryPolicy
        integrity_mode = $ExpectedIntegrityMode
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R33FromR35.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R35_RC1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 16 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R35 RC1 installed side-by-side; verified SQLite migration, full scope and fast heartbeat readbacks passed."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "Accepted R33 files/state were not modified; R33 task was disabled only after R35 PASS."
}
catch {
    Disable-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
    if ($R33WasEnabled) { Enable-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
