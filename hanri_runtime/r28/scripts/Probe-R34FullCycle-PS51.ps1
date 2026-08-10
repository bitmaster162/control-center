param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Config = Join-Path $SourceRoot "config\r33.windows.json"
$ExpectedBranch = "hanri/r34-full-cycle-profiler"

$Head = (& git -C $SourceRoot rev-parse HEAD 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R34 probe gate: git rev-parse failed" }
$Branch = (& git -C $SourceRoot branch --show-current 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R34 probe gate: git branch lookup failed" }
$Dirty = (& git -C $SourceRoot status --porcelain 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R34 probe gate: git status failed" }

if ($Branch -ne $ExpectedBranch) { throw "R34 probe gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "R34 probe gate: worktree must be clean" }
if (-not (Test-Path $Config)) { throw "R34 probe gate: R33 config missing: $Config" }

$ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "33.0.0") { throw "R34 probe gate: source config must be R33" }
if ($ConfigObject.shadow_only -ne $true) { throw "R34 probe gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "R34 probe gate: external model/API must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "R34 probe gate: can_trade must be false" }
if ($ConfigObject.state_root -notmatch "ControlCenterHANRIR33") { throw "R34 probe gate: accepted R33 state root required" }

Write-Host "HANRI R34 isolated full-cycle profiler (measurement only)"
Write-Host "Source: $SourceRoot"
Write-Host "HEAD:   $Head"
Write-Host "Live R33 state and Drive output are read-only; replay writes only under TEMP."

$env:PYTHONPATH = Join-Path $SourceRoot "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
& $Python -m hanri.full_cycle_profiler --config $Config
if ($LASTEXITCODE -ne 0) { throw "R34 profiler failed with exit code $LASTEXITCODE" }

$DirtyAfter = (& git -C $SourceRoot status --porcelain 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R34 probe gate: post-probe git status failed" }
if ($DirtyAfter) { throw "R34 probe gate: source worktree changed during probe" }
