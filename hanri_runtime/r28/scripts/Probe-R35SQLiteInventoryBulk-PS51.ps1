param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Config = Join-Path $SourceRoot "config\r33.windows.json"
$ExpectedBranch = "hanri/r35-sqlite-inventory-probe"

$Head = (& git -C $SourceRoot rev-parse HEAD 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R35.1 probe gate: git rev-parse failed" }
$Branch = (& git -C $SourceRoot branch --show-current 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R35.1 probe gate: git branch lookup failed" }
$Dirty = (& git -C $SourceRoot status --porcelain 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "R35.1 probe gate: git status failed" }

if ($Branch -ne $ExpectedBranch) { throw "R35.1 probe gate: expected branch $ExpectedBranch, got $Branch" }
if ($Dirty) { throw "R35.1 probe gate: worktree must be clean" }
if (-not (Test-Path $Config)) { throw "R35.1 probe gate: R33 config missing: $Config" }

$ConfigObject = Get-Content $Config -Raw | ConvertFrom-Json
if ($ConfigObject.program_version -ne "33.0.0") { throw "R35.1 probe gate: source config must be accepted R33" }
if ($ConfigObject.shadow_only -ne $true) { throw "R35.1 probe gate: shadow_only must be true" }
if ($ConfigObject.external_model_api -ne "DENY") { throw "R35.1 probe gate: external model/API must be DENY" }
if ($ConfigObject.can_trade -ne $false) { throw "R35.1 probe gate: can_trade must be false" }

Write-Host "HANRI R35.1 isolated JSON vs SQLite BULK inventory A/B (measurement only)"
Write-Host "Source: $SourceRoot"
Write-Host "HEAD:   $Head"
Write-Host "Live R33 state and Drive output are read-only; SQLite and JSON comparison writes only under TEMP."

$Before = (& git -C $SourceRoot status --porcelain 2>$null | Out-String).Trim()
$env:PYTHONPATH = Join-Path $SourceRoot "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
& $Python -m hanri.sqlite_inventory_probe_v2 --config $Config
if ($LASTEXITCODE -ne 0) { throw "R35.1 profiler failed with exit code $LASTEXITCODE" }
$After = (& git -C $SourceRoot status --porcelain 2>$null | Out-String).Trim()
if ($After -ne $Before) { throw "R35.1 probe gate: source repository changed during probe" }
