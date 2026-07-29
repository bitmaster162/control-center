$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Port = 8764
Write-Host "HANRI Control Center R64: http://127.0.0.1:$Port"
Write-Host "Read-only local snapshot. Stop with Ctrl+C."
Set-Location $Root
if (Get-Command py -ErrorAction SilentlyContinue) {
  py -m http.server $Port --bind 127.0.0.1
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
  python -m http.server $Port --bind 127.0.0.1
} else {
  Start-Process "$Root\index.html"
}
