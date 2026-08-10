param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R32TaskName = "ControlCenter-HANRI-R32",
    [string]$R33TaskName = "ControlCenter-HANRI-R33"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR33"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$R32StateRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR32\state"
$ConfigSource = Join-Path $SourceRoot "config\r33.windows.json"
$ExpectedBranch = "hanri/r33-release-candidate"
$ExpectedDigestIdentity = "HANRI R33"
$ForbiddenDigestIdentity = "HANRI R32"
$ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"
$ExpectedHeartbeatPolicy = "32.0.0-heartbeat-fast-path-v1"
$ExpectedIntegrityPolicy = "33.0.0-steady-integrity-inherited-v1"
$ExpectedIntegrityMode = "STREAMING_SHA256_NO_JSON_PARSE"
$ExpectedScanPolicy = "33.0.0-scandir-metadata-cache-v1"
$ExpectedScanEngine = "OS_SCANDIR_SINGLE_STAT_CACHE_REUSE"
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

function Assert-HeavyRawHashes($Projection, [string]$StateRootPath) {
    foreach ($Name in @("latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json")) {
        $Path = Join-Path $StateRootPath $Name
        if (-not (Test-Path $Path)) { throw "R33 heavy state missing: $Name" }
        $Expected = $Projection.heavy_snapshot_raw_sha256.$Name
        if ([string]::IsNullOrWhiteSpace([string]$Expected)) { throw "R33 heavy SHA checkpoint missing: $Name" }
        $Actual = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Actual -ne ([string]$Expected).ToLowerInvariant()) { throw "R33 heavy SHA mismatch: $Name" }
    }
}

function Assert-BaseSafety($Run, $State, [string]$FirstLine, $Projection) {
    if ($Run.program_version -ne "33.0.0") { throw "R33 run receipt version mismatch" }
    if ($Run.can_trade -ne $false) { throw "R33 run receipt can_trade invariant failed" }
    if ($Run.self_application -ne $false) { throw "R33 run receipt self_application invariant failed" }
    if ([int]$Run.external_model_api_calls -ne 0) { throw "R33 run receipt external API invariant failed" }
    if ($State.program_version -ne "33.0.0") { throw "R33 AI-state version mismatch" }
    if ($State.shadow_only -ne $true) { throw "R33 AI-state shadow_only invariant failed" }
    if ($State.invariants.can_trade -ne $false) { throw "R33 AI-state can_trade invariant failed" }
    if ($State.invariants.self_application -ne $false) { throw "R33 AI-state self_application invariant failed" }
    if ([int]$State.invariants.external_model_api_calls -ne 0) { throw "R33 AI-state external API invariant failed" }
    if ($State.invariants.source_repository_writes -ne $false) { throw "R33 source repository write invariant failed" }
    if (-not $FirstLine.Contains($ExpectedDigestIdentity) -or $FirstLine.Contains($ForbiddenDigestIdentity)) { throw "R33 human digest identity mismatch" }
    if ($Projection.program_version -ne "33.0.0") { throw "R33 projection receipt version mismatch" }
    if ($Projection.self_projection_excluded_from_archive -ne $true) { throw "R33 self-projection exclusion invariant failed" }
    if ($Projection.can_trade -ne $false) { throw "R33 projection can_trade invariant failed" }
    if ($Projection.self_application -ne $false) { throw "R33 projection self_application invariant failed" }
    if ([int]$Projection.external_model_api_calls -ne 0) { throw "R33 projection external API invariant failed" }
    if ($Projection.material_policy.version -ne $ExpectedMaterialPolicy) { throw "R33 inherited material policy mismatch" }
    if ($Projection.material_policy.heartbeat_fast_path_policy -ne $ExpectedHeartbeatPolicy) { throw "R33 heartbeat policy mismatch" }
    if ($Projection.material_policy.archive_scan_policy_version -ne $ExpectedScanPolicy) { throw "R33 scan policy mismatch" }
    if ($Projection.material_policy.archive_scan_engine -ne $ExpectedScanEngine) { throw "R33 scan engine mismatch" }
    if ($Projection.material_policy.archive_scan_cache_hit_record_reuse -ne $true) { throw "R33 cache-hit record reuse policy missing" }
    if ($Projection.material_policy.archive_scan_single_stat_metadata_path -ne $true) { throw "R33 single-stat metadata policy missing" }
    if ($Projection.material_policy.fast_path_streaming_sha256_integrity -ne $true) { throw "R33 streaming integrity policy missing" }
    if ($Projection.material_policy.heavy_json_parse_required_on_fast_path -ne $false) { throw "R33 fast-path JSON parse policy mismatch" }
    if ($Projection.integrity_policy_version -ne $ExpectedIntegrityPolicy) { throw "R33 integrity policy mismatch" }
    if ($Projection.heavy_snapshot_integrity_mode -ne $ExpectedIntegrityMode) { throw "R33 integrity mode mismatch" }
    if (-not $Projection.heavy_snapshot_raw_sha256) { throw "R33 raw heavy SHA checkpoint missing" }
}

