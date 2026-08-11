param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R35TaskName = "ControlCenter-HANRI-R35",
    [string]$R36TaskName = "ControlCenter-HANRI-R36",
    [int]$BenchmarkSamples = 3
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$RepoRoot = (& git -C $SourceRoot rev-parse --show-toplevel 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($RepoRoot)) { throw "R36 gate: git top-level resolution failed" }

$ExpectedBranch = "hanri/r36-accepted-runtime"
$ExpectedProgramVersion = "36.0.0"
$ExpectedIntegrityPolicy = "36.0.0-heartbeat-integrity-fast-gate-v1"
$ExpectedCachedMode = "CACHED_STAT_GUARD"
$ExpectedFullMode = "STREAMING_SHA256_NO_JSON_PARSE"
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR36"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$ConfigSource = Join-Path $SourceRoot "config\r36.windows.json"
$R35Base = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR35"
$R35App = Join-Path $R35Base "app"
$R35State = Join-Path $R35Base "state"
$R35Config = Join-Path $R35App "config\r35.windows.json"
$R35LockPath = Join-Path $R35State "hanri.lock"

function GitValue([string[]]$Arguments) {
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $value = & git -C $RepoRoot @Arguments 2>$null
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $old
    }
    if ($code -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
    return ($value | Out-String).Trim()
}

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

function Wait-TaskStopped([string]$TaskName, [int]$TimeoutSeconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if (-not $task -or $task.State -ne "Running") { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Quiesce-HanriLock([string]$LockPath, [int]$TimeoutSeconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ((Test-Path -LiteralPath $LockPath) -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path -LiteralPath $LockPath)) { return $null }

    try {
        $payload = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
        $ownerPid = [int]$payload.pid
    }
    catch {
        throw "R35 lock remained after scheduler stop and payload is unreadable; refusing quarantine: $LockPath"
    }
    if ($ownerPid -le 0) { throw "R35 lock has invalid PID; refusing quarantine: $LockPath" }

    try {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerPid" -ErrorAction Stop
    }
    catch {
        throw "R35 lock PID liveness check failed; refusing quarantine: $($_.Exception.Message)"
    }
    if ($owner) {
        $commandLine = [string]$owner.CommandLine
        throw "R35 lock still has a live PID $ownerPid; refusing quarantine. CommandLine=$commandLine"
    }

    $suffix = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $quarantine = "$LockPath.orphaned-r36-cutover-$suffix"
    Move-Item -LiteralPath $LockPath -Destination $quarantine -ErrorAction Stop
    if (Test-Path -LiteralPath $LockPath) { throw "R35 orphan lock quarantine did not clear active lock path" }
    if (-not (Test-Path -LiteralPath $quarantine)) { throw "R35 orphan lock quarantine evidence missing" }
    return $quarantine
}

function Median([double[]]$Values) {
    if (-not $Values -or $Values.Count -eq 0) { throw "median requires values" }
    $sorted = @($Values | Sort-Object)
    $n = $sorted.Count
    if (($n % 2) -eq 1) { return [double]$sorted[[int]($n / 2)] }
    return ([double]$sorted[($n / 2) - 1] + [double]$sorted[$n / 2]) / 2.0
}

function Read-Runtime([string]$RuntimeStateRoot) {
    $runPath = Join-Path $RuntimeStateRoot "latest_run_receipt.json"
    $projectionPath = Join-Path $RuntimeStateRoot "latest_projection_receipt.json"
    $statePath = Join-Path $RuntimeStateRoot "latest_ai_state.json"
    foreach ($path in @($runPath, $projectionPath, $statePath)) {
        if (-not (Test-Path $path)) { throw "runtime readback missing: $path" }
    }
    return [pscustomobject]@{
        Run = (Get-Content $runPath -Raw | ConvertFrom-Json)
        Projection = (Get-Content $projectionPath -Raw | ConvertFrom-Json)
        State = (Get-Content $statePath -Raw | ConvertFrom-Json)
    }
}

function Invoke-HanriOnce([string]$AppRoot, [string]$ConfigPath) {
    $oldPythonPath = $env:PYTHONPATH
    $oldLocation = Get-Location
    try {
        $env:PYTHONPATH = Join-Path $AppRoot "src"
        Set-Location $AppRoot
        Invoke-Native $Python @("-m", "hanri", "once", "--config", $ConfigPath)
    } finally {
        Set-Location $oldLocation
        $env:PYTHONPATH = $oldPythonPath
    }
}

function Assert-HeavyHashes($Projection, [string]$RuntimeStateRoot) {
    foreach ($name in @("latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json")) {
        $path = Join-Path $RuntimeStateRoot $name
        if (-not (Test-Path $path)) { throw "R36 heavy state missing: $name" }
        $expected = [string]$Projection.heavy_snapshot_raw_sha256.$name
        if ([string]::IsNullOrWhiteSpace($expected)) { throw "R36 heavy SHA checkpoint missing: $name" }
        $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $expected.ToLowerInvariant()) { throw "R36 heavy SHA mismatch: $name" }
    }
}

