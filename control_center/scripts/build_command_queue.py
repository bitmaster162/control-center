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


def build(
    agent: dict[str, Any],
    lifecycle: dict[str, Any],
    ledger: dict[str, Any],
    effect: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if agent.get("schema") != "control_center.agent_control_plane.v1":
        errors.append("agent_schema_mismatch")
    if lifecycle.get("schema") != "control_center.work_order_lifecycle.v1":
        errors.append("lifecycle_schema_mismatch")
    if ledger.get("schema") != "control_center.decision_effect_ledger.v1":
        errors.append("ledger_schema_mismatch")
    if effect.get("schema") != "control_center.effect_readback_plane.v1":
        errors.append("effect_schema_mismatch")
    for name, source in (("agent", agent), ("lifecycle", lifecycle), ("ledger", ledger), ("effect", effect)):
        _validate_anchor(name, source, errors)

    agent_global = agent.get("global_dispatch", {})
    life_policy = lifecycle.get("global_policy", {})
    ledger_policy = ledger.get("policy", {})
    effect_policy = effect.get("policy", {})
    if agent_global.get("auto_dispatch") is not False or agent_global.get("auto_accept") is not False:
        errors.append("agent_auto_transition_forbidden")
    if life_policy.get("auto_dispatch") is not False or life_policy.get("auto_accept") is not False or life_policy.get("auto_apply") is not False:
        errors.append("lifecycle_auto_transition_forbidden")
    if ledger_policy.get("auto_dispatch") is not False or ledger_policy.get("auto_accept") is not False or ledger_policy.get("auto_apply") is not False or ledger_policy.get("self_approval") is not False:
        errors.append("ledger_auto_or_self_approval_forbidden")
    if effect_policy.get("auto_apply") is not False or effect_policy.get("self_application") is not False:
        errors.append("effect_auto_apply_forbidden")

    lifecycle_by_work = {str(r.get("work_order")): r for r in lifecycle.get("work_orders", []) if r.get("work_order")}
    decision_rows = ledger.get("decisions", [])
    decision_by_id = {str(d.get("decision_id")): d for d in decision_rows if d.get("decision_id")}
    effect_by_decision = {str(e.get("decision_id")): e for e in effect.get("effect_candidates", []) if e.get("decision_id")}
    attention_by_decision = {
        str(a.get("decision_id")): a
        for a in ledger.get("compressed_operator_attention", [])
        if a.get("decision_id")
    }
    slot_by_name = {str(s.get("slot")): s for s in agent.get("slots", []) if s.get("slot")}

    expected_human = {
        str(did) for did in ledger.get("queues", {}).get("human_ripe", [])
        if did
    }
    if len(expected_human) > MAX_HUMAN_NOW:
        errors.append("human_now_exceeds_max")

    commands: list[dict[str, Any]] = []
    seen_work: set[str] = set()

    for decision in decision_rows:
        decision_id = str(decision.get("decision_id"))
        work_order = str(decision.get("work_order"))
        if not decision_id or not work_order:
            errors.append("decision_identity_missing")
            continue
        if work_order in seen_work:
            errors.append(f"duplicate_work_order::{work_order}")
            continue
        seen_work.add(work_order)
        lifecycle_row = lifecycle_by_work.get(work_order)
        if not lifecycle_row:
            errors.append(f"decision_without_lifecycle::{work_order}")
            continue

        decision_class = str(decision.get("decision_class"))
        decision_state = str(decision.get("decision_state"))
        owner = str(decision.get("owner"))
        human_ripe = bool(decision.get("human_ripe"))
        do_not_touch = bool(decision.get("do_not_touch"))

        if decision_class == "DISPATCH_AUTHORITY_EXCEPTION":
            queue = "BLOCKED_QUEUE"
            command_state = "BLOCKED_NOT_RIPE"
            priority = 100
            requested_action = "KEEP_BLOCKED_UNLESS_EXPLICIT_BOUNDED_OVERRIDE"
        elif human_ripe and decision_state == "OPEN":
            queue = "HUMAN_NOW"
            command_state = "RIPE_HUMAN_GATE"
            priority = 1000
            requested_action = decision.get("gate") or decision.get("authority_required")
        elif owner == "CONTROL_CENTER" and decision_state == "OPEN":
            queue = "CONTROL_CENTER_QUEUE"
            command_state = "ROUTED_FOR_SEMANTIC_REVIEW"
            attention = attention_by_decision.get(decision_id)
            rank = int(attention.get("rank", 99)) if attention else 99
            priority = 900 + max(0, 20 - rank) if attention else 500
            requested_action = "CONTROL_CENTER_SEMANTIC_ADJUDICATION"
        else:
            queue = "PROJECT_OWNER_QUEUE"
            command_state = "ROUTED_TO_PROJECT_OWNER"
            priority = 300
            requested_action = decision.get("authority_required") or "PROJECT_OWNER_REVIEW"

        if queue == "HUMAN_NOW" and decision_id not in expected_human:
            errors.append(f"human_now_not_in_ledger::{decision_id}")
        if decision_id in expected_human and queue != "HUMAN_NOW":
            errors.append(f"ledger_human_ripe_not_in_now::{decision_id}")
        if do_not_touch and queue != "PROJECT_OWNER_QUEUE":
            errors.append(f"do_not_touch_route_violation::{work_order}")

        effect_row = effect_by_decision.get(decision_id)
        if effect_row and queue != "HUMAN_NOW":
            errors.append(f"effect_candidate_not_human_now::{decision_id}")

        slot = str(decision.get("slot") or lifecycle_row.get("slot") or "UNBOUND")
        agent_slot = slot_by_name.get(slot)
        source_reported_state = agent_slot.get("reported_state") if agent_slot else lifecycle_row.get("reported_state")
        attention = attention_by_decision.get(decision_id)

        command = {
            "command_id": f"CMD::{work_order}",
            "decision_id": decision_id,
            "work_order": work_order,
            "slot": slot,
            "project": decision.get("project") or lifecycle_row.get("project") or "UNBOUND",
            "queue": queue,
            "command_state": command_state,
            "priority": priority,
            "routing_priority_only": True,
            "owner": owner,
            "authority_required": decision.get("authority_required"),
            "requested_action": requested_action,
            "allowed_decisions": decision.get("allowed_decisions", []),
            "decision_outcome": decision.get("decision_outcome"),
            "human_ripe": human_ripe,
            "source_lifecycle_stage": lifecycle_row.get("lifecycle_stage"),
            "source_reported_state": source_reported_state,
            "semantic_status": decision.get("semantic_status"),
            "apply_status": decision.get("apply_status"),
            "effect_stage": effect_row.get("stage") if effect_row else "NOT_EFFECT_CANDIDATE",
            "effect_authorized": bool(effect_row.get("effect_authorized")) if effect_row else False,
            "execution_authorized": bool(effect_row.get("execution_authorized")) if effect_row else False,
            "execution_receipt_id": effect_row.get("execution_receipt_id") if effect_row else None,
            "readback_receipt_id": effect_row.get("readback_receipt_id") if effect_row else None,
            "operator_attention_rank": attention.get("rank") if attention else None,
            "operator_attention_reason": attention.get("reason") if attention else None,
            "do_not_touch": do_not_touch,
            "auto_dispatch": False,
            "auto_accept": False,
            "auto_apply": False,
            "auto_execute": False,
        }
        if command["effect_authorized"] or command["execution_authorized"]:
            errors.append(f"current_queue_unexpected_authority::{work_order}")
        if command["execution_receipt_id"] or command["readback_receipt_id"]:
            errors.append(f"current_queue_unexpected_receipt::{work_order}")
        if queue == "BLOCKED_QUEUE" and human_ripe:
            errors.append(f"blocked_item_marked_human_ripe::{work_order}")
        commands.append(command)

    if set(decision_by_id) != {c["decision_id"] for c in commands}:
        errors.append("decision_command_coverage_mismatch")

    if errors:
        raise ValueError(";".join(errors))

    commands.sort(key=lambda c: (-int(c["priority"]), str(c["work_order"])))
    queue_names = ["HUMAN_NOW", "CONTROL_CENTER_QUEUE", "PROJECT_OWNER_QUEUE", "BLOCKED_QUEUE"]
    queues = {
        name: [c["command_id"] for c in commands if c["queue"] == name]
        for name in queue_names
    }
    queue_counts = Counter(c["queue"] for c in commands)

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": effect.get("observed_at") or ledger.get("observed_at"),
        "authority_anchor": _anchor(ledger),
        "source_chain": [
            "AGENT_CONTROL",
            "WORK_ORDER_LIFECYCLE",
            "DECISION_EFFECT_LEDGER",
            "EFFECT_READBACK",
            "COMMAND_QUEUE",
        ],
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
            "human_now": queue_counts.get("HUMAN_NOW", 0),
            "control_center_queue": queue_counts.get("CONTROL_CENTER_QUEUE", 0),
            "project_owner_queue": queue_counts.get("PROJECT_OWNER_QUEUE", 0),
            "blocked_queue": queue_counts.get("BLOCKED_QUEUE", 0),
            "effect_candidates": len(effect_by_decision),
            "effects_authorized": sum(1 for c in commands if c["effect_authorized"]),
            "executions_authorized": sum(1 for c in commands if c["execution_authorized"]),
            "execution_receipts": sum(1 for c in commands if c["execution_receipt_id"]),
            "readback_receipts": sum(1 for c in commands if c["readback_receipt_id"]),
        },
        "queues": queues,
        "commands": commands,
        "invariants": {
            "human_now_equals_open_human_ripe": True,
            "blocked_never_promoted_to_now": True,
            "tradingos_owner_only": True,
            "queue_never_grants_authority": True,
            "queue_never_executes": True,
            "effect_receipts_never_invented": True,
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
