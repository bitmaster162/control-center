param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R29RC1TaskName = "ControlCenter-HANRI-R29",
    [string]$R29RC2TaskName = "ControlCenter-HANRI-R29-RC2"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR29RC2"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$ConfigSource = Join-Path $SourceRoot "config\r29.rc2.windows.json"
$ExpectedBranch = "hanri/r29-release-candidate-2.1"
$ExpectedDigestIdentity = "HANRI R29"
$ForbiddenDigestIdentity = "HANRI R28"

function GitValue([string[]]$Arguments) {
    $value = & git -C $SourceRoot @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
    return ($value | Out-String).Trim()
}

function Assert-R29RuntimeReadback([string]$RunReceiptPath, [string]$AiStatePath, [string]$DigestPath) {
    if (-not (Test-Path $RunReceiptPath)) { throw "RC2 readback missing latest_run_receipt.json" }
    if (-not (Test-Path $AiStatePath)) { throw "RC2 readback missing latest_ai_state.json" }
    if (-not (Test-Path $DigestPath)) { throw "RC2 readback missing latest_human_digest.md" }

    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Digest = Get-Content $DigestPath -Raw
    $FirstLine = (($Digest -split "`r?`n", 2)[0])

    if ($Run.program_version -ne "29.0.0") { throw "RC2 run receipt version mismatch" }
    if ($Run.can_trade -ne $false) { throw "RC2 run receipt can_trade invariant failed" }
    if ($Run.self_application -ne $false) { throw "RC2 run receipt self_application invariant failed" }
    if ([int]$Run.external_model_api_calls -ne 0) { throw "RC2 run receipt external API invariant failed" }

    if ($State.program_version -ne "29.0.0") { throw "RC2 AI-state version mismatch" }
    if ($State.shadow_only -ne $true) { throw "RC2 AI-state shadow_only invariant failed" }
    if ($State.invariants.can_trade -ne $false) { throw "RC2 AI-state can_trade invariant failed" }
    if ($State.invariants.self_application -ne $false) { throw "RC2 AI-state self_application invariant failed" }
    if ([int]$State.invariants.external_model_api_calls -ne 0) { throw "RC2 AI-state external API invariant failed" }

    if (-not $FirstLine.Contains($ExpectedDigestIdentity) -or $FirstLine.Contains($ForbiddenDigestIdentity)) {
        throw "RC2 identity readback failed: human digest identity mismatch"
    }
}

$Head = GitValue @("rev-parse", "HEAD")
$Branch = GitValue @("branch", "--show-current")
$Dirty = GitValue @("status", "--porcelain")

if ($Branch -ne $ExpectedBranch) { throw "Install gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "Install gate: worktree must be clean" }
if ($Apply -and [string]::IsNullOrWhiteSpace($ExpectedCommit)) { throw "Install gate: -ExpectedCommit is required with -Apply" }
if ($Apply -and $Head -ne $ExpectedCommit) { throw "Install gate: HEAD $Head does not match expected $ExpectedCommit" }

$ConfigObject = Get-Content $ConfigSource -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "29.0.0") { throw "Config gate: program_version must be 29.0.0" }
if ($ConfigObject.shadow_only -ne $true) { throw "Config gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "Config gate: external_model_api must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "Config gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR29RC2") { throw "Config gate: RC2 state must be isolated" }
if ($ConfigObject.human_output_root -notmatch "HANRI_R29_RC2") { throw "Config gate: RC2 Drive output must be isolated" }

Write-Host "HANRI R29 RC2 side-by-side install gate (PS5.1 safe)"
Write-Host "Source: $SourceRoot"
Write-Host "HEAD:   $Head"
Write-Host "Install: $InstallRoot"
Write-Host "RC1 files/state remain untouched until RC2 scheduled readback passes."

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

$RC1Task = Get-ScheduledTask -TaskName $R29RC1TaskName -ErrorAction SilentlyContinue
$RC1WasEnabled = [bool]($RC1Task -and $RC1Task.State -ne "Disabled")

New-Item -ItemType Directory -Force -Path $InstallBase, $StateRoot, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousRC2Backup = $null
if (Test-Path $InstallRoot) {
    $PreviousRC2Backup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousRC2Backup
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r29.rc2.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$env:PYTHONPATH = $PythonPath

try {
    Set-Location $InstallRoot
    & $Python -m compileall -q (Join-Path $InstallRoot "src")
    if ($LASTEXITCODE -ne 0) { throw "RC2 compile check failed with exit code $LASTEXITCODE" }

    & $Python -m hanri once --config $Config
    if ($LASTEXITCODE -ne 0) { throw "RC2 direct one-shot failed with exit code $LASTEXITCODE" }
    Assert-R29RuntimeReadback $RunReceiptPath $AiStatePath $DigestPath

    $Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
    $Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
    $TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
    $Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
    Register-ScheduledTask -TaskName $R29RC2TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R29 RC2 bounded shadow supervisor; identity + secret-boundary hardening" -Force | Out-Null
    Enable-ScheduledTask -TaskName $R29RC2TaskName | Out-Null

    $BeforeWrite = (Get-Item $RunReceiptPath).LastWriteTimeUtc
    Start-ScheduledTask -TaskName $R29RC2TaskName
    $SchedulerObserved = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((Test-Path $RunReceiptPath) -and ((Get-Item $RunReceiptPath).LastWriteTimeUtc -gt $BeforeWrite)) {
            $SchedulerObserved = $true
            break
        }
    }
    if (-not $SchedulerObserved) { throw "RC2 scheduled-task readback did not update receipt within gate window" }

    Assert-R29RuntimeReadback $RunReceiptPath $AiStatePath $DigestPath
    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R29RC2TaskName
    if ($TaskInfo.LastTaskResult -ne 0) { throw "RC2 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }

    if ($RC1Task -and $RC1WasEnabled) { Disable-ScheduledTask -TaskName $R29RC1TaskName | Out-Null }

    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R29_RC2_1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        rc2_task = $R29RC2TaskName
        rc2_last_task_result = $TaskInfo.LastTaskResult
        rc1_task = $R29RC1TaskName
        rc1_was_enabled = $RC1WasEnabled
        rc1_disabled_only_after_rc2_readback = [bool]($RC1Task -and $RC1WasEnabled)
        rc1_files_modified = $false
        rc1_state_modified_by_installer = $false
        previous_rc2_backup = $PreviousRC2Backup
        digest_identity = "HANRI R29"
        run_receipt_sha256 = (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        ai_state_sha256 = (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R29RC1FromRC2.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R29_RC2_1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R29 RC2.1 installed side-by-side and scheduled readback verified."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "RC1 files/state were not modified; RC1 task was disabled only after RC2 PASS."
}
catch {
    Disable-ScheduledTask -TaskName $R29RC2TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($RC1Task -and $RC1WasEnabled) { Enable-ScheduledTask -TaskName $R29RC1TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
