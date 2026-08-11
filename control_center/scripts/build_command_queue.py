from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "control_center.command_queue.v1"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
MAX_HUMAN_NOW = 3


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _anchor(source: dict[str, Any]) -> dict[str, Any]:
    return source.get("authority_anchor", {})


def _validate_anchor(name: str, source: dict[str, Any], errors: list[str]) -> None:
    anchor = _anchor(source)
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE":
        errors.append(f"{name}_r64_anchor_mismatch")
    if anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA or anchor.get("provider_readback") != "all_exact":
        errors.append(f"{name}_pointer_binding_mismatch")


def build(agent: dict[str, Any], lifecycle: dict[str, Any], ledger: dict[str, Any], effect: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    expected_schemas = {
        "agent": (agent, "control_center.agent_control_plane.v1"),
        "lifecycle": (lifecycle, "control_center.work_order_lifecycle.v1"),
        "ledger": (ledger, "control_center.decision_effect_ledger.v1"),
        "effect": (effect, "control_center.effect_readback_plane.v1"),
    }
    for name, (source, schema) in expected_schemas.items():
        if source.get("schema") != schema:
            errors.append(f"{name}_schema_mismatch")
        _validate_anchor(name, source, errors)

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

    commands: list[dict[str, Any]] = []
    seen_work: set[str] = set()
    decision_ids: set[str] = set()

    for decision in ledger.get("decisions", []):
        decision_id = str(decision.get("decision_id") or "")
        work_order = str(decision.get("work_order") or "")
        if not decision_id or not work_order:
            errors.append("decision_identity_missing")
            continue
        decision_ids.add(decision_id)
        if work_order in seen_work:
            errors.append(f"duplicate_work_order::{work_order}")
            continue
        seen_work.add(work_order)
        life = lifecycle_by_work.get(work_order)
        if not life:
            errors.append(f"decision_without_lifecycle::{work_order}")
            continue

        decision_class = str(decision.get("decision_class"))
        decision_state = str(decision.get("decision_state"))
        owner = str(decision.get("owner"))
        human_ripe = bool(decision.get("human_ripe"))
        do_not_touch = bool(decision.get("do_not_touch"))

        if decision_class == "DISPATCH_AUTHORITY_EXCEPTION":
            queue, state, priority = "BLOCKED_QUEUE", "BLOCKED_NOT_RIPE", 100
            requested_action = "KEEP_BLOCKED_UNLESS_EXPLICIT_BOUNDED_OVERRIDE"
        elif human_ripe and decision_state == "OPEN":
            queue, state, priority = "HUMAN_NOW", "RIPE_HUMAN_GATE", 1000
            requested_action = decision.get("gate") or decision.get("authority_required")
        elif owner == "CONTROL_CENTER" and decision_state == "OPEN":
            queue, state = "CONTROL_CENTER_QUEUE", "ROUTED_FOR_SEMANTIC_REVIEW"
            attn = attention.get(decision_id)
            priority = 900 + max(0, 20 - int(attn.get("rank", 99))) if attn else 500
            requested_action = "CONTROL_CENTER_SEMANTIC_ADJUDICATION"
        else:
            queue, state, priority = "PROJECT_OWNER_QUEUE", "ROUTED_TO_PROJECT_OWNER", 300
            requested_action = decision.get("authority_required") or "PROJECT_OWNER_REVIEW"

        if queue == "HUMAN_NOW" and decision_id not in expected_human:
            errors.append(f"human_now_not_in_ledger::{decision_id}")
        if decision_id in expected_human and queue != "HUMAN_NOW":
            errors.append(f"ledger_human_ripe_not_in_now::{decision_id}")
        if queue == "BLOCKED_QUEUE" and human_ripe:
            errors.append(f"blocked_item_marked_human_ripe::{work_order}")
        if do_not_touch and queue != "PROJECT_OWNER_QUEUE":
            errors.append(f"do_not_touch_route_violation::{work_order}")

        effect_row = effects.get(decision_id)
        if effect_row and queue != "HUMAN_NOW":
            errors.append(f"effect_candidate_not_human_now::{decision_id}")
        if effect_row and (effect_row.get("effect_authorized") or effect_row.get("execution_authorized") or effect_row.get("execution_receipt_id") or effect_row.get("readback_receipt_id")):
            errors.append(f"current_effect_state_not_zero::{decision_id}")

        slot = str(decision.get("slot") or life.get("slot") or "UNBOUND")
        slot_state = slot_by_name.get(slot, {}).get("reported_state")
        source_state = life.get("reported_state")
        source_views = list(life.get("source_views", []))
        provenance_divergence = bool(slot_state is not None and slot_state != source_state)
        attn = attention.get(decision_id)

        commands.append({
            "command_id": f"CMD::{work_order}",
            "decision_id": decision_id,
            "work_order": work_order,
            "slot": slot,
            "project": decision.get("project") or life.get("project") or "UNBOUND",
            "queue": queue,
            "state": state,
            "priority": priority,
            "owner": owner,
            "requested_action": requested_action,
            "allowed_decisions": list(decision.get("allowed_decisions", [])),
            "human_ripe": human_ripe,
            "lifecycle_stage": life.get("lifecycle_stage"),
            "source_reported_state": source_state,
            "slot_reported_state_observation": slot_state,
            "source_views": source_views,
            "provenance_divergence": provenance_divergence,
            "effect_stage": effect_row.get("stage") if effect_row else "NOT_EFFECT_CANDIDATE",
            "operator_attention_rank": attn.get("rank") if attn else None,
            "operator_attention_reason": attn.get("reason") if attn else None,
            "do_not_touch": do_not_touch,
            "authority_granted": False,
            "auto_execute": False,
        })

    if decision_ids != {c["decision_id"] for c in commands}:
        errors.append("decision_command_coverage_mismatch")
    if errors:
        raise ValueError(";".join(errors))

    commands.sort(key=lambda c: (-int(c["priority"]), str(c["work_order"])))
    names = ["HUMAN_NOW", "CONTROL_CENTER_QUEUE", "PROJECT_OWNER_QUEUE", "BLOCKED_QUEUE"]
    queues = {name: [c["command_id"] for c in commands if c["queue"] == name] for name in names}
    counts = Counter(c["queue"] for c in commands)

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": effect.get("observed_at") or ledger.get("observed_at"),
        "authority_anchor": _anchor(ledger),
        "source_chain": ["AGENT_CONTROL", "WORK_ORDER_LIFECYCLE", "DECISION_EFFECT_LEDGER", "EFFECT_READBACK", "COMMAND_QUEUE"],
        "policy": {
            "max_human_now": MAX_HUMAN_NOW,
            "routing_priority_only": True,
            "queue_grants_authority": False,
            "auto_dispatch": False,
            "auto_accept": False,
            "auto_apply": False,
            "auto_execute": False,
            "self_approval": False,
            "self_application": False,
        },
        "summary": {
            "commands_total": len(commands),
            "human_now": counts.get("HUMAN_NOW", 0),
            "control_center_queue": counts.get("CONTROL_CENTER_QUEUE", 0),
            "project_owner_queue": counts.get("PROJECT_OWNER_QUEUE", 0),
            "blocked_queue": counts.get("BLOCKED_QUEUE", 0),
            "effect_candidates": len(effects),
            "provenance_divergences": sum(1 for c in commands if c["provenance_divergence"]),
            "effects_authorized": 0,
            "executions_authorized": 0,
        },
        "queues": queues,
        "commands": commands,
        "invariants": {
            "human_now_equals_open_human_ripe": True,
            "blocked_never_promoted_to_now": True,
            "tradingos_owner_only": True,
            "work_order_provenance_preserved": True,
            "queue_never_grants_authority": True,
            "queue_never_executes": True,
            "max_human_now": MAX_HUMAN_NOW,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic non-authority Control Center Command Queue V1.")
    parser.add_argument("agent", type=Path)
    parser.add_argument("lifecycle", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("effect", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = build(load(args.agent), load(args.lifecycle), load(args.ledger), load(args.effect))
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": str(exc).split(";")}, indent=2))
        return 2
    rendered = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
