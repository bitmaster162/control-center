param(
    [string]$Python = "python",
    [string]$Config = "$PSScriptRoot\..\config\r28.windows.json"
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path "$PSScriptRoot\..").Path
$env:PYTHONPATH = Join-Path $AppRoot "src"
& $Python -m hanri once --config $Config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
