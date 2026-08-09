param(
    [string]$Python = "python",
    [string]$TaskName = "ControlCenter-HANRI-R29"
)

$ErrorActionPreference = "Stop"
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR29"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$Config = Join-Path $InstallRoot "config\r29.windows.json"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"

$Checks = [ordered]@{}
$Checks.install_root_exists = Test-Path $InstallRoot
$Checks.config_exists = Test-Path $Config
$Checks.run_receipt_exists = Test-Path $RunReceiptPath
$Checks.ai_state_exists = Test-Path $AiStatePath
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Checks.task_exists = [bool]$Task
$Checks.task_enabled = [bool]($Task -and $Task.State -ne "Disabled")

if ($Checks.config_exists) {
    $ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
    $Checks.config_program_version = ($ConfigObject.program_version -eq "29.0.0")
    $Checks.config_shadow_only = ($ConfigObject.shadow_only -eq $true)
    $Checks.config_external_model_api_deny = ($ConfigObject.external_model_api -eq "DENY")
    $Checks.config_can_trade_false = ($ConfigObject.can_trade -eq $false)
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

$Failed = @($Checks.GetEnumerator() | Where-Object { $_.Value -ne $true } | ForEach-Object { $_.Key })
$Status = if ($Failed.Count -eq 0) { "PASS" } else { "FAIL" }

New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$Receipt = [ordered]@{
    schema_version = 1
    status = $Status
    verified_at_utc = [DateTime]::UtcNow.ToString("o")
    checks = $Checks
    failed_checks = $Failed
    task_name = $TaskName
    run_receipt_sha256 = if (Test-Path $RunReceiptPath) { (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    ai_state_sha256 = if (Test-Path $AiStatePath) { (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    self_application = $false
    can_trade = $false
}
$ReceiptPath = Join-Path $ReceiptRoot "R29_RUNTIME_READBACK_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $ReceiptPath
$Receipt | ConvertTo-Json -Depth 10
if ($Status -ne "PASS") { exit 2 }
