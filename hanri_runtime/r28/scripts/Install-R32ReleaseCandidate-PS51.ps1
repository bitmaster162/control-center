param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R31TaskName = "ControlCenter-HANRI-R31",
    [string]$R32TaskName = "ControlCenter-HANRI-R32"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR32"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$ConfigSource = Join-Path $SourceRoot "config\r32.windows.json"
$ExpectedBranch = "hanri/r32-release-candidate"
$ExpectedDigestIdentity = "HANRI R32"
$ForbiddenDigestIdentity = "HANRI R31"
$ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"
$ExpectedHeartbeatPolicy = "32.0.0-heartbeat-fast-path-v1"
$ExpectedIntegrityPolicy = "32.0.0-steady-integrity-v1"
$ExpectedIntegrityMode = "STREAMING_SHA256_NO_JSON_PARSE"
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

function Assert-BaseSafety($Run, $State, [string]$FirstLine, $Projection) {
    if ($Run.program_version -ne "32.0.0") { throw "R32 run receipt version mismatch" }
    if ($Run.can_trade -ne $false) { throw "R32 run receipt can_trade invariant failed" }
    if ($Run.self_application -ne $false) { throw "R32 run receipt self_application invariant failed" }
    if ([int]$Run.external_model_api_calls -ne 0) { throw "R32 run receipt external API invariant failed" }
    if ($State.program_version -ne "32.0.0") { throw "R32 AI-state version mismatch" }
    if ($State.shadow_only -ne $true) { throw "R32 AI-state shadow_only invariant failed" }
    if ($State.invariants.can_trade -ne $false) { throw "R32 AI-state can_trade invariant failed" }
    if ($State.invariants.self_application -ne $false) { throw "R32 AI-state self_application invariant failed" }
    if ([int]$State.invariants.external_model_api_calls -ne 0) { throw "R32 AI-state external API invariant failed" }
    if ($State.invariants.source_repository_writes -ne $false) { throw "R32 source repository write invariant failed" }
    if (-not $FirstLine.Contains($ExpectedDigestIdentity) -or $FirstLine.Contains($ForbiddenDigestIdentity)) {
        throw "R32 identity readback failed: human digest identity mismatch"
    }
    if ($Projection.program_version -ne "32.0.0") { throw "R32 projection receipt version mismatch" }
    if ($Projection.self_projection_excluded_from_archive -ne $true) { throw "R32 self-projection exclusion invariant failed" }
    if ($Projection.can_trade -ne $false) { throw "R32 projection can_trade invariant failed" }
    if ($Projection.self_application -ne $false) { throw "R32 projection self_application invariant failed" }
    if ([int]$Projection.external_model_api_calls -ne 0) { throw "R32 projection external API invariant failed" }
    if ($Projection.material_policy.version -ne $ExpectedMaterialPolicy) { throw "R32 inherited material policy mismatch" }
    if ($Projection.material_policy.heartbeat_fast_path_policy -ne $ExpectedHeartbeatPolicy) { throw "R32 heartbeat policy mismatch" }
    if ($Projection.material_policy.fast_path_streaming_sha256_integrity -ne $true) { throw "R32 streaming integrity policy missing" }
    if ($Projection.material_policy.heavy_json_parse_required_on_fast_path -ne $false) { throw "R32 fast-path JSON parse policy mismatch" }
    if ($Projection.integrity_policy_version -ne $ExpectedIntegrityPolicy) { throw "R32 integrity policy mismatch" }
    if ($Projection.heavy_snapshot_integrity_mode -ne $ExpectedIntegrityMode) { throw "R32 integrity mode mismatch" }
    if (-not $Projection.heavy_snapshot_raw_sha256) { throw "R32 raw heavy SHA checkpoint missing" }
}

