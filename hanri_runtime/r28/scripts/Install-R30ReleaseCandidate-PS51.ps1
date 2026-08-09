param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R29TaskName = "ControlCenter-HANRI-R29-RC2",
    [string]$R30TaskName = "ControlCenter-HANRI-R30"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR30"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$ConfigSource = Join-Path $SourceRoot "config\r30.windows.json"
$ExpectedBranch = "hanri/r30-release-candidate"
$ExpectedDigestIdentity = "HANRI R30"
$ForbiddenDigestIdentity = "HANRI R29"

function GitValue([string[]]$Arguments) {
    $value = & git -C $SourceRoot @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
    return ($value | Out-String).Trim()
}

function Assert-R30RuntimeReadback(
    [string]$RunReceiptPath,
    [string]$AiStatePath,
    [string]$DigestPath,
    [string]$ProjectionReceiptPath
) {
    if (-not (Test-Path $RunReceiptPath)) { throw "R30 readback missing latest_run_receipt.json" }
    if (-not (Test-Path $AiStatePath)) { throw "R30 readback missing latest_ai_state.json" }
    if (-not (Test-Path $DigestPath)) { throw "R30 readback missing latest_human_digest.md" }
    if (-not (Test-Path $ProjectionReceiptPath)) { throw "R30 readback missing latest_projection_receipt.json" }

    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Digest = Get-Content $DigestPath -Raw
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $FirstLine = (($Digest -split "`r?`n", 2)[0])

    if ($Run.program_version -ne "30.0.0") { throw "R30 run receipt version mismatch" }
    if ($Run.can_trade -ne $false) { throw "R30 run receipt can_trade invariant failed" }
    if ($Run.self_application -ne $false) { throw "R30 run receipt self_application invariant failed" }
    if ([int]$Run.external_model_api_calls -ne 0) { throw "R30 run receipt external API invariant failed" }

    if ($State.program_version -ne "30.0.0") { throw "R30 AI-state version mismatch" }
    if ($State.shadow_only -ne $true) { throw "R30 AI-state shadow_only invariant failed" }
    if ($State.invariants.can_trade -ne $false) { throw "R30 AI-state can_trade invariant failed" }
    if ($State.invariants.self_application -ne $false) { throw "R30 AI-state self_application invariant failed" }
    if ([int]$State.invariants.external_model_api_calls -ne 0) { throw "R30 AI-state external API invariant failed" }
    if ($State.invariants.source_repository_writes -ne $false) { throw "R30 source repository write invariant failed" }

    if (-not $FirstLine.Contains($ExpectedDigestIdentity) -or $FirstLine.Contains($ForbiddenDigestIdentity)) {
        throw "R30 identity readback failed: human digest identity mismatch"
    }

    if ($Projection.program_version -ne "30.0.0") { throw "R30 projection receipt version mismatch" }
    if ($Projection.self_projection_excluded_from_archive -ne $true) { throw "R30 self-projection exclusion invariant failed" }
    if ($Projection.can_trade -ne $false) { throw "R30 projection can_trade invariant failed" }
    if ($Projection.self_application -ne $false) { throw "R30 projection self_application invariant failed" }
    if ([int]$Projection.external_model_api_calls -ne 0) { throw "R30 projection external API invariant failed" }
}

$Head = GitValue @("rev-parse", "HEAD")
$Branch = GitValue @("branch", "--show-current")
$Dirty = GitValue @("status", "--porcelain")

if ($Branch -ne $ExpectedBranch) { throw "Install gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "Install gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "Install gate: -ExpectedCommit is required with -Apply" }
if ($Apply -and $Head -ne $ExpectedCommit) { throw "Install gate: HEAD $Head does not match expected $ExpectedCommit" }

$ConfigObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "30.0.0") { throw "Config gate: program_version must be 30.0.0" }
if ($ConfigObject.shadow_only -ne $true) { throw "Config gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "Config gate: external_model_api must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "Config gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR30") { throw "Config gate: R30 state must be isolated" }
if ($ConfigObject.human_output_root -notmatch "HANRI_R30") { throw "Config gate: R30 Drive output must be isolated" }

$R29Task = Get-ScheduledTask -TaskName $R29TaskName -ErrorAction SilentlyContinue
if (-not $R29Task) { throw "Promotion gate: accepted R29 task not found: $R29TaskName" }
$R29WasEnabled = [bool]($R29Task.State -ne "Disabled")
if (-not $R29WasEnabled) { throw "Promotion gate: accepted R29 task is not enabled" }

Write-Host "HANRI R30 side-by-side install gate (PS5.1 safe)"
Write-Host "Source:  $SourceRoot"
Write-Host "HEAD:    $Head"
Write-Host "Install: $InstallRoot"
Write-Host "Accepted R29 remains enabled until R30 scheduled readback passes."

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

New-Item -ItemType Directory -Force -Path $InstallBase, $StateRoot, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousR30Backup = $null
if (Test-Path $InstallRoot) {
    $PreviousR30Backup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousR30Backup
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r30.windows.json"
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
    if ($LASTEXITCODE -ne 0) { throw "R30 compile check failed with exit code $LASTEXITCODE" }

    & $Python -m hanri once --config $Config
    if ($LASTEXITCODE -ne 0) { throw "R30 direct one-shot failed with exit code $LASTEXITCODE" }
    Assert-R30RuntimeReadback $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath

    $Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
    $TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName $R30TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R30 bounded shadow supervisor; self-observation containment and delta projection" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R30TaskName | Out-Null

    $BeforeWrite = (Get-Item $RunReceiptPath).LastWriteTimeUtc
    Start-ScheduledTask -TaskName $R30TaskName
    $SchedulerObserved = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((Test-Path $RunReceiptPath) -and ((Get-Item $RunReceiptPath).LastWriteTimeUtc -gt $BeforeWrite)) {
            $SchedulerObserved = $true
            break
        }
    }
    if (-not $SchedulerObserved) { throw "R30 scheduled-task readback did not update receipt within gate window" }

    Assert-R30RuntimeReadback $RunReceiptPath $AiStatePath $DigestPath $ProjectionReceiptPath
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R30TaskName
    if ($TaskInfo.LastTaskResult -ne 0) { throw "R30 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }

    Disable-ScheduledTask -TaskName $R29TaskName | Out-Null

    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R30_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        r30_task = $R30TaskName
        r30_last_task_result = $TaskInfo.LastTaskResult
        r29_task = $R29TaskName
        r29_was_enabled = $R29WasEnabled
        r29_disabled_only_after_r30_readback = $true
        r29_files_modified = $false
        r29_state_modified_by_installer = $false
        previous_r30_backup = $PreviousR30Backup
        digest_identity = "HANRI R30"
        projection_bytes_avoided_latest = [int64]$Projection.bytes_avoided
        run_receipt_sha256 = (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        ai_state_sha256 = (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        projection_receipt_sha256 = (Get-FileHash $ProjectionReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R29RC2FromR30.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R30_RC1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R30 RC1 installed side-by-side and scheduled readback verified."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "Accepted R29 files/state were not modified; R29 task was disabled only after R30 PASS."
}
catch {
    Disable-ScheduledTask -TaskName $R30TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($R29WasEnabled) { Enable-ScheduledTask -TaskName $R29TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
