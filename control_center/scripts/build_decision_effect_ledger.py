from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from current_authority_anchor import append_anchor_errors

SCHEMA = "control_center.decision_effect_ledger.v1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_decision(row: dict[str, Any]) -> dict[str, Any]:
    work_order = str(row["work_order"])
    stage = str(row["lifecycle_stage"])
    do_not_touch = bool(row.get("do_not_touch"))

    if stage == "HISTORICAL_EVIDENCE_ONLY":
        decision_class = "HISTORICAL_PREDECESSOR_NO_ACTION"
        decision_state = "CLOSED_NO_ACTION"
        owner = "NONE"
        authority = "NONE_HISTORICAL_EVIDENCE"
        allowed: list[str] = []
        human_ripe = False
        gate = row.get("effect_gate") or "NONE_STALE_PREDECESSOR"
    elif stage == "EFFECT_GATE_WAIT":
        decision_class = "HUMAN_EFFECT_AUTHORIZATION"
        decision_state = "OPEN"
        owner = "ROBERT"
        authority = "HUMAN_SOVEREIGN_EXPLICIT_BOUNDED_EFFECT_GATE"
        allowed = ["AUTHORIZE_APPLY", "HOLD", "REJECT_EFFECT"]
        human_ripe = True
        gate = row.get("effect_gate") or "EXPLICIT_HUMAN_EFFECT_GATE"
    elif stage == "DISPATCH_BLOCKED":
        decision_class = "DISPATCH_AUTHORITY_EXCEPTION"
        decision_state = "BLOCKED_NOT_RIPE"
        owner = "ROBERT"
        authority = "HUMAN_SOVEREIGN_EXPLICIT_BOUNDED_DISPATCH_OVERRIDE"
        allowed = ["KEEP_BLOCKED", "AUTHORIZE_BOUNDED_DISPATCH"]
        human_ripe = False
        gate = "R64_NO_FURTHER_AGENT_WORK"
    else:
        decision_class = "SEMANTIC_ADJUDICATION"
        owner = "TRADINGOS_OWNER" if do_not_touch else "CONTROL_CENTER"
        decision_state = "OWNER_REVIEW_ONLY" if do_not_touch else "OPEN"
        authority = "TRADINGOS_OWNER_DECISION" if do_not_touch else "CONTROL_CENTER_SEMANTIC_ADJUDICATION"
        allowed = ["ACCEPT", "REVISE", "HOLD", "REJECT"]
        human_ripe = False
        gate = row.get("effect_gate")

    return {
        "decision_id": f"DEC::{work_order}",
        "work_order": work_order,
        "slot": row.get("slot"),
        "project": row.get("project"),
        "source_lifecycle_stage": stage,
        "decision_class": decision_class,
        "decision_state": decision_state,
        "owner": owner,
        "authority_required": authority,
        "allowed_decisions": allowed,
        "semantic_status": row.get("semantic_status"),
        "apply_status": row.get("apply_status"),
        "decision_outcome": None,
        "gate": gate,
        "human_ripe": human_ripe,
        "effect_authorized": False,
        "execution_authorized": False,
        "readback_status": row.get("readback_status", "NOT_DUE_NO_EFFECT"),
        "do_not_touch": do_not_touch,
        "historical_predecessor": bool(row.get("historical_predecessor")),
    }


def build(lifecycle: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    anchor = lifecycle.get("authority_anchor", {})
    policy = lifecycle.get("global_policy", {})
    if lifecycle.get("schema") != "control_center.work_order_lifecycle.v1":
        errors.append("lifecycle_schema_mismatch")
    append_anchor_errors("work_lifecycle", anchor, errors)
    if policy.get("auto_dispatch") is not False or policy.get("auto_accept") is not False or policy.get("auto_apply") is not False:
        errors.append("lifecycle_auto_transition_forbidden")
    if errors:
        raise ValueError(";".join(errors))

    decisions = [make_decision(row) for row in lifecycle.get("work_orders", [])]
    by_work = {row["work_order"]: row for row in decisions}

    attention: list[dict[str, Any]] = []
    for item in lifecycle.get("operator_attention", []):
        work_order = item.get("work_order")
        decision = by_work.get(str(work_order)) if work_order else None
        if not decision:
            attention.append({"rank": item.get("rank"), "work_order": work_order, "route": "CONTROL_CENTER_BINDING_REVIEW", "human_ripe": False})
            continue
        route = (
            "ROBERT_HUMAN_GATE" if decision["human_ripe"]
            else "CONTROL_CENTER_SEMANTIC_QUEUE" if decision["owner"] == "CONTROL_CENTER"
            else "PROJECT_OWNER_QUEUE" if decision["owner"] not in {"NONE", "ROBERT"}
            else "HISTORICAL_NO_ACTION"
        )
        attention.append({
            "rank": item.get("rank"), "work_order": work_order, "slot": item.get("slot"), "project": item.get("project"),
            "route": route, "human_ripe": decision["human_ripe"], "decision_id": decision["decision_id"], "reason": item.get("reason"),
        })

    class_counts = Counter(d["decision_class"] for d in decisions)
    owner_counts = Counter(d["owner"] for d in decisions)
    human_ids = [d["decision_id"] for d in decisions if d["human_ripe"] and d["decision_state"] == "OPEN"]
    control_ids = [d["decision_id"] for d in decisions if d["owner"] == "CONTROL_CENTER" and d["decision_state"] == "OPEN"]
    owner_ids = [d["decision_id"] for d in decisions if d["owner"] not in {"CONTROL_CENTER", "ROBERT", "NONE"}]
    historical_ids = [d["decision_id"] for d in decisions if d["decision_class"] == "HISTORICAL_PREDECESSOR_NO_ACTION"]

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": lifecycle.get("observed_at"),
        "authority_anchor": anchor,
        "policy": {
            "auto_dispatch": False, "auto_accept": False, "auto_apply": False, "self_approval": False,
            "semantic_acceptance_grants_effect": False, "effect_authorization_executes_effect": False,
            "historical_predecessor_grants_effect": False, "readback_required_after_any_effect": True,
        },
        "summary": {
            "decision_objects_total": len(decisions),
            "decision_class_counts": dict(sorted(class_counts.items())),
            "owner_counts": dict(sorted(owner_counts.items())),
            "human_ripe_count": len(human_ids),
            "control_center_semantic_queue_count": len(control_ids),
            "project_owner_queue_count": len(owner_ids),
            "historical_no_action_count": len(historical_ids),
            "effects_authorized": 0, "executions_authorized": 0,
        },
        "queues": {
            "human_ripe": human_ids,
            "control_center_semantic": control_ids,
            "project_owner": owner_ids,
            "historical_no_action": historical_ids,
        },
        "compressed_operator_attention": attention,
        "decisions": decisions,
        "invariants": {
            "accept_never_implies_apply": True,
            "historical_predecessor_never_human_gate": True,
            "effect_gate_never_executes_effect": True,
            "dispatch_override_never_auto_runs": True,
            "tradingos_routes_to_owner_only": True,
            "robert_only_receives_ripe_human_gates": True,
            "readback_required_after_effect": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-authority decision/effect gate ledger from Work Order Lifecycle.")
    parser.add_argument("lifecycle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = build(load(args.lifecycle))
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