function Read-R33Runtime([string]$RunReceiptPath, [string]$AiStatePath, [string]$DigestPath, [string]$ProjectionReceiptPath) {
    foreach ($Path in @($RunReceiptPath, $AiStatePath, $DigestPath, $ProjectionReceiptPath)) {
        if (-not (Test-Path $Path)) { throw "R33 readback missing: $Path" }
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

function Assert-FullMaterialReadback($Runtime, [string]$CausalPath, [string]$ScopePath) {
    if ($Runtime.Run.heartbeat_fast_path -eq $true) { throw "R33 first/direct run unexpectedly used heartbeat fast path" }
    if ($Runtime.Projection.heartbeat_fast_path -eq $true) { throw "R33 first/direct projection unexpectedly marked fast path" }
    if ($Runtime.Projection.material_state_reused -eq $true) { throw "R33 first/direct material state unexpectedly marked reused" }
    if ($Runtime.Projection.ai_state_run_envelope.run_id -ne $Runtime.Run.run_id) { throw "R33 full run envelope run_id mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.source_sha256 -ne $Runtime.Run.state_sha256) { throw "R33 full run state SHA mismatch" }
    if (-not $Runtime.Projection.archive_scan_checkpoint.generated_at) { throw "R33 full run archive checkpoint missing" }
    if (-not $Runtime.Projection.archive_scan_runtime_metrics) { throw "R33 full run scan metrics missing" }
    $Metrics = $Runtime.Projection.archive_scan_runtime_metrics
    if ($Metrics.scan_engine -ne $ExpectedScanEngine) { throw "R33 runtime scan engine mismatch" }
    if ($Metrics.scan_policy_version -ne $ExpectedScanPolicy) { throw "R33 runtime scan policy mismatch" }
    if ([int]$Metrics.files_seen -le 0) { throw "R33 runtime scan files_seen invalid" }
    if ([int]$Metrics.cache_hits -le 0) { throw "R33 runtime scan did not reuse seeded cache" }
    if ([int]$Metrics.elapsed_ms -le 0) { throw "R33 runtime scan elapsed_ms invalid" }

    $Causal = Get-Content $CausalPath -Raw | ConvertFrom-Json
    $Scope = Get-Content $ScopePath -Raw | ConvertFrom-Json
    if ($Scope.status -ne "COMPLETE") { throw "R33 scope certificate is not COMPLETE" }
    if ([double]$Scope.coverage_percent -ne 100.0) { throw "R33 scope coverage is not 100 percent" }
    $ExpectedDenominator = [int]$Causal.origin_files_seen + [int]$Causal.pivot_files_seen + [int]$Causal.current_files_seen
    if ([int]$Scope.denominator -ne $ExpectedDenominator) { throw "R33 scope denominator mismatch" }
    if ([int]$Metrics.files_seen -ne $ExpectedDenominator) { throw "R33 scan metrics/files scope mismatch" }
    $SelfRows = @($Scope.files | Where-Object { [string]$_.path -match "HANRI_R33" })
    if ($SelfRows.Count -ne 0) { throw "R33 self projection leaked into archive scope" }
    $PredecessorRows = @($Scope.files | Where-Object { [string]$_.path -match "HANRI_R32" })
    if ($PredecessorRows.Count -eq 0) { throw "R33 predecessor R32 evidence is missing from narrow archive scope" }
}

function Assert-FastHeartbeatReadback($Runtime, [string]$DirectMaterialRunId) {
    if ($Runtime.Run.heartbeat_fast_path -ne $true) { throw "R33 scheduled run did not use heartbeat fast path" }
    if ($Runtime.Run.fast_path_integrity_verified -ne $true) { throw "R33 scheduled fast-path integrity was not verified" }
    if ($Runtime.Run.material_state_reused -ne $true) { throw "R33 scheduled run did not mark material state reuse" }
    if ($Runtime.Run.material_state_run_id -ne $DirectMaterialRunId) { throw "R33 scheduled heartbeat did not reuse direct material run" }
    if ($Runtime.Projection.heartbeat_fast_path -ne $true) { throw "R33 scheduled projection did not mark fast path" }
    if ($Runtime.Projection.material_state_reused -ne $true) { throw "R33 scheduled projection did not mark material state reuse" }
    if ($Runtime.Projection.ai_state_run_envelope.run_id -ne $Runtime.Run.run_id) { throw "R33 fast envelope run_id mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.source_sha256 -ne $Runtime.Run.state_sha256) { throw "R33 fast envelope state SHA mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.shadow_only -ne $true) { throw "R33 fast envelope shadow_only invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.can_trade -ne $false) { throw "R33 fast envelope can_trade invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.self_application -ne $false) { throw "R33 fast envelope self_application invariant failed" }
    if ([int]$Runtime.Projection.ai_state_run_envelope.external_model_api_calls -ne 0) { throw "R33 fast envelope external API invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.source_repository_writes -ne $false) { throw "R33 fast envelope repository-write invariant failed" }
}

$Head = GitValue @("rev-parse", "HEAD")
$Branch = GitValue @("branch", "--show-current")
$Dirty = GitValue @("status", "--porcelain")
if ($Branch -ne $ExpectedBranch) { throw "Install gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "Install gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "Install gate: -ExpectedCommit is required with -Apply" }
if ($Apply -and $Head -ne $ExpectedCommit) { throw "Install gate: HEAD $Head does not match expected $ExpectedCommit" }

$ConfigObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "33.0.0") { throw "Config gate: program_version must be 33.0.0" }
if ($ConfigObject.shadow_only -ne $true) { throw "Config gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "Config gate: external_model_api must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "Config gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR33") { throw "Config gate: R33 state must be isolated" }
if ($ConfigObject.human_output_root -notmatch "HANRI_R33") { throw "Config gate: R33 Drive output must be isolated" }

$R32Task = Get-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue
if (-not $R32Task) { throw "Promotion gate: accepted R32 task not found: $R32TaskName" }
$R32WasEnabled = [bool]($R32Task.State -ne "Disabled")
if (-not $R32WasEnabled) { throw "Promotion gate: accepted R32 task is not enabled" }
$R32CachePath = Join-Path $R32StateRoot "archive_inventory_cache.json"
if (-not (Test-Path $R32CachePath)) { throw "Promotion gate: accepted R32 inventory cache missing" }

Write-Host "HANRI R33 RC1 scandir side-by-side install gate (PS5.1 safe)"
Write-Host "Source:  $SourceRoot"
Write-Host "HEAD:    $Head"
Write-Host "Install: $InstallRoot"
Write-Host "Accepted R32 remains enabled until R33 full scope/integrity plus fast scheduled readback pass."
if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

$ExistingR33Task = Get-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
if ($ExistingR33Task) {
    Disable-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($ExistingR33Task.State -eq "Running") { Stop-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue }
    if (-not (Wait-TaskStopped $R33TaskName 60)) { throw "Recovery gate: previous R33 task did not stop within 60 seconds" }
}

New-Item -ItemType Directory -Force -Path $InstallBase, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousR33AppBackup = $null
$PreviousR33StateBackup = $null
if (Test-Path $InstallRoot) {
    $PreviousR33AppBackup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousR33AppBackup
}
if (Test-Path $StateRoot) {
    $PreviousR33StateBackup = "$StateRoot.backup.$Timestamp"
    Move-Item -Force $StateRoot $PreviousR33StateBackup
}
New-Item -ItemType Directory -Force -Path $InstallRoot, $StateRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot
Copy-Item -Force $R32CachePath (Join-Path $StateRoot "archive_inventory_cache.json")
$SeedCacheSha = (Get-FileHash $R32CachePath -Algorithm SHA256).Hash.ToLowerInvariant()

$Config = Join-Path $InstallRoot "config\r33.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ProjectionReceiptPath = Join-Path $StateRoot "latest_projection_receipt.json"
$CausalPath = Join-Path $StateRoot "latest_archive_causal_spine.json"
$ScopePath = Join-Path $StateRoot "latest_archive_scope_certificate.json"
$env:PYTHONPATH = $PythonPath

try {
    Set-Location $InstallRoot
    & $Python -m compileall -q (Join-Path $InstallRoot "src")
    if ($LASTEXITCODE -ne 0) { throw "R33 compile check failed with exit code $LASTEXITCODE" }

    $DirectStarted = [DateTime]::UtcNow
    & $Python -m hanri once --config $Config
    if ($LASTEXITCODE -ne 0) { throw "R33 direct full one-shot failed with exit code $LASTEXITCODE" }
    $DirectRuntime = Read-R33Runtime $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    Assert-FullMaterialReadback $DirectRuntime $CausalPath $ScopePath
    $DirectElapsedSeconds = [int]([DateTime]::UtcNow - $DirectStarted).TotalSeconds
    $DirectMaterialRunId = [string]$DirectRuntime.Run.run_id
    $DirectScanMetrics = $DirectRuntime.Projection.archive_scan_runtime_metrics
    $DirectScope = Get-Content $ScopePath -Raw | ConvertFrom-Json

    $Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
    $TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes $SchedulerExecutionLimitMinutes)
    Register-ScheduledTask -TaskName $R33TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R33 bounded shadow supervisor; scandir archive scan with R32 integrity heartbeat" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R33TaskName | Out-Null

    $BeforeRunWrite = (Get-Item $RunReceiptPath).LastWriteTimeUtc
    $BeforeProjectionWrite = (Get-Item $ProjectionReceiptPath).LastWriteTimeUtc
    $SchedulerGateStarted = [DateTime]::UtcNow
    $SchedulerDeadline = $SchedulerGateStarted.AddMinutes($SchedulerGateTimeoutMinutes)
    $RunUpdated = $false
    $ProjectionUpdated = $false
    $TaskCompleted = $false
    Start-ScheduledTask -TaskName $R33TaskName
    while ([DateTime]::UtcNow -lt $SchedulerDeadline) {
        Start-Sleep -Seconds 2
        if ((Test-Path $RunReceiptPath) -and ((Get-Item $RunReceiptPath).LastWriteTimeUtc -gt $BeforeRunWrite)) { $RunUpdated = $true }
        if ((Test-Path $ProjectionReceiptPath) -and ((Get-Item $ProjectionReceiptPath).LastWriteTimeUtc -gt $BeforeProjectionWrite)) { $ProjectionUpdated = $true }
        $TaskState = (Get-ScheduledTask -TaskName $R33TaskName -ErrorAction Stop).State
        if ($RunUpdated -and $ProjectionUpdated -and $TaskState -ne "Running") { $TaskCompleted = $true; break }
    }
    if (-not $RunUpdated) { throw "R33 scheduled task did not produce a fresh run receipt within gate window" }
    if (-not $ProjectionUpdated) { throw "R33 scheduled task did not produce a fresh projection receipt within gate window" }
    if (-not $TaskCompleted) { throw "R33 scheduled task did not complete within gate window" }

    $ScheduledRuntime = Read-R33Runtime $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    Assert-FastHeartbeatReadback $ScheduledRuntime $DirectMaterialRunId
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R33TaskName
    if ($TaskInfo.LastTaskResult -eq $SchedulerRunningResult) { throw "R33 scheduler completion race: LastTaskResult still reports SCHED_S_TASK_RUNNING" }
    if ($TaskInfo.LastTaskResult -ne 0) { throw "R33 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }

    Disable-ScheduledTask -TaskName $R32TaskName | Out-Null

    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R33_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        r33_task = $R33TaskName
        r33_last_task_result = $TaskInfo.LastTaskResult
        direct_full_material_run_id = $DirectMaterialRunId
        direct_full_elapsed_seconds = $DirectElapsedSeconds
        direct_scan_metrics = $DirectScanMetrics
        direct_scope_denominator = [int]$DirectScope.denominator
        direct_scope_manifest_sha256 = [string]$DirectScope.scope_manifest_sha256
        seeded_r32_inventory_cache_sha256 = $SeedCacheSha
        scheduled_fast_run_id = [string]$ScheduledRuntime.Run.run_id
        scheduled_fast_path_verified = $true
        scheduled_fast_integrity_verified = $true
        scheduled_fast_path_elapsed_ms = $ScheduledRuntime.Run.fast_path_elapsed_ms
        scheduled_heavy_snapshot_bytes_hashed = $ScheduledRuntime.Run.heavy_snapshot_bytes_hashed
        r32_task = $R32TaskName
        r32_was_enabled = $R32WasEnabled
        r32_disabled_only_after_r33_full_scope_and_fast_readback = $true
        r32_files_modified = $false
        r32_state_modified_by_installer = $false
        previous_r33_app_backup = $PreviousR33AppBackup
        previous_r33_state_backup = $PreviousR33StateBackup
        digest_identity = "HANRI R33"
        scan_policy = $ExpectedScanPolicy
        scan_engine = $ExpectedScanEngine
        integrity_mode = $ExpectedIntegrityMode
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R32FromR33.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R33_RC1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 16 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R33 RC1 installed side-by-side; full scandir scope and fast heartbeat readbacks verified."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "Accepted R32 files/state were not modified; R32 task was disabled only after R33 PASS."
}
catch {
    Disable-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R33TaskName -ErrorAction SilentlyContinue
    if ($R32WasEnabled) { Enable-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