function Assert-HeavyRawHashes($Projection, [string]$StateRootPath) {
    foreach ($Name in @("latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json")) {
        $Path = Join-Path $StateRootPath $Name
        if (-not (Test-Path $Path)) { throw "R32 heavy state missing: $Name" }
        $Expected = $Projection.heavy_snapshot_raw_sha256.$Name
        if ([string]::IsNullOrWhiteSpace([string]$Expected)) { throw "R32 heavy SHA checkpoint missing: $Name" }
        $Actual = (Get-FileHash $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Actual -ne ([string]$Expected).ToLowerInvariant()) { throw "R32 heavy SHA mismatch: $Name" }
    }
}

function Read-R32Runtime(
    [string]$RunReceiptPath,
    [string]$AiStatePath,
    [string]$DigestPath,
    [string]$ProjectionReceiptPath
) {
    if (-not (Test-Path $RunReceiptPath)) { throw "R32 readback missing latest_run_receipt.json" }
    if (-not (Test-Path $AiStatePath)) { throw "R32 readback missing latest_ai_state.json" }
    if (-not (Test-Path $DigestPath)) { throw "R32 readback missing latest_human_digest.md" }
    if (-not (Test-Path $ProjectionReceiptPath)) { throw "R32 readback missing latest_projection_receipt.json" }
    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Digest = Get-Content $DigestPath -Raw
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $FirstLine = (($Digest -split "`r?`n", 2)[0])
    Assert-BaseSafety $Run $State $FirstLine $Projection
    Assert-HeavyRawHashes $Projection $StateRoot
    return [pscustomobject]@{ Run=$Run; State=$State; Projection=$Projection; FirstLine=$FirstLine }
}

function Assert-FullMaterialReadback($Runtime) {
    if ($Runtime.Run.heartbeat_fast_path -eq $true) { throw "R32 first/direct run unexpectedly used heartbeat fast path" }
    if ($Runtime.Projection.heartbeat_fast_path -eq $true) { throw "R32 first/direct projection unexpectedly marked fast path" }
    if ($Runtime.Projection.material_state_reused -eq $true) { throw "R32 first/direct material state unexpectedly marked reused" }
    if ($Runtime.Projection.ai_state_run_envelope.run_id -ne $Runtime.Run.run_id) { throw "R32 full run envelope run_id mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.source_sha256 -ne $Runtime.Run.state_sha256) { throw "R32 full run state SHA mismatch" }
    if (-not $Runtime.Projection.archive_scan_checkpoint.generated_at) { throw "R32 full run archive checkpoint missing" }
}

function Assert-FastHeartbeatReadback($Runtime) {
    if ($Runtime.Run.heartbeat_fast_path -ne $true) { throw "R32 scheduled run did not use heartbeat fast path" }
    if ($Runtime.Run.fast_path_integrity_verified -ne $true) { throw "R32 scheduled fast-path integrity was not verified" }
    if ($Runtime.Run.material_state_reused -ne $true) { throw "R32 scheduled run did not mark material state reuse" }
    if ([string]::IsNullOrWhiteSpace([string]$Runtime.Run.material_state_run_id)) { throw "R32 material_state_run_id missing" }
    if ($Runtime.Projection.heartbeat_fast_path -ne $true) { throw "R32 scheduled projection did not mark fast path" }
    if ($Runtime.Projection.material_state_reused -ne $true) { throw "R32 scheduled projection did not mark material state reuse" }
    if ($Runtime.Projection.ai_state_run_envelope.run_id -ne $Runtime.Run.run_id) { throw "R32 fast envelope run_id mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.source_sha256 -ne $Runtime.Run.state_sha256) { throw "R32 fast envelope state SHA mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.material_state_run_id -ne $Runtime.Run.material_state_run_id) { throw "R32 material state lineage mismatch" }
    if ($Runtime.Projection.ai_state_run_envelope.shadow_only -ne $true) { throw "R32 fast envelope shadow_only invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.can_trade -ne $false) { throw "R32 fast envelope can_trade invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.self_application -ne $false) { throw "R32 fast envelope self_application invariant failed" }
    if ([int]$Runtime.Projection.ai_state_run_envelope.external_model_api_calls -ne 0) { throw "R32 fast envelope external API invariant failed" }
    if ($Runtime.Projection.ai_state_run_envelope.source_repository_writes -ne $false) { throw "R32 fast envelope repository-write invariant failed" }
    if (-not $Runtime.Projection.archive_scan_checkpoint.generated_at) { throw "R32 fast archive checkpoint missing" }
}

$Head = GitValue @("rev-parse", "HEAD")
$Branch = GitValue @("branch", "--show-current")
$Dirty = GitValue @("status", "--porcelain")
if ($Branch -ne $ExpectedBranch) { throw "Install gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "Install gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "Install gate: -ExpectedCommit is required with -Apply" }
if ($Apply -and $Head -ne $ExpectedCommit) { throw "Install gate: HEAD $Head does not match expected $ExpectedCommit" }

$ConfigObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "32.0.0") { throw "Config gate: program_version must be 32.0.0" }
if ($ConfigObject.shadow_only -ne $true) { throw "Config gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "Config gate: external_model_api must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "Config gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR32") { throw "Config gate: R32 state must be isolated" }
if ($ConfigObject.human_output_root -notmatch "HANRI_R32") { throw "Config gate: R32 Drive output must be isolated" }

