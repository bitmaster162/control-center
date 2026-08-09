param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R30TaskName = "ControlCenter-HANRI-R30",
    [string]$R31TaskName = "ControlCenter-HANRI-R31"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR31"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$ConfigSource = Join-Path $SourceRoot "config\r31.windows.json"
$ExpectedBranch = "hanri/r31-release-candidate"
$ExpectedDigestIdentity = "HANRI R31"
$ForbiddenDigestIdentity = "HANRI R30"
$ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"
$SchedulerRunningResult = 267009
$SchedulerExecutionLimitMinutes = 20
$SchedulerGateTimeoutMinutes = 21

function GitValue([string[]]$Arguments) {
    $value = & git -C $SourceRoot @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
    return ($value | Out-String).Trim()
}

function Assert-R31RuntimeReadback(
    [string]$RunReceiptPath,
    [string]$AiStatePath,
    [string]$DigestPath,
    [string]$ProjectionReceiptPath
) {
    if (-not (Test-Path $RunReceiptPath)) { throw "R31 readback missing latest_run_receipt.json" }
    if (-not (Test-Path $AiStatePath)) { throw "R31 readback missing latest_ai_state.json" }
    if (-not (Test-Path $DigestPath)) { throw "R31 readback missing latest_human_digest.md" }
    if (-not (Test-Path $ProjectionReceiptPath)) { throw "R31 readback missing latest_projection_receipt.json" }

    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Digest = Get-Content $DigestPath -Raw
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $FirstLine = (($Digest -split "`r?`n", 2)[0])

    if ($Run.program_version -ne "31.0.0") { throw "R31 run receipt version mismatch" }
    if ($Run.can_trade -ne $false) { throw "R31 run receipt can_trade invariant failed" }
    if ($Run.self_application -ne $false) { throw "R31 run receipt self_application invariant failed" }
    if ([int]$Run.external_model_api_calls -ne 0) { throw "R31 run receipt external API invariant failed" }

    if ($State.program_version -ne "31.0.0") { throw "R31 AI-state version mismatch" }
    if ($State.shadow_only -ne $true) { throw "R31 AI-state shadow_only invariant failed" }
    if ($State.invariants.can_trade -ne $false) { throw "R31 AI-state can_trade invariant failed" }
    if ($State.invariants.self_application -ne $false) { throw "R31 AI-state self_application invariant failed" }
    if ([int]$State.invariants.external_model_api_calls -ne 0) { throw "R31 AI-state external API invariant failed" }
    if ($State.invariants.source_repository_writes -ne $false) { throw "R31 source repository write invariant failed" }

    if (-not $FirstLine.Contains($ExpectedDigestIdentity) -or $FirstLine.Contains($ForbiddenDigestIdentity)) {
        throw "R31 identity readback failed: human digest identity mismatch"
    }

    if ($Projection.program_version -ne "31.0.0") { throw "R31 projection receipt version mismatch" }
    if ($Projection.self_projection_excluded_from_archive -ne $true) { throw "R31 self-projection exclusion invariant failed" }
    if ($Projection.can_trade -ne $false) { throw "R31 projection can_trade invariant failed" }
    if ($Projection.self_application -ne $false) { throw "R31 projection self_application invariant failed" }
    if ([int]$Projection.external_model_api_calls -ne 0) { throw "R31 projection external API invariant failed" }

    if ($Projection.material_policy.version -ne $ExpectedMaterialPolicy) { throw "R31 material policy version mismatch" }
    $Ignored = @($Projection.material_policy.latest_ai_state_ignored_top_level_keys)
    if ($Ignored.Count -ne 1 -or $Ignored[0] -ne "new_events") { throw "R31 material policy ignored-key set mismatch" }
    if ($Projection.material_policy.nested_new_events_remains_material -ne $true) { throw "R31 nested new_events material gate failed" }
    if ($Projection.material_policy.new_findings_remains_material -ne $true) { throw "R31 new_findings material gate failed" }
    if ($Projection.material_policy.new_candidates_remains_material -ne $true) { throw "R31 new_candidates material gate failed" }
    if ($Projection.material_policy.new_decisions_remains_material -ne $true) { throw "R31 new_decisions material gate failed" }
    if ($Projection.material_policy.stop_reasons_remains_material -ne $true) { throw "R31 stop_reasons material gate failed" }
    if ($Projection.material_policy.current_run_envelope_always_projected -ne $true) { throw "R31 current-run envelope gate failed" }

    $Envelope = $Projection.ai_state_run_envelope
    if (-not $Envelope) { throw "R31 projection AI-state run envelope missing" }
    if ($Envelope.run_id -ne $Run.run_id) { throw "R31 envelope run_id mismatch" }
    if ([int]$Envelope.new_events -ne [int]$Run.events_processed) { throw "R31 envelope new_events mismatch" }
    if ([int]$Envelope.new_findings -ne [int]$Run.findings_generated) { throw "R31 envelope new_findings mismatch" }
    if ([int]$Envelope.new_candidates -ne [int]$Run.candidates_generated) { throw "R31 envelope new_candidates mismatch" }
    if ([int]$Envelope.new_decisions -ne [int]$Run.decisions_processed) { throw "R31 envelope new_decisions mismatch" }
    if ($Envelope.source_sha256 -ne $Run.state_sha256) { throw "R31 envelope state SHA mismatch" }
    if ($Envelope.material_digest -ne $Projection.material_digests.'latest_ai_state.json') { throw "R31 envelope material digest mismatch" }
    if ($Envelope.shadow_only -ne $true) { throw "R31 envelope shadow_only invariant failed" }
    if ($Envelope.can_trade -ne $false) { throw "R31 envelope can_trade invariant failed" }
    if ($Envelope.self_application -ne $false) { throw "R31 envelope self_application invariant failed" }
    if ([int]$Envelope.external_model_api_calls -ne 0) { throw "R31 envelope external API invariant failed" }
    if ($Envelope.source_repository_writes -ne $false) { throw "R31 envelope repository-write invariant failed" }
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

$Head = GitValue @("rev-parse", "HEAD")
$Branch = GitValue @("branch", "--show-current")
$Dirty = GitValue @("status", "--porcelain")

if ($Branch -ne $ExpectedBranch) { throw "Install gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "Install gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "Install gate: -ExpectedCommit is required with -Apply" }
if ($Apply -and $Head -ne $ExpectedCommit) { throw "Install gate: HEAD $Head does not match expected $ExpectedCommit" }

$ConfigObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "31.0.0") { throw "Config gate: program_version must be 31.0.0" }
if ($ConfigObject.shadow_only -ne $true) { throw "Config gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "Config gate: external_model_api must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "Config gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR31") { throw "Config gate: R31 state must be isolated" }
if ($ConfigObject.human_output_root -notmatch "HANRI_R31") { throw "Config gate: R31 Drive output must be isolated" }

