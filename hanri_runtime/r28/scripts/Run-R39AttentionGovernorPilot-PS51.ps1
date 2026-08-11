param(
  [string]$OutputPath = "$env:LOCALAPPDATA\ControlCenterHANRIR39\receipts\R39_ATTENTION_OVER_ATTENTION_RECEIPT.json"
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $runtime 'src'
$policy = Join-Path $runtime 'config\r39.attention-governor.json'
$input = Join-Path $runtime 'data\r39_attention_fixture.json'
$tests = Join-Path $runtime 'tests\test_r39_attention_governor.py'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputPath) | Out-Null
python -m pytest -q $tests
python -m hanri.attention_governor_cli --input $input --policy $policy --output $OutputPath | Out-Null
$r = Get-Content -Raw -Encoding UTF8 $OutputPath | ConvertFrom-Json
if (-not $r.meta_audit.attention_over_attention) { throw 'attention_over_attention=false' }
if (-not $r.meta_audit.coverage_complete) { throw 'coverage_complete=false' }
foreach ($d in @('SELF','AGENT','SYSTEM','OPERATOR')) {
  if ([int]$r.meta_audit.domain_counts.$d -lt 1) { throw "missing_domain:$d" }
}
if (-not $r.capabilities.agent_skill_factory) { throw 'agent_skill_factory=false' }
if (-not $r.capabilities.operator_advice) { throw 'operator_advice=false' }
if (-not $r.capabilities.system_improvement_proposals) { throw 'system_improvement_proposals=false' }
if (-not $r.capabilities.self_audit) { throw 'self_audit=false' }
if (-not $r.effect_boundary.proposal_only) { throw 'proposal_only=false' }
if ($r.effect_boundary.self_apply) { throw 'self_apply=true' }
if ($r.effect_boundary.skill_install) { throw 'skill_install=true' }
if ($r.effect_boundary.system_write) { throw 'system_write=true' }
if ($r.effect_boundary.operator_message) { throw 'operator_message=true' }
if ($r.effect_boundary.auto_dispatch) { throw 'auto_dispatch=true' }
if ($r.effect_boundary.can_trade) { throw 'can_trade=true' }
if ($r.effect_boundary.capital_permission -ne 'DENY') { throw 'capital_permission_not_DENY' }
$skillCandidates = @($r.proposals | Where-Object { $_.kind -eq 'SKILL_CANDIDATE' }).Count
$operatorAdvice = @($r.proposals | Where-Object { $_.kind -eq 'OPERATOR_ADVICE' }).Count
$systemImprovements = @($r.proposals | Where-Object { $_.kind -eq 'SYSTEM_IMPROVEMENT' }).Count
$selfImprovements = @($r.proposals | Where-Object { $_.kind -eq 'HANRI_SELF_IMPROVEMENT' }).Count
Write-Host 'HANRI_R39_ATTENTION_OVER_ATTENTION_PASS'
Write-Host "RECEIPT $OutputPath"
Write-Host "FINDINGS $(@($r.findings).Count)"
Write-Host "PROPOSALS $(@($r.proposals).Count)"
Write-Host "SKILL_CANDIDATES $skillCandidates"
Write-Host "OPERATOR_ADVICE $operatorAdvice"
Write-Host "SYSTEM_IMPROVEMENTS $systemImprovements"
Write-Host "SELF_IMPROVEMENTS $selfImprovements"
Write-Host 'EXECUTION_EFFECTS_PERFORMED 0'
