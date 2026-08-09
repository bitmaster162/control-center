param(
    [Parameter(Mandatory=$true)][string]$CandidateId,
    [Parameter(Mandatory=$true)][ValidateSet("ACCEPT","REVISE","HOLD","REJECT")][string]$Verdict,
    [string]$Comment = "",
    [string]$Python = "python",
    [string]$Config = "$PSScriptRoot\..\config\r25.windows.json"
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path "$PSScriptRoot\..").Path
$env:PYTHONPATH = Join-Path $AppRoot "src"
$decision = [ordered]@{
    schema_version = 1
    candidate_id = $CandidateId
    verdict = $Verdict
    operator = "Robert"
    comment = $Comment
    can_trade = $false
}
$json = $decision | ConvertTo-Json -Depth 8 -Compress
& $Python -m hanri decide --config $Config --decision-json $json --process-now
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