$R31Task = Get-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
if (-not $R31Task) { throw "Promotion gate: accepted R31 task not found: $R31TaskName" }
$R31WasEnabled = [bool]($R31Task.State -ne "Disabled")
if (-not $R31WasEnabled) { throw "Promotion gate: accepted R31 task is not enabled" }

Write-Host "HANRI R32 RC1 side-by-side install gate (PS5.1 safe)"
Write-Host "Source:  $SourceRoot"
Write-Host "HEAD:    $Head"
Write-Host "Install: $InstallRoot"
Write-Host "Accepted R31 remains enabled until R32 full material run plus fast scheduled readback pass."
if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

$ExistingR32Task = Get-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue
if ($ExistingR32Task) {
    Disable-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($ExistingR32Task.State -eq "Running") { Stop-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue }
    if (-not (Wait-TaskStopped $R32TaskName 60)) { throw "Recovery gate: previous R32 task instance did not stop within 60 seconds" }
}

New-Item -ItemType Directory -Force -Path $InstallBase, $StateRoot, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousR32Backup = $null
if (Test-Path $InstallRoot) {
    $PreviousR32Backup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousR32Backup
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r32.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ProjectionReceiptPath = Join-Path $StateRoot "latest_projection_receipt.json"
$env:PYTHONPATH = $PythonPath

try {
    Set-Location $InstallRoot
    & $Python -m compileall -q (Join-Path $InstallRoot "src")
    if ($LASTEXITCODE -ne 0) { throw "R32 compile check failed with exit code $LASTEXITCODE" }

    $DirectStarted = [DateTime]::UtcNow
    & $Python -m hanri once --config $Config
    if ($LASTEXITCODE -ne 0) { throw "R32 direct full one-shot failed with exit code $LASTEXITCODE" }
    $DirectRuntime = Read-R32Runtime $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    Assert-FullMaterialReadback $DirectRuntime
    $DirectElapsedSeconds = [int]([DateTime]::UtcNow - $DirectStarted).TotalSeconds
    $DirectMaterialRunId = [string]$DirectRuntime.Run.run_id

    $Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
    $TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes $SchedulerExecutionLimitMinutes)
    Register-ScheduledTask -TaskName $R32TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R32 bounded shadow supervisor; fail-closed steady heartbeat fast path" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R32TaskName | Out-Null

    $BeforeRunWrite = (Get-Item $RunReceiptPath).LastWriteTimeUtc
    $BeforeProjectionWrite = (Get-Item $ProjectionReceiptPath).LastWriteTimeUtc
    $SchedulerGateStarted = [DateTime]::UtcNow
    $SchedulerDeadline = $SchedulerGateStarted.AddMinutes($SchedulerGateTimeoutMinutes)
    $RunUpdated = $false
    $ProjectionUpdated = $false
    $TaskCompleted = $false
    Start-ScheduledTask -TaskName $R32TaskName
    while ([DateTime]::UtcNow -lt $SchedulerDeadline) {
        Start-Sleep -Seconds 2
        if ((Test-Path $RunReceiptPath) -and ((Get-Item $RunReceiptPath).LastWriteTimeUtc -gt $BeforeRunWrite)) { $RunUpdated = $true }
        if ((Test-Path $ProjectionReceiptPath) -and ((Get-Item $ProjectionReceiptPath).LastWriteTimeUtc -gt $BeforeProjectionWrite)) { $ProjectionUpdated = $true }
        $TaskState = (Get-ScheduledTask -TaskName $R32TaskName -ErrorAction Stop).State
        if ($RunUpdated -and $ProjectionUpdated -and $TaskState -ne "Running") { $TaskCompleted = $true; break }
    }
    if (-not $RunUpdated) { throw "R32 scheduled task did not produce a fresh run receipt within gate window" }
    if (-not $ProjectionUpdated) { throw "R32 scheduled task did not produce a fresh projection receipt within gate window" }
    if (-not $TaskCompleted) { throw "R32 scheduled task did not complete within gate window" }

    $ScheduledRuntime = Read-R32Runtime $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    Assert-FastHeartbeatReadback $ScheduledRuntime
    if ($ScheduledRuntime.Run.material_state_run_id -ne $DirectMaterialRunId) { throw "R32 scheduled heartbeat did not reuse direct material run" }

    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R32TaskName
    if ($TaskInfo.LastTaskResult -eq $SchedulerRunningResult) { throw "R32 scheduler completion race: LastTaskResult still reports SCHED_S_TASK_RUNNING" }
    if ($TaskInfo.LastTaskResult -ne 0) { throw "R32 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }

    Disable-ScheduledTask -TaskName $R31TaskName | Out-Null

    $SchedulerWaitSeconds = [int]([DateTime]::UtcNow - $SchedulerGateStarted).TotalSeconds
    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R32_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        r32_task = $R32TaskName
        r32_last_task_result = $TaskInfo.LastTaskResult
        direct_full_material_run_id = $DirectMaterialRunId
        direct_full_elapsed_seconds = $DirectElapsedSeconds
        scheduled_fast_run_id = [string]$ScheduledRuntime.Run.run_id
        scheduled_fast_path_verified = $true
        scheduled_fast_integrity_verified = $true
        scheduled_fast_path_elapsed_ms = $ScheduledRuntime.Run.fast_path_elapsed_ms
        scheduled_heavy_snapshot_bytes_hashed = $ScheduledRuntime.Run.heavy_snapshot_bytes_hashed
        scheduler_wait_seconds = $SchedulerWaitSeconds
        scheduler_execution_limit_minutes = $SchedulerExecutionLimitMinutes
        fresh_run_receipt_observed = $RunUpdated
        fresh_projection_receipt_observed = $ProjectionUpdated
        task_completion_observed = $TaskCompleted
        r31_task = $R31TaskName
        r31_was_enabled = $R31WasEnabled
        r31_disabled_only_after_r32_full_and_fast_readback = $true
        r31_files_modified = $false
        r31_state_modified_by_installer = $false
        previous_r32_backup = $PreviousR32Backup
        digest_identity = "HANRI R32"
        integrity_mode = $ExpectedIntegrityMode
        run_receipt_sha256 = (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        ai_state_sha256 = (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        projection_receipt_sha256 = (Get-FileHash $ProjectionReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R31FromR32.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R32_RC1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R32 RC1 installed side-by-side; full material and fast heartbeat readbacks verified."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "Accepted R31 files/state were not modified; R31 task was disabled only after R32 PASS."
}
catch {
    Disable-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R32TaskName -ErrorAction SilentlyContinue
    if ($R31WasEnabled) { Enable-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
