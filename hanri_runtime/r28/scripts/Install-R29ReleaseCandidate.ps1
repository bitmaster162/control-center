param(
    [switch]$Apply,
    [Parameter(Mandatory=$false)][string]$ExpectedCommit,
    [string]$Python = "python",
    [string]$R28TaskName = "ControlCenter-HANRI-R28",
    [string]$R29TaskName = "ControlCenter-HANRI-R29"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR29"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$LogRoot = Join-Path $InstallBase "logs"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$ConfigSource = Join-Path $SourceRoot "config\r29.windows.json"
$ExpectedBranch = "hanri/r29-release-candidate"

function GitValue([string[]]$Arguments) {
    $value = & git -C $SourceRoot @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git command failed: git $($Arguments -join ' ')" }
    return ($value | Out-String).Trim()
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

Write-Host "HANRI R29 release-candidate install gate"
Write-Host "Source:  $SourceRoot"
Write-Host "HEAD:    $Head"
Write-Host "Install: $InstallRoot"
Write-Host "R28 task remains physically present; it is disabled only after R29 direct-run readback passes."

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply -ExpectedCommit $Head"
    exit 0
}

New-Item -ItemType Directory -Force -Path $InstallBase, $StateRoot, $LogRoot, $ReceiptRoot | Out-Null
$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$PreviousR29Backup = $null
if (Test-Path $InstallRoot) {
    $PreviousR29Backup = "$InstallRoot.backup.$Timestamp"
    Move-Item -Force $InstallRoot $PreviousR29Backup
}
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
Copy-Item -Recurse -Force "$SourceRoot\*" $InstallRoot

$Config = Join-Path $InstallRoot "config\r29.windows.json"
$PythonPath = Join-Path $InstallRoot "src"
$Stdout = Join-Path $LogRoot "scheduled.stdout.log"
$Stderr = Join-Path $LogRoot "scheduled.stderr.log"
$env:PYTHONPATH = $PythonPath

Set-Location $InstallRoot
& $Python -m compileall -q (Join-Path $InstallRoot "src")
if ($LASTEXITCODE -ne 0) { throw "R29 compile check failed with exit code $LASTEXITCODE" }

& $Python -m hanri once --config $Config
if ($LASTEXITCODE -ne 0) { throw "R29 direct one-shot failed with exit code $LASTEXITCODE" }

$DirectReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
if (-not (Test-Path $DirectReceiptPath)) { throw "R29 readback missing latest_run_receipt.json" }
if (-not (Test-Path $AiStatePath)) { throw "R29 readback missing latest_ai_state.json" }
$DirectReceipt = Get-Content $DirectReceiptPath -Raw | ConvertFrom-Json
$AiState = Get-Content $AiStatePath -Raw | ConvertFrom-Json

if ($DirectReceipt.program_version -ne "29.0.0") { throw "R29 readback version mismatch: $($DirectReceipt.program_version)" }
if ($DirectReceipt.can_trade -ne $false) { throw "R29 readback can_trade invariant failed" }
if ($DirectReceipt.self_application -ne $false) { throw "R29 readback self_application invariant failed" }
if ([int]$DirectReceipt.external_model_api_calls -ne 0) { throw "R29 readback external API invariant failed" }
if ($AiState.shadow_only -ne $true) { throw "R29 AI-state shadow_only invariant failed" }
if ($AiState.invariants.can_trade -ne $false) { throw "R29 AI-state can_trade invariant failed" }
if ($AiState.invariants.self_application -ne $false) { throw "R29 AI-state self_application invariant failed" }
if ([int]$AiState.invariants.external_model_api_calls -ne 0) { throw "R29 AI-state external API invariant failed" }

$R28Task = Get-ScheduledTask -TaskName $R28TaskName -ErrorAction SilentlyContinue
$R28WasEnabled = $false
if ($R28Task) { $R28WasEnabled = ($R28Task.State -ne "Disabled") }

$Argument = "-NoProfile -ExecutionPolicy Bypass -Command `"`$env:PYTHONPATH='$PythonPath'; Set-Location '$InstallRoot'; & '$Python' -m hanri once --config '$Config' 1>>'$Stdout' 2>>'$Stderr'`""
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Argument
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$TriggerRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$Settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $R29TaskName -Action $Action -Trigger @($TriggerLogon, $TriggerRepeat) -Settings $Settings -Description "HANRI R29 bounded shadow supervisor; contextual secret-boundary hardening" -Force | Out-Null

try {
    if ($R28Task -and $R28WasEnabled) { Disable-ScheduledTask -TaskName $R28TaskName | Out-Null }
    Enable-ScheduledTask -TaskName $R29TaskName | Out-Null

    $BeforeWrite = (Get-Item $DirectReceiptPath).LastWriteTimeUtc
    Start-ScheduledTask -TaskName $R29TaskName
    $SchedulerObserved = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if ((Test-Path $DirectReceiptPath) -and ((Get-Item $DirectReceiptPath).LastWriteTimeUtc -gt $BeforeWrite)) {
            $SchedulerObserved = $true
            break
        }
    }
    if (-not $SchedulerObserved) { throw "R29 scheduled-task readback did not update receipt within gate window" }

    $ScheduledReceipt = Get-Content $DirectReceiptPath -Raw | ConvertFrom-Json
    if ($ScheduledReceipt.program_version -ne "29.0.0" -or $ScheduledReceipt.can_trade -ne $false -or $ScheduledReceipt.self_application -ne $false -or [int]$ScheduledReceipt.external_model_api_calls -ne 0) {
        throw "R29 scheduled-task invariant readback failed"
    }

    $TaskInfo = Get-ScheduledTaskInfo -TaskName $R29TaskName
    if ($TaskInfo.LastTaskResult -ne 0) { throw "R29 scheduled task LastTaskResult=$($TaskInfo.LastTaskResult)" }

    $Receipt = [ordered]@{
        schema_version = 1
        status = "PASS"
        release = "HANRI_R29_RC1"
        installed_at_utc = [DateTime]::UtcNow.ToString("o")
        source_commit = $Head
        source_branch = $Branch
        install_root = $InstallRoot
        state_root = $StateRoot
        r29_task = $R29TaskName
        r29_last_task_result = $TaskInfo.LastTaskResult
        r28_task = $R28TaskName
        r28_was_enabled = $R28WasEnabled
        r28_disabled_after_r29_readback = [bool]($R28Task -and $R28WasEnabled)
        previous_r29_backup = $PreviousR29Backup
        direct_receipt_sha256 = (Get-FileHash $DirectReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        self_application = $false
        external_model_api_calls = 0
        can_trade = $false
        rollback = "scripts/Restore-R28FromR29.ps1"
    }
    $ReceiptPath = Join-Path $ReceiptRoot "INSTALL_R29_RC1_RECEIPT.json"
    $Receipt | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $ReceiptPath
    Write-Host "PASS: HANRI R29 RC1 installed and scheduler readback verified."
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "R28 was not deleted. Rollback remains available."
}
catch {
    Disable-ScheduledTask -TaskName $R29TaskName -ErrorAction SilentlyContinue | Out-Null
    if ($R28Task -and $R28WasEnabled) { Enable-ScheduledTask -TaskName $R28TaskName -ErrorAction SilentlyContinue | Out-Null }
    throw
}
