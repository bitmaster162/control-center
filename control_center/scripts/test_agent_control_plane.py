from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "control_center" / "scripts" / "build_agent_control_plane.py"
SOURCE_PATH = ROOT / "control_center" / "data" / "agent_control_sources.current.v1.json"

spec = importlib.util.spec_from_file_location("agent_control_plane", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def expect_failure(source: dict, expected_code: str) -> None:
    errors = module.validate_source(source)
    assert expected_code in errors, (expected_code, errors)


source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
out1 = module.build(source)
out2 = module.build(copy.deepcopy(source))
assert out1 == out2
assert out1["projection_kind"] == "NON_AUTHORITY_PROJECTION"
assert out1["authority_anchor"]["generation"] == "R64"
assert out1["global_dispatch"]["state"] == "BLOCKED_BY_R64_NO_FURTHER_AGENT_WORK"
assert out1["global_dispatch"]["auto_dispatch"] is False
assert out1["fleet_summary"]["slots_total"] == 13
assert out1["fleet_summary"]["historical_predecessor_slots"] == 1
assert len(out1["operator_attention"]) <= 3

slots = {row["slot"]: row for row in out1["slots"]}
assert slots["CODEX-08"]["operational_class"] == "PENDING_EXECUTION_BLOCKED"
assert slots["CLAUDE-BITUNIX"]["operational_class"] == "PENDING_OBSERVATION_BLOCKED"
assert slots["FABLE-5"]["operational_class"] == "GATED_RESERVED"
assert slots["CODEX-02"]["do_not_touch"] is True
assert all(row["dispatch_authorized"] is False for row in out1["slots"])
assert all(row["semantic_authority"] == "NONE_FROM_REGISTRY" for row in out1["slots"])
assert all(row["apply_authority"] == "NONE_FROM_REGISTRY" for row in out1["slots"])

code7 = slots["CODEX-07"]
assert code7["work_order"] == "CODEX07-R43-RETURN-PLANE-V2"
assert code7["current_route"] == "HISTORICAL_PREDECESSOR_NO_ACTION"
assert code7["source_conflict"] == "REGISTRY_R43_NEXT_SUPERSEDED_BY_CANONICAL_R59_RUNTIME"
assert code7["canonical_runtime"]["broker_status"] == "INSTALLED_AND_WATCHING"
assert code7["canonical_runtime"]["watcher_generation"] == "R59"

attention_projects = [row["project"] for row in out1["operator_attention"]]
assert "MAWorld" in attention_projects
assert "Arena" in attention_projects
assert "ContinuityOS" in attention_projects
assert "Return Plane" not in attention_projects
assert "TradingOS" not in attention_projects

bad = copy.deepcopy(source)
bad["pointer"]["effect_ceiling"]["auto_dispatch"] = True
expect_failure(bad, "effect_ceiling_mismatch:auto_dispatch")

bad = copy.deepcopy(source)
bad["return_registry"]["drive_file_id"] = "WRONG"
expect_failure(bad, "registry_drive_id_mismatch")

bad = copy.deepcopy(source)
bad["return_registry"]["rules"]["source_mutation"] = True
expect_failure(bad, "registry_rule_mismatch:source_mutation")

bad = copy.deepcopy(source)
bad["canonical_current_state"]["broker_plane"]["watcher_generation"] = "R43"
expect_failure(bad, "canonical_broker_state_mismatch")

bad = copy.deepcopy(source)
bad["canonical_role_views"]["roles"]["CODEX-07"]["state"] = "R43_TASK"
expect_failure(bad, "codex07_role_view_mismatch")

print(json.dumps({
    "status": "PASS",
    "tests": [
        "deterministic_replay",
        "r64_global_dispatch_block",
        "13_live_registry_slots",
        "canonical_r59_suppresses_r43_routing",
        "pending_execution_blocked",
        "pending_observation_blocked",
        "registry_never_semantic_or_apply",
        "tradingos_excluded_from_attention",
        "historical_return_plane_excluded_from_attention",
        "max_three_operator_attention",
        "tampered_auto_dispatch_rejected",
        "tampered_registry_identity_rejected",
        "tampered_source_mutation_rejected",
        "tampered_canonical_broker_generation_rejected",
        "tampered_codex07_role_view_rejected"
    ]
}, indent=2))
