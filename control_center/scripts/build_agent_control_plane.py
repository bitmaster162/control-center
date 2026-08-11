from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SOURCE_SCHEMA = "control_center.agent_control_sources.v1"
OUTPUT_SCHEMA = "control_center.agent_control_plane.v1"

R64_POINTER = {
    "drive_file_id": "10HUmbzBVCQDnbFAL6UQ6B2O336ENkEW5",
    "raw_sha256": "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef",
    "generation": "R64",
    "status": "ACTIVE",
    "decision": "ACCEPT_R64_POINTER_PROMOTION",
    "manifest_sha256": "41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d",
}
CURRENT_STATE = {
    "drive_file_id": "10w_2sw2Sl2I5SNe3aY9jqS46u0muvYs_",
    "raw_sha256": "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd",
}
ROLE_VIEWS = {
    "drive_file_id": "19S7z_XwuG-SsKnsxa8vplx4DZxvy49VT",
    "raw_sha256": "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148",
}
RETURN_REGISTRY_ID = "1BXdqWzA74SvkgcygO_ktO_2uolqFshWm"
RETURN_REGISTRY_SCHEMA = "CONTROL_RETURN_REGISTRY_V4"
RETURN_REGISTRY_NAME = "CONTROL_CANTER_RETURN_REGISTRY"

PASS_STATES = {"OUTCOME_PASS", "CLOSEOUT_PASS"}
FAIL_STATES = {"RLS_TEST_FAIL", "ACCEPTANCE_VERIFIED_FAIL_INITDB"}
PENDING_EXEC_STATES = {"PENDING_EXECUTION"}
PENDING_OBSERVATION_STATES = {"PENDING_OBSERVATION_WINDOW"}
GATED_STATES = {"GATED_RESERVED"}
HUMAN_GATE_STATES = {"HUMAN_GATE_READY"}


def _project_hint(slot_id: str, row: dict[str, Any]) -> str:
    explicit = row.get("project")
    if explicit:
        return str(explicit)
    text = " ".join(str(row.get(k, "")) for k in ("work_order", "next")).upper()
    token_map = [
        ("TRADINGOS", "TradingOS"),
        ("CONTINUITY", "ContinuityOS"),
        ("RETURN-PLANE", "Return Plane"),
        ("RETURN_PLANE", "Return Plane"),
        ("VISIONASSIST", "VisionAssist"),
        ("PARASITE-KILLER", "Parasite-Killer"),
        ("HANRI", "HANRI"),
        ("MAWORLD", "MAWorld"),
        ("ARENA", "Arena"),
    ]
    for token, project in token_map:
        if token in text:
            return project
    if slot_id.startswith("ANTIGRAVITY_"):
        return "ANTIGRAVITY"
    return "UNBOUND"


def _operational_class(state: str) -> str:
    if state in PASS_STATES:
        return "RETURN_OR_DECISION_PENDING"
    if state in FAIL_STATES:
        return "FAILURE_REQUIRES_DIAGNOSTIC_GATE"
    if state in HUMAN_GATE_STATES:
        return "HUMAN_GATE_READY"
    if state in PENDING_EXEC_STATES:
        return "PENDING_EXECUTION_BLOCKED"
    if state in PENDING_OBSERVATION_STATES:
        return "PENDING_OBSERVATION_BLOCKED"
    if state in GATED_STATES:
        return "GATED_RESERVED"
    return "OBSERVED"


