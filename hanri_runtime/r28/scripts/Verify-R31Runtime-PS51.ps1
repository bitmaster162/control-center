param(
    [string]$TaskName = "ControlCenter-HANRI-R31"
)

$ErrorActionPreference = "Stop"
$InstallBase = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR31"
$InstallRoot = Join-Path $InstallBase "app"
$StateRoot = Join-Path $InstallBase "state"
$ReceiptRoot = Join-Path $InstallBase "receipts"
$Config = Join-Path $InstallRoot "config\r31.windows.json"
$RunReceiptPath = Join-Path $StateRoot "latest_run_receipt.json"
$AiStatePath = Join-Path $StateRoot "latest_ai_state.json"
$DigestPath = Join-Path $StateRoot "latest_human_digest.md"
$ProjectionReceiptPath = Join-Path $StateRoot "latest_projection_receipt.json"
$ExpectedDigestIdentity = "HANRI R31"
$ForbiddenDigestIdentity = "HANRI R30"
$ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"

$Checks = [ordered]@{}
$Checks.install_root_exists = Test-Path $InstallRoot
$Checks.config_exists = Test-Path $Config
$Checks.run_receipt_exists = Test-Path $RunReceiptPath
$Checks.ai_state_exists = Test-Path $AiStatePath
$Checks.human_digest_exists = Test-Path $DigestPath
$Checks.projection_receipt_exists = Test-Path $ProjectionReceiptPath
$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$Checks.task_exists = [bool]$Task
$Checks.task_enabled = [bool]($Task -and $Task.State -ne "Disabled")

$Run = $null
$State = $null
$Projection = $null
if ($Checks.config_exists) {
    $ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
    $Checks.config_program_version = ($ConfigObject.program_version -eq "31.0.0")
    $Checks.config_shadow_only = ($ConfigObject.shadow_only -eq $true)
    $Checks.config_external_model_api_deny = ($ConfigObject.external_model_api -eq "DENY")
    $Checks.config_can_trade_false = ($ConfigObject.can_trade -eq $false)
    $Checks.config_state_isolated = ($ConfigObject.state_root -match "ControlCenterHANRIR31")
    $Checks.config_drive_output_isolated = ($ConfigObject.human_output_root -match "HANRI_R31")
}

if ($Checks.run_receipt_exists) {
    $Run = Get-Content $RunReceiptPath -Raw | ConvertFrom-Json
    $Checks.receipt_program_version = ($Run.program_version -eq "31.0.0")
    $Checks.receipt_self_application_false = ($Run.self_application -eq $false)
    $Checks.receipt_can_trade_false = ($Run.can_trade -eq $false)
    $Checks.receipt_external_api_zero = ([int]$Run.external_model_api_calls -eq 0)
}

if ($Checks.ai_state_exists) {
    $State = Get-Content $AiStatePath -Raw | ConvertFrom-Json
    $Checks.state_program_version = ($State.program_version -eq "31.0.0")
    $Checks.state_shadow_only = ($State.shadow_only -eq $true)
    $Checks.state_self_application_false = ($State.invariants.self_application -eq $false)
    $Checks.state_can_trade_false = ($State.invariants.can_trade -eq $false)
    $Checks.state_external_api_zero = ([int]$State.invariants.external_model_api_calls -eq 0)
    $Checks.state_repo_writes_false = ($State.invariants.source_repository_writes -eq $false)
}

if ($Checks.human_digest_exists) {
    $Digest = Get-Content $DigestPath -Raw
    $FirstLine = (($Digest -split "`r?`n", 2)[0])
    $Checks.digest_identifies_r31 = ($FirstLine.Contains($ExpectedDigestIdentity))
    $Checks.digest_does_not_identify_r30 = (-not $FirstLine.Contains($ForbiddenDigestIdentity))
}

