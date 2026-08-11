from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "control_center.command_queue.v1"
EXPECTED_POINTER_SHA = "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3"
MAX_HUMAN_NOW = 3


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def anchor(source: dict[str, Any]) -> dict[str, Any]:
    return source.get("authority_anchor", {})


def validate_source(name: str, source: dict[str, Any], schema: str, errors: list[str]) -> None:
    if source.get("schema") != schema:
        errors.append(f"{name}_schema_mismatch")
    a = anchor(source)
    if a.get("generation") != "R64" or a.get("status") != "ACTIVE":
        errors.append(f"{name}_r64_anchor_mismatch")
    if a.get("pointer_sha256") != EXPECTED_POINTER_SHA or a.get("provider_readback") != "all_exact":
        errors.append(f"{name}_pointer_binding_mismatch")


def build(agent: dict[str, Any], lifecycle: dict[str, Any], ledger: dict[str, Any], effect: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    validate_source("agent", agent, "control_center.agent_control_plane.v1", errors)
    validate_source("lifecycle", lifecycle, "control_center.work_order_lifecycle.v1", errors)
    validate_source("ledger", ledger, "control_center.decision_effect_ledger.v1", errors)
    validate_source("effect", effect, "control_center.effect_readback_plane.v1", errors)
    if agent.get("global_dispatch", {}).get("auto_dispatch") is not False or agent.get("global_dispatch", {}).get("auto_accept") is not False:
        errors.append("agent_auto_transition_forbidden")
    lp = lifecycle.get("global_policy", {})
    if lp.get("auto_dispatch") is not False or lp.get("auto_accept") is not False or lp.get("auto_apply") is not False:
        errors.append("lifecycle_auto_transition_forbidden")
    dp = ledger.get("policy", {})
    if dp.get("auto_dispatch") is not False or dp.get("auto_accept") is not False or dp.get("auto_apply") is not False or dp.get("self_approval") is not False:
        errors.append("ledger_auto_or_self_approval_forbidden")
    ep = effect.get("policy", {})
    if ep.get("auto_apply") is not False or ep.get("self_application") is not False:
        errors.append("effect_auto_apply_forbidden")

    lifecycle_by_work = {str(r["work_order"]): r for r in lifecycle.get("work_orders", []) if r.get("work_order")}
    slot_by_name = {str(s["slot"]): s for s in agent.get("slots", []) if s.get("slot")}
    effects = {str(e["decision_id"]): e for e in effect.get("effect_candidates", []) if e.get("decision_id")}
    attention = {str(a["decision_id"]): a for a in ledger.get("compressed_operator_attention", []) if a.get("decision_id")}
    expected_human = {str(x) for x in ledger.get("queues", {}).get("human_ripe", []) if x}
    if len(expected_human) > MAX_HUMAN_NOW:
        errors.append("human_now_exceeds_max")

    routed: list[dict[str, Any]] = []
    divergences: list[dict[str, Any]] = []
    human_now: list[dict[str, Any]] = []
    seen_work: set[str] = set()
    decision_ids: set[str] = set()

    for decision in ledger.get("decisions", []):
        did = str(decision.get("decision_id") or "")
        work = str(decision.get("work_order") or "")
        if not did or not work:
            errors.append("decision_identity_missing")
            continue
        decision_ids.add(did)
        if work in seen_work:
            errors.append(f"duplicate_work_order::{work}")
            continue
        seen_work.add(work)
        life = lifecycle_by_work.get(work)
        if not life:
            errors.append(f"decision_without_lifecycle::{work}")
            continue

        dclass = str(decision.get("decision_class"))
        dstate = str(decision.get("decision_state"))
        owner = str(decision.get("owner"))
        human = bool(decision.get("human_ripe"))
        dnt = bool(decision.get("do_not_touch"))
        attn = attention.get(did)

        if dclass == "HISTORICAL_PREDECESSOR_NO_ACTION":
            queue, priority = "HISTORICAL_QUEUE", 0
        elif dclass == "DISPATCH_AUTHORITY_EXCEPTION":
            queue, priority = "BLOCKED_QUEUE", 100
        elif human and dstate == "OPEN":
            queue, priority = "HUMAN_NOW", 1000
        elif owner == "CONTROL_CENTER" and dstate == "OPEN":
            queue = "CONTROL_CENTER_QUEUE"
            priority = 900 + max(0, 20 - int(attn.get("rank", 99))) if attn else 500
        else:
            queue, priority = "PROJECT_OWNER_QUEUE", 300

        if dclass == "HISTORICAL_PREDECESSOR_NO_ACTION":
            if human or owner != "NONE" or dstate != "CLOSED_NO_ACTION" or effects.get(did):
                errors.append(f"historical_route_violation::{did}")
        if queue == "HUMAN_NOW" and did not in expected_human:
            errors.append(f"human_now_not_in_ledger::{did}")
        if did in expected_human and queue != "HUMAN_NOW":
            errors.append(f"ledger_human_ripe_not_in_now::{did}")
        if queue == "BLOCKED_QUEUE" and human:
            errors.append(f"blocked_item_marked_human_ripe::{work}")
        if dnt and queue != "PROJECT_OWNER_QUEUE":
            errors.append(f"do_not_touch_route_violation::{work}")

        effect_row = effects.get(did)
        if effect_row and queue != "HUMAN_NOW":
            errors.append(f"effect_candidate_not_human_now::{did}")
        if effect_row and (effect_row.get("effect_authorized") or effect_row.get("execution_authorized") or effect_row.get("execution_receipt_id") or effect_row.get("readback_receipt_id")):
            errors.append(f"current_effect_state_not_zero::{did}")

        command_id = f"CMD::{work}"
        routed.append({"command_id": command_id, "decision_id": did, "work_order": work, "queue": queue, "priority": priority})
        if queue == "HUMAN_NOW":
            human_now.append({
                "command_id": command_id, "decision_id": did, "work_order": work, "project": decision.get("project"),
                "requested_action": decision.get("gate") or decision.get("authority_required"),
                "allowed_decisions": list(decision.get("allowed_decisions", [])),
                "effect_stage": effect_row.get("stage") if effect_row else "NOT_EFFECT_CANDIDATE",
                "authority_granted": False, "auto_execute": False,
            })

        slot = str(decision.get("slot") or life.get("slot") or "UNBOUND")
        slot_state = slot_by_name.get(slot, {}).get("reported_state")
        source_state = life.get("reported_state")
        if slot_state is not None and slot_state != source_state:
            divergences.append({
                "work_order": work, "slot": slot, "lifecycle_reported_state": source_state,
                "slot_reported_state_observation": slot_state, "action": "PRESERVE_BOTH_NO_SILENT_RECONCILIATION",
            })

    if decision_ids != {r["decision_id"] for r in routed}:
        errors.append("decision_command_coverage_mismatch")
    if errors:
        raise ValueError(";".join(errors))

    routed.sort(key=lambda r: (-int(r["priority"]), str(r["work_order"])))
    names = ["HUMAN_NOW", "CONTROL_CENTER_QUEUE", "PROJECT_OWNER_QUEUE", "BLOCKED_QUEUE", "HISTORICAL_QUEUE"]
    queues = {name: [r["command_id"] for r in routed if r["queue"] == name] for name in names}
    counts = Counter(r["queue"] for r in routed)
    route_by_decision = {r["decision_id"]: r for r in routed}
    attention_routing = []
    for item in ledger.get("compressed_operator_attention", []):
        did = str(item.get("decision_id") or "")
        route = route_by_decision.get(did)
        attention_routing.append({
            "rank": item.get("rank"), "decision_id": did or None,
            "command_id": route.get("command_id") if route else None,
            "queue": route.get("queue") if route else "UNBOUND",
            "work_order": item.get("work_order"), "reason": item.get("reason"),
        })

    return {
        "schema": SCHEMA, "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": effect.get("observed_at") or ledger.get("observed_at"),
        "authority_anchor": anchor(ledger),
        "source_chain": ["AGENT_CONTROL", "WORK_ORDER_LIFECYCLE", "DECISION_EFFECT_LEDGER", "EFFECT_READBACK", "COMMAND_QUEUE"],
        "policy": {"max_human_now": MAX_HUMAN_NOW, "routing_priority_only": True, "queue_grants_authority": False,
                   "auto_dispatch": False, "auto_accept": False, "auto_apply": False, "auto_execute": False,
                   "self_approval": False, "self_application": False},
        "summary": {
            "commands_total": len(routed), "human_now": counts.get("HUMAN_NOW", 0),
            "control_center_queue": counts.get("CONTROL_CENTER_QUEUE", 0),
            "project_owner_queue": counts.get("PROJECT_OWNER_QUEUE", 0),
            "blocked_queue": counts.get("BLOCKED_QUEUE", 0), "historical_queue": counts.get("HISTORICAL_QUEUE", 0),
            "effect_candidates": len(effects), "provenance_divergences": len(divergences),
            "effects_authorized": 0, "executions_authorized": 0,
        },
        "ordered_command_ids": [r["command_id"] for r in routed],
        "queues": queues, "human_now": human_now, "attention_routing": attention_routing,
        "owner_only_do_not_touch": [r["command_id"] for r in routed if r["queue"] == "PROJECT_OWNER_QUEUE" and lifecycle_by_work[r["work_order"]].get("do_not_touch")],
        "provenance_divergences": sorted(divergences, key=lambda d: d["work_order"]),
        "invariants": {
            "human_now_equals_open_human_ripe": True, "blocked_never_promoted_to_now": True,
            "historical_never_promoted_to_now": True, "tradingos_owner_only": True,
            "work_order_provenance_preserved": True, "queue_never_grants_authority": True,
            "queue_never_executes": True, "max_human_now": MAX_HUMAN_NOW,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build deterministic non-authority Control Center Command Queue V1.")
    p.add_argument("agent", type=Path); p.add_argument("lifecycle", type=Path); p.add_argument("ledger", type=Path); p.add_argument("effect", type=Path); p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        output = build(load(args.agent), load(args.lifecycle), load(args.ledger), load(args.effect))
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": str(exc).split(";")}, indent=2)); return 2
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output: args.output.write_text(rendered, encoding="utf-8")
    else: print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
