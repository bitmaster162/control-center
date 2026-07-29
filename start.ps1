$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8764
Set-Location $Root

$Python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  $Python = 'py'
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  $Python = 'python'
}

if ($Python) {
  if (-not (Test-Path "$Root\data\snapshot.js")) {
    & $Python "$Root\scripts\generate_snapshot_assets.py" --snapshot "$Root\data\snapshot.v1.example.json"
  }
  & $Python "$Root\scripts\validate_snapshot.py" --snapshot "$Root\data\snapshot.v1.example.json"
  Write-Host "HANRI Control Center R64-P1: http://127.0.0.1:$Port"
  Write-Host "Read-only local snapshot. Stop with Ctrl+C."
  & $Python -m http.server $Port --bind 127.0.0.1
} else {
  Write-Host "Python not found. Open the generated standalone HTML from a release package."
  exit 1
}
