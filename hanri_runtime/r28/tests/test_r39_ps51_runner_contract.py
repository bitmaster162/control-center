from __future__ import annotations

from pathlib import Path


def test_r39_ps51_runner_uses_runtime_parent_of_scripts_directory():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "Run-R39AttentionGovernorPilot-PS51.ps1"
    ).read_text(encoding="utf-8")

    assert "$runtime = Split-Path -Parent $PSScriptRoot" in script
    assert "Join-Path $root 'hanri_runtime\\r28'" not in script
    assert "hanri_runtime\\hanri_runtime" not in script


def test_r39_ps51_runner_keeps_zero_effect_host_gate():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "Run-R39AttentionGovernorPilot-PS51.ps1"
    ).read_text(encoding="utf-8")

    assert "if ($r.effect_boundary.self_apply)" in script
    assert "if ($r.effect_boundary.skill_install)" in script
    assert "if ($r.effect_boundary.system_write)" in script
    assert "if ($r.effect_boundary.operator_message)" in script
    assert "if ($r.effect_boundary.auto_dispatch)" in script
    assert "EXECUTION_EFFECTS_PERFORMED 0" in script