$R30Task = Get-ScheduledTask -TaskName $R30TaskName -ErrorAction SilentlyContinue
if (-not $R30Task) { throw "Promotion gate: accepted R30 task not found: $R30TaskName" }
$R30WasEnabled = [bool]($R30Task.State -ne "Disabled")
if (-not $R30WasEnabled) { throw "Promotion gate: accepted R30 task is not enabled" }

Write-Host "HANRI R31 RC1 side-by-side install gate (PS5.1 safe)"
Write-Host "Source:  $SourceRoot"
Write-Host "HEAD:    $Head"
Write-Host "Install: $InstallRoot"
Write-Host "Accepted R30 remains enabled until R31 scheduled completion/readback passes."

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

$ExistingR31Task = Get-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
if ($ExistingR31Task) {
    Disable-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($ExistingR31Task.State -eq "Running") {
        Stop-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
    }
    if (-not (Wait-TaskStopped $R31TaskName 60)) {
        throw "Recovery gate: previous R31 task instance did not stop within 60 seconds"
    }
}

New-Item -ItemType Directory -Force -Path $InstallBase, $StateRoot, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousR31Backup = $null
if (Test-Path $InstallRoot) {
    $PreviousR31Backup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousR31Backup
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r31.windows.json"
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
    if ($LASTEXITCODE -ne 0) { throw "R31 compile check failed with exit code $LASTEXITCODE" }

    & $Python -m hanri once --config $Config
    if ($LASTEXITCODE -ne 0) { throw "R31 direct one-shot failed with exit code $LASTEXITCODE" }
    Assert-R31RuntimeReadback $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath

    $Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
    $TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes $SchedulerExecutionLimitMinutes)
    Register-ScheduledTask -TaskName $R31TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R31 bounded shadow supervisor; stable AI-state projection with fresh run envelope" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R31TaskName | Out-Null

    $BeforeRunWrite = (Get-Item $RunReceiptPath).LastWriteTimeUtc
    $BeforeProjectionWrite = (Get-Item $ProjectionReceiptPath).LastWriteTimeUtc
    $SchedulerGateStarted = [DateTime]::UtcNow
    $SchedulerDeadline = $SchedulerGateStarted.AddMinutes($SchedulerGateTimeoutMinutes)
    $RunUpdated = $false
    $ProjectionUpdated = $false
    $TaskCompleted = $false

    Start-ScheduledTask -TaskName $R31TaskName
    while ([DateTime]::UtcNow -lt $SchedulerDeadline) {
        Start-Sleep -Seconds 2
        if ((Test-Path $RunReceiptPath) -and ((Get-Item $RunReceiptPath).LastWriteTimeUtc -gt $BeforeRunWrite)) {
            $RunUpdated = $true
        }
        if ((Test-Path $ProjectionReceiptPath) -and ((Get-Item $ProjectionReceiptPath).LastWriteTimeUtc -gt $BeforeProjectionWrite)) {
            $ProjectionUpdated = $true
        }
        $TaskState = (Get-ScheduledTask -TaskName $R31TaskName -ErrorAction Stop).State
        if ($RunUpdated -and $ProjectionUpdated -and $TaskState -ne "Running") {
            $TaskCompleted = $true
            break
        }
    }

    if (-not $RunUpdated) { throw "R31 scheduled task did not produce a fresh run receipt within gate window" }
    if (-not $ProjectionUpdated) { throw "R31 scheduled task did not produce a fresh projection receipt within gate window" }
    if (-not $TaskCompleted) { throw "R31 scheduled task did not complete within gate window" }

    Assert-R31RuntimeReadback $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R31TaskName
    if ($TaskInfo.LastTaskResult -eq $SchedulerRunningResult) {
        throw "R31 scheduler completion race: LastTaskResult still reports SCHED_S_TASK_RUNNING"
    }
    if ($TaskInfo.LastTaskResult -ne 0) { throw "R31 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }

    Disable-ScheduledTask -TaskName $R30TaskName | Out-Null

    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $SchedulerWaitSeconds = [int]([DateTime]::UtcNow - $SchedulerGateStarted).TotalSeconds
    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R31_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        r31_task = $R31TaskName
        r31_last_task_result = $TaskInfo.LastTaskResult
        scheduler_wait_seconds = $SchedulerWaitSeconds
        scheduler_execution_limit_minutes = $SchedulerExecutionLimitMinutes
        fresh_run_receipt_observed = $RunUpdated
        fresh_projection_receipt_observed = $ProjectionUpdated
        task_completion_observed = $TaskCompleted
        r30_task = $R30TaskName
        r30_was_enabled = $R30WasEnabled
        r30_disabled_only_after_r31_readback = $true
        r30_files_modified = $false
        r30_state_modified_by_installer = $false
        previous_r31_backup = $PreviousR31Backup
        digest_identity = "HANRI R31"
        material_policy_version = $Projection.material_policy.version
        projection_bytes_avoided_latest = [int64]$Projection.bytes_avoided
        run_receipt_sha256 = (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        ai_state_sha256 = (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        projection_receipt_sha256 = (Get-FileHash $ProjectionReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R30FromR31.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R31_RC1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R31 RC1 installed side-by-side and scheduled completion/readback verified."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "Accepted R30 files/state were not modified; R30 task was disabled only after R31 PASS."
}
catch {
    Disable-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R31TaskName -ErrorAction SilentlyContinue
    if ($R30WasEnabled) { Enable-ScheduledTask -TaskName $R30TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
