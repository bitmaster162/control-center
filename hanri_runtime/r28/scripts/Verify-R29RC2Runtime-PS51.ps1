param(
    [string]$TaskName = "ControlCenter-HANRI-R29-RC2"
)

$ErrorActionPreference = "Stop"
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR29RC2"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$Config = Join-Path $InstallRoot "config\r29.rc2.windows.json"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ExpectedDigestIdentity = "HANRI R29"
$ForbiddenDigestIdentity = "HANRI R28"

$Checks = [ordered]@{}
$Checks.install_root_exists = Test-Path $InstallRoot
$Checks.config_exists = Test-Path $Config
$Checks.run_receipt_exists = Test-Path $RunReceiptPath
$Checks.ai_state_exists = Test-Path $AiStatePath
$Checks.human_digest_exists = Test-Path $DigestPath
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Checks.task_exists = [bool]$Task
$Checks.task_enabled = [bool]($Task -and $Task.State -ne "Disabled")

if ($Checks.config_exists) {
    $ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
    $Checks.config_program_version = ($ConfigObject.program_version -eq "29.0.0")
    $Checks.config_shadow_only = ($ConfigObject.shadow_only -eq $true)
    $Checks.config_external_model_api_deny = ($ConfigObject.external_model_api -eq "DENY")
    $Checks.config_can_trade_false = ($ConfigObject.can_trade -eq $false)
    $Checks.config_state_isolated = ($ConfigObject.state_root -match "ControlCenterHANRIR29RC2")
    $Checks.config_drive_output_isolated = ($ConfigObject.human_output_root -match "HANRI_R29_RC2")
}

if ($Checks.run_receipt_exists) {
    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $Checks.receipt_program_version = ($Run.program_version -eq "29.0.0")
    $Checks.receipt_self_application_false = ($Run.self_application -eq $false)
    $Checks.receipt_can_trade_false = ($Run.can_trade -eq $false)
    $Checks.receipt_external_api_zero = ([int]$Run.external_model_api_calls -eq 0)
}

if ($Checks.ai_state_exists) {
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Checks.state_program_version = ($State.program_version -eq "29.0.0")
    $Checks.state_shadow_only = ($State.shadow_only -eq $true)
    $Checks.state_self_application_false = ($State.invariants.self_application -eq $false)
    $Checks.state_can_trade_false = ($State.invariants.can_trade -eq $false)
    $Checks.state_external_api_zero = ([int]$State.invariants.external_model_api_calls -eq 0)
}

if ($Checks.human_digest_exists) {
    $Digest = Get-Content $DigestPath -Raw
    $FirstLine = (($Digest -split "`r?`n", 2)[0])
    $Checks.digest_identifies_r29 = $FirstLine.Contains($ExpectedDigestIdentity)
    $Checks.digest_does_not_identify_r28 = (-not $FirstLine.Contains($ForbiddenDigestIdentity))
}

$Failed = @($Checks.GetEnumerator() | Where-Object { $_.Value -ne $true } | ForEach-Object { $_.Key })
$Status = if ($Failed.Count -eq 0) { "PASS" } else { "FAIL" }

New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$Receipt = [ordered]@{
    schema_version = 1
    status = $Status
    release = "HANRI_R29_RC2_1"
    verified_at_utc = [DateTime]::UtcNow.ToString("o")
    checks = $Checks
    failed_checks = $Failed
    task_name = $TaskName
    run_receipt_sha256 = if (Test-Path $RunReceiptPath) { (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    ai_state_sha256 = if (Test-Path $AiStatePath) { (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    human_digest_sha256 = if (Test-Path $DigestPath) { (Get-FileHash $DigestPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    self_application = $false
    can_trade = $false
}
$ReceiptPath = Join-Path $ReceiptRoot "R29_RC2_1_RUNTIME_READBACK_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $ReceiptPath
$Receipt | ConvertTo-Json -Depth 10
if ($Status -ne "PASS") { exit 2 }
