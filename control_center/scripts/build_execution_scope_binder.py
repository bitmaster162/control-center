from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "control_center.execution_scope_binder.v1"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
EXPECTED_CURRENT_STATE_SHA = "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd"
EXPECTED_ROLE_VIEWS_SHA = "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(source: dict[str, Any], command: dict[str, Any], effect: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if source.get("schema") != "control_center.execution_scope_sources.v1":
        errors.append("source_schema_mismatch")
    anchor = source.get("authority_anchor", {})
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE" or anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA or anchor.get("provider_readback") != "all_exact":
        errors.append("r64_anchor_mismatch")
    state = source.get("canonical_current_state", {})
    role = source.get("canonical_role_views", {})
    if state.get("sha256") != EXPECTED_CURRENT_STATE_SHA or state.get("broker_status") != "INSTALLED_AND_WATCHING" or state.get("watcher_generation") != "R59":
        errors.append("canonical_broker_state_mismatch")
    if role.get("sha256") != EXPECTED_ROLE_VIEWS_SHA or role.get("codex07_lane") != "Return Plane / broker hardening" or not str(role.get("codex07_state", "")).startswith("R59_"):
        errors.append("canonical_role_view_mismatch")
    if command.get("schema") != "control_center.command_queue.v1" or command.get("summary", {}).get("human_now") != 0 or command.get("queues", {}).get("HUMAN_NOW") != []:
        errors.append("command_queue_must_have_no_human_gate")
    if command.get("queues", {}).get("HISTORICAL_QUEUE") != ["CMD::CODEX07-R43-RETURN-PLANE-V2"]:
        errors.append("historical_r43_binding_missing")
    if effect.get("schema") != "control_center.effect_readback_plane.v1" or effect.get("summary", {}).get("effect_candidates_total") != 0 or effect.get("effect_candidates") != []:
        errors.append("effect_plane_must_have_zero_candidates")
    safety = source.get("safety", {})
    if safety.get("execution_authorized") is not False or safety.get("auto_execute") is not False or safety.get("can_trade") is not False or safety.get("capital_permission") != "DENY" or safety.get("deploy_permission") != "DENY" or safety.get("self_application") is not False:
        errors.append("safety_ceiling_mismatch")
    divergences = source.get("known_divergences", [])
    if not any(x.get("id") == "BROKER_REGISTRY_MUTATION_SEMANTICS_DIVERGENCE" for x in divergences):
        errors.append("required_semantics_divergence_missing")
    if errors:
        raise ValueError(";".join(errors))

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_READ_ONLY_BINDING",
        "observed_at": source.get("observed_at"),
        "authority_anchor": anchor,
        "verdict": "NO_EXECUTABLE_GATE_STALE_R43_PREDECESSOR",
        "canonical_runtime": {
            "broker_status": state.get("broker_status"),
            "watcher_generation": state.get("watcher_generation"),
            "role_lane": role.get("codex07_lane"),
            "role_state": role.get("codex07_state"),
            "runtime_liveness_current": "UNVERIFIED_PROVIDER_READBACK_REQUIRED",
            "canonical_snapshot_is_not_fresh_liveness_proof": True,
        },
        "binding": {
            "historical_work_order": "CODEX07-R43-RETURN-PLANE-V2",
            "historical_gate_suppressed": True,
            "current_human_gate_count": 0,
            "current_effect_candidate_count": 0,
            "execution_scope_bound": False,
            "provider_target_bound": False,
            "mutation_set_bound": False,
            "executor_bound": False,
            "execution_authorized": False,
            "execution_ready": False,
            "blockers": [
                "NO_CURRENT_EFFECT_GATE",
                "R43_IS_HISTORICAL_PREDECESSOR",
                "CURRENT_RUNTIME_LIVENESS_NOT_FRESHLY_VERIFIED",
                "EXACT_PROVIDER_MUTATION_SEMANTICS_REQUIRE_READ_ONLY_VERIFICATION"
            ]
        },
        "source_precedence": ["R64_CURRENT_STATE", "R64_ROLE_VIEWS", "CURRENT_CONTROL_PROJECTIONS", "HISTORICAL_IMPLEMENTATION_EVIDENCE", "RETURN_REGISTRY_OBSERVATION"],
        "historical_evidence": source.get("historical_evidence", []),
        "source_divergences": divergences,
        "next_read_only_action": "READ_ONLY_CURRENT_BROKER_RUNTIME_AND_REPO_IDENTITY_READBACK",
        "next_readback_requirements": [
            "BROKER_PROCESS_OR_WATCHER_LIVENESS",
            "C:\\PROJECTS\\control_return_broker_CURRENT_HEAD_TREE",
            "INSTALLED_WATCHER_CONFIGURATION",
            "CURRENT_RETURN_REGISTRY_MUTATION_IMPLEMENTATION_PATH",
            "NO_MUTATION_PERFORMED_DURING_READBACK"
        ],
        "policy": {
            "binder_grants_authority": False,
            "readback_grants_execution_authority": False,
            "auto_execute": False,
            "auto_apply": False,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
            "deploy_permission": "DENY"
        },
        "invariants": {
            "canonical_runtime_outranks_historical_registry_next": True,
            "historical_gate_never_execution_ready": True,
            "no_scope_invention": True,
            "divergence_preserved": True,
            "fresh_liveness_required_before_any_future_execution_design": True
        }
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build read-only Execution Scope Binder V1.")
    p.add_argument("source", type=Path); p.add_argument("command_queue", type=Path); p.add_argument("effect_plane", type=Path); p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        out = build(load(args.source), load(args.command_queue), load(args.effect_plane))
    except ValueError as exc:
        print(json.dumps({"status":"FAIL","errors":str(exc).split(";")}, indent=2)); return 2
    rendered = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output: args.output.write_text(rendered, encoding="utf-8")
    else: print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
