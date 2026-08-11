from pathlib import Path


def test_r39_ps51_display_counts_are_array_safe():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "Run-R39AttentionGovernorPilot-PS51.ps1"
    ).read_text(encoding="utf-8")
    assert "$skillCandidates = @($r.proposals | Where-Object" in script
    assert "$operatorAdvice = @($r.proposals | Where-Object" in script
    assert "$systemImprovements = @($r.proposals | Where-Object" in script
    assert "$selfImprovements = @($r.proposals | Where-Object" in script
    assert "SKILL_CANDIDATES $skillCandidates" in script
    assert "OPERATOR_ADVICE $operatorAdvice" in script
    assert "SYSTEM_IMPROVEMENTS $systemImprovements" in script
