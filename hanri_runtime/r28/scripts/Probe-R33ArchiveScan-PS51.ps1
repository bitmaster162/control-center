param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$SourceRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Config = Join-Path $SourceRoot "config\r32.windows.json"
$PythonPath = Join-Path $SourceRoot "src"

$env:PYTHONPATH = $PythonPath
& $Python -m hanri.archive_scan_profiler --config $Config
if ($LASTEXITCODE -ne 0) {
    throw "R33 archive scan profiler failed with exit code $LASTEXITCODE"
}
