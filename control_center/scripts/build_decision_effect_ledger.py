from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "control_center.decision_effect_ledger.v1"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_decision(row: dict[str, Any]) -> dict[str, Any]:
    work_order = str(row["work_order"])
    stage = str(row["lifecycle_stage"])
    do_not_touch = bool(row.get("do_not_touch"))

    base = {
        "decision_id": f"DEC::{work_order}",
        "work_order": work_order,
        "slot": row.get("slot"),
        "project": row.get("project"),
        "source_lifecycle_stage": stage,
        "semantic_status": row.get("semantic_status"),
        "apply_status": row.get("apply_status"),
        "decision_outcome": None,
        "effect_authorized": False,
        "execution_authorized": False,
        "auto_transition": False,
        "readback_contract": "REQUIRED_AFTER_ANY_EFFECT",
        "readback_status": row.get("readback_status", "NOT_DUE_NO_EFFECT"),
        "do_not_touch": do_not_touch,
    }

    if stage == "EFFECT_GATE_WAIT":
        base.update(
            decision_class="HUMAN_EFFECT_AUTHORIZATION",
            decision_state="OPEN",
            owner="ROBERT",
            authority_required="HUMAN_SOVEREIGN_EXPLICIT_BOUNDED_EFFECT_GATE",
            allowed_decisions=["AUTHORIZE_APPLY", "HOLD", "REJECT_EFFECT"],
            human_attention=True,
            attention_reason="SEMANTIC_ACCEPTED_EFFECT_NOT_AUTHORIZED",
            gate=row.get("effect_gate") or "EXPLICIT_HUMAN_EFFECT_GATE",
            prerequisite="SEMANTIC_STATUS_ACCEPTED",
            next_transition="EXPLICIT_EFFECT_AUTHORIZATION_OR_NO_EFFECT",
        )
    elif stage == "DISPATCH_BLOCKED":
        base.update(
            decision_class="DISPATCH_AUTHORITY_EXCEPTION",
            decision_state="BLOCKED_NOT_RIPE",
            owner="ROBERT",
            authority_required="HUMAN_SOVEREIGN_EXPLICIT_BOUNDED_DISPATCH_OVERRIDE",
            allowed_decisions=["KEEP_BLOCKED", "AUTHORIZE_BOUNDED_DISPATCH"],
            human_attention=False,
            attention_reason="SUPPRESSED_BY_R64_GLOBAL_NO_FURTHER_AGENT_WORK",
            gate="R64_NO_FURTHER_AGENT_WORK",
            prerequisite="EXPLICIT_BOUNDED_OVERRIDE_REQUIRED",
            next_transition="REMAIN_BLOCKED_UNLESS_SEPARATELY_AUTHORIZED",
        )
    else:
        owner = "TRADINGOS_OWNER" if do_not_touch else "CONTROL_CENTER"
        authority = "TRADINGOS_OWNER_DECISION" if do_not_touch else "CONTROL_CENTER_SEMANTIC_ADJUDICATION"
        state = "OWNER_REVIEW_ONLY" if do_not_touch else "OPEN"
        base.update(
            decision_class="SEMANTIC_ADJUDICATION",
            decision_state=state,
            owner=owner,
            authority_required=authority,
            allowed_decisions=["ACCEPT", "REVISE", "HOLD", "REJECT"],
            human_attention=False,
            attention_reason="SEMANTIC_REVIEW_BEFORE_ANY_EFFECT",
            gate=row.get("effect_gate"),
            prerequisite="EVIDENCE_REVIEW",
            next_transition="SEMANTIC_DECISION_ONLY_NO_IMPLICIT_EFFECT",
        )
    return base


def queue_ref(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": decision["decision_id"],
        "work_order": decision["work_order"],
        "slot": decision.get("slot"),
        "project": decision.get("project"),
        "decision_class": decision["decision_class"],
        "decision_state": decision["decision_state"],
        "owner": decision["owner"],
        "authority_required": decision["authority_required"],
        "gate": decision.get("gate"),
        "allowed_decisions": decision["allowed_decisions"],
    }


