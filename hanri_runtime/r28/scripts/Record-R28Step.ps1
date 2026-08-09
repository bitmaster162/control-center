param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [Parameter(Mandatory=$true)][string]$StepId,
    [Parameter(Mandatory=$true)][ValidateSet("TASK_START","STEP_START","EVIDENCE_ADDED","TOOL_RESULT","STEP_END","TASK_END","OPERATOR_FEEDBACK","STATE_SNAPSHOT","DISPATCH","SIMULATION_RESULT","ARCHIVE_PROMOTION","ARCHIVE_FRONTIER_ADVANCE","ARCHIVE_CAUSAL_SPINE","TRUTH_KERNEL_AUDIT")][string]$EventType,
    [string]$Actor = "LOCAL_AGENT",
    [string]$Goal = "",
    [string]$HumanSummary = "",
    [string]$ChecksJson = "{}",
    [int]$RecursionDepth = 0,
    [string]$Python = "python",
    [string]$Config = "$PSScriptRoot\..\config\r28.windows.json"
)

$ErrorActionPreference = "Stop"
$AppRoot = (Resolve-Path "$PSScriptRoot\..").Path
$env:PYTHONPATH = Join-Path $AppRoot "src"
$checks = $ChecksJson | ConvertFrom-Json
$event = [ordered]@{
    schema_version = 1
    task_id = $TaskId
    step_id = $StepId
    event_type = $EventType
    actor = $Actor
    goal = $Goal
    human_summary = $HumanSummary
    recursion_depth = $RecursionDepth
    checks = $checks
    evidence_refs = @()
    can_trade = $false
}
$json = $event | ConvertTo-Json -Depth 12 -Compress
& $Python -m hanri record --config $Config --event-json $json --process-now
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
