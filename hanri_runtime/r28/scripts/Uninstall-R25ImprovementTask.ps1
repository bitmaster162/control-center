param(
    [switch]$Apply,
    [string]$TaskName = "ControlCenter-HANRI-R25"
)

$ErrorActionPreference = "Stop"
$InstallRoot = Join-Path $env:LOCALAPPDATA "ControlCenterHANRIR25\app"
if (-not $Apply) {
    Write-Host "DRY RUN: would remove scheduled task $TaskName and installed app $InstallRoot."
    Write-Host "State, decisions and Drive reports would be preserved."
    exit 0
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
if (Test-Path $InstallRoot) { Remove-Item -Recurse -Force $InstallRoot }
Write-Host "Removed task and installed app. State was preserved."