function Assert-R36Common($Runtime) {
    if ($Runtime.Run.program_version -ne $ExpectedProgramVersion) { throw "R36 run version mismatch" }
    if ($Runtime.Run.can_trade -ne $false) { throw "R36 can_trade invariant failed" }
    if ($Runtime.Run.self_application -ne $false) { throw "R36 self_application invariant failed" }
    if ([int]$Runtime.Run.external_model_api_calls -ne 0) { throw "R36 external model API invariant failed" }
    if ($Runtime.State.program_version -ne $ExpectedProgramVersion) { throw "R36 state version mismatch" }
    if ($Runtime.State.shadow_only -ne $true) { throw "R36 shadow_only invariant failed" }
    if ($Runtime.State.invariants.source_repository_writes -ne $false) { throw "R36 source repo write invariant failed" }
    if ($Runtime.Projection.program_version -ne $ExpectedProgramVersion) { throw "R36 projection version mismatch" }
    if ($Runtime.Projection.integrity_policy_version -ne $ExpectedIntegrityPolicy) { throw "R36 integrity policy mismatch" }
    if ($Runtime.Projection.material_policy.archive_inventory_backend -ne "SQLITE") { throw "R36 SQLite backend missing" }
    if ($Runtime.Projection.material_policy.fast_path_cached_stat_integrity_gate -ne $true) { throw "R36 cached stat policy missing" }
    if ($Runtime.Projection.material_policy.fast_path_full_rehash_required_periodically -ne $true) { throw "R36 periodic full rehash policy missing" }
}

function Collect-FastSamples(
    [string]$AppRoot,
    [string]$ConfigPath,
    [string]$RuntimeStateRoot,
    [int]$Count,
    [string]$RequiredMode
) {
    $samples = @()
    $attempts = 0
    while ($samples.Count -lt $Count -and $attempts -lt ($Count + 5)) {
        $attempts++
        Invoke-HanriOnce $AppRoot $ConfigPath
        $runtime = Read-Runtime $RuntimeStateRoot
        if ($runtime.Run.heartbeat_fast_path -ne $true) { continue }
        if ($RequiredMode -and $runtime.Projection.heavy_snapshot_integrity_mode -ne $RequiredMode) { continue }
        $samples += [double]$runtime.Run.fast_path_total_observed_ms
    }
    if ($samples.Count -ne $Count) { throw "could not collect $Count required fast-path samples; collected $($samples.Count)" }
    return [double[]]$samples
}

$head = GitValue @("rev-parse", "HEAD")
$tree = GitValue @("rev-parse", "HEAD^{tree}")
$branch = GitValue @("branch", "--show-current")
$dirty = GitValue @("status", "--porcelain")
if ($branch -ne $ExpectedBranch) { throw "R36 gate: expected branch $ExpectedBranch, got $branch" }
if ($dirty) { throw "R36 gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "R36 gate: -ExpectedCommit required with -Apply" }
if ($Apply -and $head -ne $ExpectedCommit) { throw "R36 gate: HEAD moved; expected $ExpectedCommit got $head" }
if (-not (Test-Path $ConfigSource)) { throw "R36 gate: config missing" }

$configObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($configObject.program_version -ne $ExpectedProgramVersion) { throw "R36 config version mismatch" }
if ($configObject.shadow_only -ne $true) { throw "R36 config shadow_only must be true" }
if ($configObject.external_model_api -ne "DENY") { throw "R36 config external_model_api must be DENY" }
if ($configObject.can_trade -ne $false) { throw "R36 config can_trade must be false" }
if ($configObject.state_root -notmatch "ControlCenterHANRIR36") { throw "R36 state root is not isolated" }
if ($configObject.human_output_root -notmatch "HANRI_R36") { throw "R36 output root is not isolated" }

$r35Task = Get-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
if (-not $r35Task) { throw "R36 promotion gate: accepted R35 task not found" }
$r35WasEnabled = [bool]($r35Task.State -ne "Disabled")
if (-not $r35WasEnabled) { throw "R36 promotion gate: R35 task must be enabled before cutover" }
foreach ($path in @($R35App, $R35State, $R35Config)) {
    if (-not (Test-Path $path)) { throw "R36 promotion gate: R35 runtime missing: $path" }
}

Write-Host "HANRI R36 side-by-side cutover gate"
Write-Host "HEAD: $head"
Write-Host "TREE: $tree"
Write-Host "R35 remains the rollback anchor until R36 tests, benchmark and scheduler readback pass."
if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $head"
    exit 0
}

$timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$backupApp = $null
$backupState = $null
$cutoverStarted = $false
$r35OrphanLockQuarantine = $null
try {
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $SourceRoot "src"
        Invoke-Native $Python @("-m", "pytest", "-q", (Join-Path $SourceRoot "tests\test_r36_integrity_fast_gate.py"), (Join-Path $SourceRoot "tests\test_r36_release_gate.py"))
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }

    Disable-ScheduledTask -TaskName $R35TaskName | Out-Null
    $cutoverStarted = $true
    if ((Get-ScheduledTask -TaskName $R35TaskName).State -eq "Running") {
        Stop-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
    }
    if (-not (Wait-TaskStopped $R35TaskName 60)) { throw "R35 task did not stop" }
    $r35OrphanLockQuarantine = Quiesce-HanriLock $R35LockPath 15
    if ($r35OrphanLockQuarantine) {
        Write-Host "R35_ORPHAN_LOCK_QUARANTINED $r35OrphanLockQuarantine"
    }

    $r35Samples = Collect-FastSamples $R35App $R35Config $R35State $BenchmarkSamples $ExpectedFullMode
    $r35Median = Median $r35Samples

    New-Item -ItemType Directory -Force -Path $InstallBase, $LogRoot, $ReceiptRoot | Out-Null
    if (Test-Path $InstallRoot) {
        $backupApp = "$InstallRoot.backup.$timestamp"
        Move-Item -Force $InstallRoot $backupApp
    }
    if (Test-Path $StateRoot) {
        $backupState = "$StateRoot.backup.$timestamp"
        Move-Item -Force $StateRoot $backupState
    }
    New-Item -ItemType Directory -Force -Path $InstallRoot, $StateRoot | Out-Null
    Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

    foreach ($seed in @("archive_inventory_cache.json", "archive_inventory_cache.sqlite3")) {
        $source = Join-Path $R35State $seed
        if (Test-Path $source) { Copy-Item -Force $source (Join-Path $StateRoot $seed) }
    }

    $config = Join-Path $InstallRoot "config\r36.windows.json"
    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = Join-Path $InstallRoot "src"
        Invoke-Native $Python @("-m", "compileall", "-q", (Join-Path $InstallRoot "src"))
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }

    Invoke-HanriOnce $InstallRoot $config
    $fullRuntime = Read-Runtime $StateRoot
    Assert-R36Common $fullRuntime
    if ($fullRuntime.Run.heartbeat_fast_path -eq $true) { throw "R36 first run unexpectedly used fast path" }
    if ($fullRuntime.Projection.heavy_snapshot_full_sha_performed -ne $true) { throw "R36 first run did not perform full SHA" }
    if ($fullRuntime.Projection.heavy_snapshot_integrity_mode -ne $ExpectedFullMode) { throw "R36 first run full integrity mode mismatch" }
    Assert-HeavyHashes $fullRuntime.Projection $StateRoot

    $r36Samples = Collect-FastSamples $InstallRoot $config $StateRoot $BenchmarkSamples $ExpectedCachedMode
    $r36Runtime = Read-Runtime $StateRoot
    Assert-R36Common $r36Runtime
    if ($r36Runtime.Projection.heavy_snapshot_full_sha_performed -ne $false) { throw "R36 cached heartbeat unexpectedly performed full SHA" }
    if ([int64]$r36Runtime.Projection.heavy_snapshot_bytes_hashed -ne 0) { throw "R36 cached heartbeat hashed heavy bytes" }
    $r36Median = Median $r36Samples
    if ($r36Median -ge $r35Median) { throw "R36 benchmark did not improve median heartbeat latency" }
    $improvementPercent = [math]::Round((($r35Median - $r36Median) / $r35Median) * 100.0, 2)
    if ($improvementPercent -lt 25.0) { throw "R36 benchmark improvement below 25 percent: $improvementPercent" }

    $stdout = Join-Path $LogRoot "scheduled.stdout.log"
    $stderr = Join-Path $LogRoot "scheduled.stderr.log"
    $pythonPath = Join-Path $InstallRoot "src"
    $argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$pythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$config' 1>>'$stdout' 2>>'$stderr'`""
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $argument
    $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $triggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
    Register-ScheduledTask -TaskName $R36TaskName -Action $action -Trigger @($triggerLogon, $triggerRepeat) -Settings $settings -Description "HANRI R36 bounded shadow supervisor; cached-stat integrity fast gate with periodic full SHA" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R36TaskName | Out-Null

    $runPath = Join-Path $StateRoot "latest_run_receipt.json"
    $beforeWrite = (Get-Item $runPath).LastWriteTimeUtc
    Start-ScheduledTask -TaskName $R36TaskName
    $deadline = [DateTime]::UtcNow.AddMinutes(3)
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Seconds 2
        if ((Get-Item $runPath).LastWriteTimeUtc -gt $beforeWrite -and (Get-ScheduledTask -TaskName $R36TaskName).State -ne "Running") { break }
    }
    if ((Get-Item $runPath).LastWriteTimeUtc -le $beforeWrite) { throw "R36 scheduler did not produce fresh receipt" }
    $scheduledRuntime = Read-Runtime $StateRoot
    Assert-R36Common $scheduledRuntime
    if ($scheduledRuntime.Run.heartbeat_fast_path -ne $true) { throw "R36 scheduled readback was not fast path" }
    if ($scheduledRuntime.Projection.heavy_snapshot_integrity_mode -ne $ExpectedCachedMode) { throw "R36 scheduled readback did not use cached stat guard" }
    if ([int64]$scheduledRuntime.Projection.heavy_snapshot_bytes_hashed -ne 0) { throw "R36 scheduled cached readback hashed heavy bytes" }

    $receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R36_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_branch = $branch
        source_commit = $head
        source_tree = $tree
        program_version = $ExpectedProgramVersion
        integrity_policy = $ExpectedIntegrityPolicy
        integrity_cached_mode = $ExpectedCachedMode
        r35_rollback_commit = "4e8c5bd68f5159c55ff604e8b4a9dbcbf4031b50"
        r35_task = $R35TaskName
        r36_task = $R36TaskName
        r35_lock_path = $R35LockPath
        r35_orphan_lock_quarantined = [bool]$r35OrphanLockQuarantine
        r35_orphan_lock_quarantine_path = $r35OrphanLockQuarantine
        r35_samples_ms = @($r35Samples)
        r36_samples_ms = @($r36Samples)
        r35_median_ms = [math]::Round($r35Median, 3)
        r36_median_ms = [math]::Round($r36Median, 3)
        heartbeat_improvement_percent = $improvementPercent
        r36_cached_bytes_hashed = [int64]$scheduledRuntime.Projection.heavy_snapshot_bytes_hashed
        r36_cached_full_sha_performed = [bool]$scheduledRuntime.Projection.heavy_snapshot_full_sha_performed
        r36_periodic_full_rehash_seconds = [int]$scheduledRuntime.Projection.heavy_snapshot_full_rehash_interval_seconds
        host_regression_tests = "PASS"
        full_sha_readback = "PASS"
        cached_stat_readback = "PASS"
        scheduler_readback = "PASS"
        rollback_script = "scripts/Restore-R35FromR36.ps1"
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        capital_permission = "DENY"
    }
    $receiptPath = Join-Path $ReceiptRoot "INSTALL_R36_RC1_RECEIPT.json"
    $receipt | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $receiptPath
    Write-Host "HANRI_R36_RUNTIME_CUTOVER_PASS"
    Write-Host "HEAD    $head"
    Write-Host "TREE    $tree"
    Write-Host "R35_MEDIAN_MS $([math]::Round($r35Median,3))"
    Write-Host "R36_MEDIAN_MS $([math]::Round($r36Median,3))"
    Write-Host "IMPROVEMENT_PERCENT $improvementPercent"
    Write-Host "RECEIPT $receiptPath"
}
catch {
    Disable-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue | Out-Null
    Stop-ScheduledTask -TaskName $R36TaskName -ErrorAction SilentlyContinue
    if ($cutoverStarted -and $r35WasEnabled) {
        $rollbackLockSafeToStart = $true
        try {
            $rollbackQuarantine = Quiesce-HanriLock $R35LockPath 10
            if ($rollbackQuarantine) {
                Write-Warning "Rollback quarantined orphan R35 lock: $rollbackQuarantine"
            }
        }
        catch {
            $rollbackLockSafeToStart = $false
            Write-Warning "Rollback lock quiesce blocked by live/invalid lock: $($_.Exception.Message)"
        }
        Enable-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue | Out-Null
        if ($rollbackLockSafeToStart) {
            Start-ScheduledTask -TaskName $R35TaskName -ErrorAction SilentlyContinue
        }
        else {
            Write-Warning "R35 task re-enabled but not force-started because lock ownership was not safely quiesced."
        }
    }
    if ($backupApp) {
        if (Test-Path $InstallRoot) { Remove-Item -Recurse -Force $InstallRoot }
        if (Test-Path $backupApp) { Move-Item -Force $backupApp $InstallRoot }
    }
    if ($backupState) {
        if (Test-Path $StateRoot) { Remove-Item -Recurse -Force $StateRoot }
        if (Test-Path $backupState) { Move-Item -Force $backupState $StateRoot }
    }
    throw
}