def build(lifecycle: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    anchor = lifecycle.get("authority_anchor", {})
    policy = lifecycle.get("global_policy", {})
    if lifecycle.get("schema") != "control_center.work_order_lifecycle.v1":
        errors.append("lifecycle_schema_mismatch")
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE":
        errors.append("r64_anchor_mismatch")
    if anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA or anchor.get("provider_readback") != "all_exact":
        errors.append("pointer_binding_mismatch")
    if policy.get("auto_dispatch") is not False or policy.get("auto_accept") is not False or policy.get("auto_apply") is not False:
        errors.append("lifecycle_auto_transition_forbidden")
    if errors:
        raise ValueError(";".join(errors))

    decisions = [make_decision(row) for row in lifecycle.get("work_orders", [])]
    by_work = {row["work_order"]: row for row in decisions}

    compressed_attention: list[dict[str, Any]] = []
    for item in lifecycle.get("operator_attention", []):
        work_order = item.get("work_order")
        decision = by_work.get(str(work_order)) if work_order else None
        if not decision:
            compressed_attention.append({
                "rank": item.get("rank"),
                "work_order": work_order,
                "route": "CONTROL_CENTER_BINDING_REVIEW",
                "human_ripe": False,
                "reason": "NO_UNAMBIGUOUS_DECISION_BINDING",
            })
            continue
        if decision["human_attention"] and decision["decision_state"] == "OPEN":
            route = "ROBERT_HUMAN_GATE"
            human_ripe = True
        elif decision["owner"] == "CONTROL_CENTER":
            route = "CONTROL_CENTER_SEMANTIC_QUEUE"
            human_ripe = False
        else:
            route = "PROJECT_OWNER_QUEUE"
            human_ripe = False
        compressed_attention.append({
            "rank": item.get("rank"),
            "work_order": work_order,
            "slot": item.get("slot"),
            "project": item.get("project"),
            "route": route,
            "human_ripe": human_ripe,
            "decision_id": decision["decision_id"],
            "decision_class": decision["decision_class"],
            "decision_state": decision["decision_state"],
            "reason": item.get("reason"),
        })

    class_counts = Counter(d["decision_class"] for d in decisions)
    owner_counts = Counter(d["owner"] for d in decisions)
    human_queue = [d for d in decisions if d["human_attention"] and d["decision_state"] == "OPEN"]
    control_queue = [d for d in decisions if d["owner"] == "CONTROL_CENTER" and d["decision_state"] == "OPEN"]
    owner_queue = [d for d in decisions if d["owner"] not in {"CONTROL_CENTER", "ROBERT"}]

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": lifecycle.get("observed_at"),
        "authority_anchor": anchor,
        "policy": {
            "auto_dispatch": False,
            "auto_accept": False,
            "auto_apply": False,
            "self_approval": False,
            "semantic_acceptance_grants_effect": False,
            "effect_authorization_executes_effect": False,
            "readback_required_after_any_effect": True,
        },
        "summary": {
            "decision_objects_total": len(decisions),
            "decision_class_counts": dict(sorted(class_counts.items())),
            "owner_counts": dict(sorted(owner_counts.items())),
            "human_ripe_count": len(human_queue),
            "control_center_semantic_queue_count": len(control_queue),
            "project_owner_queue_count": len(owner_queue),
            "effects_authorized": 0,
            "executions_authorized": 0,
        },
        "human_ripe_queue": [queue_ref(d) for d in human_queue],
        "control_center_semantic_queue": [queue_ref(d) for d in control_queue],
        "project_owner_queue": [queue_ref(d) for d in owner_queue],
        "compressed_operator_attention": compressed_attention,
        "decisions": decisions,
        "invariants": {
            "accept_never_implies_apply": True,
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
