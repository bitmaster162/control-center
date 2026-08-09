param(
    [string]$Python = "python",
    [string]$Config = "$PSScriptRoot\..\config\r25.windows.json"
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path "$PSScriptRoot\..").Path
$env:PYTHONPATH = Join-Path $AppRoot "src"
& $Python -m hanri status --config $Config
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
