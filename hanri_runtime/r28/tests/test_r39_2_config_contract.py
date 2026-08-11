from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r39_2_default_bindings_are_derived_from_r36_surfaces():
    r36 = json.loads((ROOT / "config" / "r36.windows.json").read_text(encoding="utf-8"))
    adapters = json.loads((ROOT / "config" / "r39.2.producer-adapters.json").read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in adapters["sources"]}

    assert sources["R36_RUNTIME_STATE"]["path"] == r36["state_root"]
    assert sources["R23_RETURN_SYNC_STATE"]["path"] == r36["r23_state_path"]
    assert sources["R36_OPERATOR_EVENT_INBOX"]["path"] == r36["event_inbox"]
    assert sources["R36_AGENT_RETURN_INTAKE"]["path"] == r36["archive_frontier"]["current_paths"][0]


def test_r39_2_config_does_not_install_or_call_providers():
    adapters = json.loads((ROOT / "config" / "r39.2.producer-adapters.json").read_text(encoding="utf-8"))
    boundary = adapters["effect_boundary"]
    assert boundary["producer_reads_only"] is True
    assert boundary["attention_inbox_write_only"] is True
    assert boundary["provider_calls"] is False
    assert boundary["stable_roots_modified"] is False
    assert boundary["r36_runtime_modified"] is False
    assert boundary["self_apply"] is False
    assert boundary["skill_install"] is False
    assert boundary["system_write"] is False
    assert boundary["operator_message"] is False
    assert boundary["auto_dispatch"] is False
    assert boundary["external_messages"] is False
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"


def test_r39_2_runner_is_execution_zero_and_has_no_scheduler_install():
    script = (ROOT / "scripts" / "Run-R39.2ProducerAdapters-PS51.ps1").read_text(encoding="utf-8")
    assert "EXECUTION_EFFECTS_PERFORMED 0" in script
    assert "PROVIDER_CALLS 0" in script
    assert "Register-ScheduledTask" not in script
    assert "New-ScheduledTask" not in script
    assert "schtasks" not in script.lower()