if ($Checks.projection_receipt_exists) {
    $Projection = Get-Content $ProjectionReceiptPath -Raw | ConvertFrom-Json
    $Checks.projection_program_version = ($Projection.program_version -eq "31.0.0")
    $Checks.projection_self_exclusion_true = ($Projection.self_projection_excluded_from_archive -eq $true)
    $Checks.projection_self_application_false = ($Projection.self_application -eq $false)
    $Checks.projection_can_trade_false = ($Projection.can_trade -eq $false)
    $Checks.projection_external_api_zero = ([int]$Projection.external_model_api_calls -eq 0)
    $Checks.projection_material_policy_v2 = ($Projection.material_policy.version -eq $ExpectedMaterialPolicy)
    $Ignored = @($Projection.material_policy.latest_ai_state_ignored_top_level_keys)
    $Checks.projection_ignores_only_top_level_new_events = ($Ignored.Count -eq 1 -and $Ignored[0] -eq "new_events")
    $Checks.projection_nested_new_events_material = ($Projection.material_policy.nested_new_events_remains_material -eq $true)
    $Checks.projection_findings_material = ($Projection.material_policy.new_findings_remains_material -eq $true)
    $Checks.projection_candidates_material = ($Projection.material_policy.new_candidates_remains_material -eq $true)
    $Checks.projection_decisions_material = ($Projection.material_policy.new_decisions_remains_material -eq $true)
    $Checks.projection_stop_reasons_material = ($Projection.material_policy.stop_reasons_remains_material -eq $true)
    $Checks.projection_current_run_envelope_always = ($Projection.material_policy.current_run_envelope_always_projected -eq $true)
    $Checks.projection_envelope_exists = [bool]$Projection.ai_state_run_envelope
}

if ($Run -and $Projection -and $Projection.ai_state_run_envelope) {
    $Envelope = $Projection.ai_state_run_envelope
    $Checks.envelope_run_id_matches_receipt = ($Envelope.run_id -eq $Run.run_id)
    $Checks.envelope_new_events_matches_receipt = ([int]$Envelope.new_events -eq [int]$Run.events_processed)
    $Checks.envelope_new_findings_matches_receipt = ([int]$Envelope.new_findings -eq [int]$Run.findings_generated)
    $Checks.envelope_new_candidates_matches_receipt = ([int]$Envelope.new_candidates -eq [int]$Run.candidates_generated)
    $Checks.envelope_new_decisions_matches_receipt = ([int]$Envelope.new_decisions -eq [int]$Run.decisions_processed)
    $Checks.envelope_state_sha_matches_receipt = ($Envelope.source_sha256 -eq $Run.state_sha256)
    $Checks.envelope_material_digest_matches_projection = ($Envelope.material_digest -eq $Projection.material_digests.'latest_ai_state.json')
    $Checks.envelope_shadow_only = ($Envelope.shadow_only -eq $true)
    $Checks.envelope_self_application_false = ($Envelope.self_application -eq $false)
    $Checks.envelope_external_api_zero = ([int]$Envelope.external_model_api_calls -eq 0)
    $Checks.envelope_repo_writes_false = ($Envelope.source_repository_writes -eq $false)
    $Checks.envelope_can_trade_false = ($Envelope.can_trade -eq $false)
}

$Failed = @($Checks.GetEnumerator() | Where-Object { $_.Value -ne $true } | ForEach-Object { $_.Key })
$Status = if ($Failed.Count -eq 0) { "PASS" } else { "FAIL" }

New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$Receipt = [ordered]@{
    schema_version = 1
    status = $Status
    release = "HANRI_R31_RC1"
    verified_at_utc = [DateTime]::UtcNow.ToString("o")
    checks = $Checks
    failed_checks = $Failed
    task_name = $TaskName
    run_receipt_sha256 = if (Test-Path $RunReceiptPath) { (Get-FileHash $RunReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    ai_state_sha256 = if (Test-Path $AiStatePath) { (Get-FileHash $AiStatePath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    human_digest_sha256 = if (Test-Path $DigestPath) { (Get-FileHash $DigestPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    projection_receipt_sha256 = if (Test-Path $ProjectionReceiptPath) { (Get-FileHash $ProjectionReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { $null }
    self_application = $false
    can_trade = $false
}
$ReceiptPath = Join-Path $ReceiptRoot "R31_RUNTIME_READBACK_RECEIPT.json"
$Receipt | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 $ReceiptPath
$Receipt | ConvertTo-Json -Depth 12
if ($Status -ne "PASS") { exit 2 }