def _canonical_route(slot_id: str, row: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    if slot_id != "CODEX-07":
        return None
    broker = source.get("canonical_current_state", {}).get("broker_plane", {})
    role = source.get("canonical_role_views", {}).get("roles", {}).get("CODEX-07", {})
    if (
        row.get("work_order") == "CODEX07-R43-RETURN-PLANE-V2"
        and row.get("next") == "ROBERT_MIGRATION_DECISION"
        and broker.get("status") == "INSTALLED_AND_WATCHING"
        and broker.get("watcher_generation") == "R59"
        and str(role.get("state", "")).startswith("R59_")
    ):
        return {
            "current_route": "HISTORICAL_PREDECESSOR_NO_ACTION",
            "source_conflict": "REGISTRY_R43_NEXT_SUPERSEDED_BY_CANONICAL_R59_RUNTIME",
            "canonical_runtime": {
                "broker_status": broker.get("status"),
                "watcher_generation": broker.get("watcher_generation"),
                "role_lane": role.get("lane"),
                "role_state": role.get("state"),
            },
        }
    return None


def _attention_score(slot_id: str, row: dict[str, Any], project: str, route: dict[str, Any] | None) -> tuple[int, str]:
    if route and route.get("current_route") == "HISTORICAL_PREDECESSOR_NO_ACTION":
        return (-1, "STALE_PREDECESSOR_EXCLUDED")
    state = str(row.get("state", "UNKNOWN"))
    nxt = str(row.get("next", ""))
    work_order = str(row.get("work_order", ""))
    if project == "TradingOS" or "TRADINGOS" in work_order.upper():
        return (-1, "DO_NOT_TOUCH_EXCLUDED")
    score = 0
    reason = "OBSERVED"
    if state in FAIL_STATES:
        score, reason = 100, "FAILURE_DIAGNOSTIC"
        if row.get("no_further_agent_work") is True:
            score += 2
    elif state in HUMAN_GATE_STATES:
        score, reason = 90, "HUMAN_GATE_READY"
    elif nxt == "ROBERT_MIGRATION_DECISION":
        score, reason = 88, "ROBERT_MIGRATION_DECISION"
    elif nxt.startswith("ROBERT_"):
        score, reason = 80, "ROBERT_DECISION"
    elif nxt and nxt != "NONE":
        score, reason = 75, "EXPLICIT_NEXT_GATE"
    elif state in PENDING_EXEC_STATES:
        score, reason = 70, "PENDING_EXECUTION"
    elif state in PENDING_OBSERVATION_STATES:
        score, reason = 65, "PENDING_OBSERVATION"
    elif state in GATED_STATES:
        score, reason = 60, "GATED_RESERVED"
    return (score, reason)


def validate_source(source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if source.get("schema") != SOURCE_SCHEMA:
        errors.append("source_schema_mismatch")
    if source.get("snapshot_kind") != "NON_AUTHORITY_PROVIDER_READBACK":
        errors.append("source_must_be_non_authority")

    pointer = source.get("pointer", {})
    for key, expected in R64_POINTER.items():
        if pointer.get(key) != expected:
            errors.append(f"pointer_mismatch:{key}")
    if pointer.get("provider_readback_all_exact") is not True:
        errors.append("pointer_provider_readback_not_all_exact")

    ceiling = pointer.get("effect_ceiling", {})
    required = {
        "NO_FURTHER_AGENT_WORK": True,
        "auto_accept": False,
        "auto_dispatch": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "deploy": "DENY",
        "external_messages": "DENY_WITHOUT_EXACT_SEPARATE_HUMAN_AUTHORIZATION",
        "self_application": False,
    }
    for key, expected in required.items():
        if ceiling.get(key) != expected:
            errors.append(f"effect_ceiling_mismatch:{key}")

    current_state = source.get("canonical_current_state", {})
    for key, expected in CURRENT_STATE.items():
        if current_state.get(key) != expected:
            errors.append(f"current_state_mismatch:{key}")
    broker = current_state.get("broker_plane", {})
    if broker.get("status") != "INSTALLED_AND_WATCHING" or broker.get("watcher_generation") != "R59":
        errors.append("canonical_broker_state_mismatch")
    if not str(broker.get("registry_mutation_rule", "")).startswith("Only the broker mutates CURRENT_RETURN_REGISTRY.json"):
        errors.append("canonical_broker_mutation_rule_mismatch")

    role_views = source.get("canonical_role_views", {})
    for key, expected in ROLE_VIEWS.items():
        if role_views.get(key) != expected:
            errors.append(f"role_views_mismatch:{key}")
    code7 = role_views.get("roles", {}).get("CODEX-07", {})
    if code7.get("lane") != "Return Plane / broker hardening" or not str(code7.get("state", "")).startswith("R59_"):
        errors.append("codex07_role_view_mismatch")

    registry = source.get("return_registry", {})
    if registry.get("drive_file_id") != RETURN_REGISTRY_ID:
        errors.append("registry_drive_id_mismatch")
    if registry.get("schema") != RETURN_REGISTRY_SCHEMA:
        errors.append("registry_schema_mismatch")
    if registry.get("registry_id") != RETURN_REGISTRY_NAME:
        errors.append("registry_id_mismatch")
    raw_sha = str(registry.get("raw_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", raw_sha):
        errors.append("registry_raw_sha_invalid")

    rules = registry.get("rules", {})
    rule_requirements = {
        "rerun_completed_work": False,
        "source_mutation": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }
    for key, expected in rule_requirements.items():
        if rules.get(key) != expected:
            errors.append(f"registry_rule_mismatch:{key}")
    if not isinstance(registry.get("slots"), dict) or not registry.get("slots"):
        errors.append("registry_slots_missing")

    boundaries = source.get("boundaries", {})
    if boundaries.get("registry_is_transport_observation_only") is not True:
        errors.append("registry_transport_boundary_missing")
    if boundaries.get("registry_cannot_accept_or_apply") is not True:
        errors.append("registry_semantic_boundary_missing")
    if boundaries.get("historical_registry_next_cannot_override_canonical_runtime") is not True:
        errors.append("canonical_runtime_precedence_missing")
    if boundaries.get("tradingos_do_not_touch") is not True:
        errors.append("tradingos_boundary_missing")
    if boundaries.get("max_operator_attention") != 3:
        errors.append("operator_attention_limit_mismatch")
    return errors


def build(source: dict[str, Any]) -> dict[str, Any]:
    errors = validate_source(source)
    if errors:
        raise ValueError(";".join(errors))

    pointer = source["pointer"]
    registry = source["return_registry"]
    current_state = source["canonical_current_state"]
    role_views = source["canonical_role_views"]
    slots_out: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    stale_count = 0

    for slot_id in sorted(registry["slots"]):
        row = registry["slots"][slot_id]
        state = str(row.get("state", "UNKNOWN"))
        project = _project_hint(slot_id, row)
        do_not_touch = project == "TradingOS"
        route = _canonical_route(slot_id, row, source)
        slot = {
            "slot": slot_id,
            "project_hint": project,
            "reported_state": state,
            "operational_class": _operational_class(state),
            "work_order": row.get("work_order"),
            "reported_next": row.get("next"),
            "dispatch_authorized": False,
            "dispatch_blocker": "R64_NO_FURTHER_AGENT_WORK",
            "semantic_authority": "NONE_FROM_REGISTRY",
            "apply_authority": "NONE_FROM_REGISTRY",
            "rerun_allowed": False,
            "do_not_touch": do_not_touch,
        }
        if route:
            slot.update(route)
            stale_count += 1
        if row.get("no_further_agent_work") is True:
            slot["slot_no_further_agent_work"] = True
        slots_out.append(slot)

        score, reason = _attention_score(slot_id, row, project, route)
        if score > 0:
            candidates.append({
                "slot": slot_id,
                "project": project,
                "reported_state": state,
                "reason": reason,
                "score": score,
                "requested_next": row.get("next") or "NONE_REPORTED",
                "human_gate": "EXPLICIT_BOUNDED_HUMAN_OR_OWNER_GATE",
                "auto_dispatch": False,
            })

    chosen_by_project: dict[str, dict[str, Any]] = {}
    for item in sorted(candidates, key=lambda x: (-x["score"], x["slot"])):
        project_key = item["project"] if item["project"] != "UNBOUND" else item["slot"]
        if project_key not in chosen_by_project:
            chosen_by_project[project_key] = item
    attention = sorted(chosen_by_project.values(), key=lambda x: (-x["score"], x["slot"]))[:3]
    for idx, item in enumerate(attention, start=1):
        item["rank"] = idx

    blocked_pending = [
        {
            "slot": row["slot"],
            "project": row["project_hint"],
            "reported_state": row["reported_state"],
            "work_order": row["work_order"],
            "dispatch_authorized": False,
            "blocker": "R64_NO_FURTHER_AGENT_WORK",
        }
        for row in slots_out
        if row["reported_state"] in (PENDING_EXEC_STATES | PENDING_OBSERVATION_STATES | GATED_STATES)
    ]

    state_counts: dict[str, int] = {}
    for row in slots_out:
        state_counts[row["reported_state"]] = state_counts.get(row["reported_state"], 0) + 1

    return {
        "schema": OUTPUT_SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": source["observed_at"],
        "authority_anchor": {
            "generation": pointer["generation"],
            "status": pointer["status"],
            "decision": pointer["decision"],
            "pointer_drive_file_id": pointer["drive_file_id"],
            "pointer_sha256": pointer["raw_sha256"],
            "provider_readback": "all_exact",
        },
        "source_provenance": {
            "pointer": {
                "provider": pointer["provider"],
                "drive_file_id": pointer["drive_file_id"],
                "raw_sha256": pointer["raw_sha256"],
                "provider_modified_time": pointer["provider_modified_time"],
            },
            "current_state": {
                "provider": current_state["provider"],
                "drive_file_id": current_state["drive_file_id"],
                "raw_sha256": current_state["raw_sha256"],
                "broker_status": current_state["broker_plane"]["status"],
                "watcher_generation": current_state["broker_plane"]["watcher_generation"],
            },
            "role_views": {
                "provider": role_views["provider"],
                "drive_file_id": role_views["drive_file_id"],
                "raw_sha256": role_views["raw_sha256"],
                "codex07_state": role_views["roles"]["CODEX-07"]["state"],
            },
            "return_registry": {
                "provider": registry["provider"],
                "drive_file_id": registry["drive_file_id"],
                "raw_sha256": registry["raw_sha256"],
                "provider_modified_time": registry["provider_modified_time"],
                "generation_label": registry["generation_label"],
            },
        },
        "global_dispatch": {
            "state": "BLOCKED_BY_R64_NO_FURTHER_AGENT_WORK",
            "auto_dispatch": False,
            "auto_accept": False,
            "human_bounded_override_required": True,
            "note": "Pending work may be observed and routed, but this projection grants no execution authority.",
        },
        "fleet_summary": {
            "slots_total": len(slots_out),
            "reported_state_counts": state_counts,
            "pending_but_blocked": len(blocked_pending),
            "operator_attention_count": len(attention),
            "historical_predecessor_slots": stale_count,
        },
        "slots": slots_out,
        "blocked_dispatch_queue": blocked_pending,
        "operator_attention": attention,
        "invariants": {
            "registry_state_never_semantic_acceptance": True,
            "registry_state_never_apply_authority": True,
            "canonical_runtime_outranks_historical_registry_routing": True,
            "no_auto_dispatch": True,
            "tradingos_do_not_touch": True,
            "max_operator_attention": 3,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic non-authority Agent Control Plane from provider readback.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    try:
        output = build(source)
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": str(exc).split(";")}, indent=2))
        return 2

    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        expected = args.check.read_text(encoding="utf-8")
        ok = rendered == expected
        print(json.dumps({"status": "PASS" if ok else "FAIL", "check": str(args.check), "errors": [] if ok else ["generated_output_mismatch"]}, indent=2))
        return 0 if ok else 2
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
