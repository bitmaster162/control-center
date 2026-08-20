from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from build_decision_effect_ledger import build

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "data" / "work_order_lifecycle.generated.v1.json"
LEDGER = ROOT / "data" / "decision_effect_ledger.generated.v1.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(lifecycle: dict[str, Any], ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        expected = build(lifecycle)
    except ValueError as exc:
        return [f"builder_rejected_lifecycle:{exc}"]
    if ledger != expected:
        errors.append("ledger_not_semantically_equal_to_builder")

    policy = ledger.get("policy", {})
    if any(policy.get(k) is not False for k in ("auto_dispatch", "auto_accept", "auto_apply", "self_approval")):
        errors.append("automatic_or_self_transition_forbidden")
    if policy.get("semantic_acceptance_grants_effect") is not False or policy.get("historical_predecessor_grants_effect") is not False:
        errors.append("accept_or_history_must_not_grant_effect")
    if policy.get("effect_authorization_executes_effect") is not False:
        errors.append("effect_authorization_must_not_execute")
    if policy.get("readback_required_after_any_effect") is not True:
        errors.append("readback_contract_missing")

    decisions = ledger.get("decisions", [])
    by_id = {d.get("decision_id"): d for d in decisions if isinstance(d, dict)}
    if len(by_id) != len(decisions):
        errors.append("decision_id_not_unique")
    for decision in decisions:
        did = decision.get("decision_id")
        if decision.get("effect_authorized") is not False:
            errors.append(f"effect_authorized_without_gate:{did}")
        if decision.get("execution_authorized") is not False:
            errors.append(f"execution_authorized_without_execution_gate:{did}")
        if decision.get("decision_outcome") is not None:
            errors.append(f"projection_must_not_record_new_outcome:{did}")
        if decision.get("apply_status") == "APPLIED":
            errors.append(f"applied_forbidden_in_current_projection:{did}")
        if decision.get("do_not_touch") and (decision.get("owner") != "TRADINGOS_OWNER" or decision.get("decision_state") != "OWNER_REVIEW_ONLY"):
            errors.append(f"do_not_touch_owner_boundary_broken:{did}")
        if decision.get("decision_class") == "DISPATCH_AUTHORITY_EXCEPTION" and (decision.get("human_ripe") is not False or decision.get("decision_state") != "BLOCKED_NOT_RIPE"):
            errors.append(f"blocked_dispatch_surfaced_as_ripe:{did}")
        if decision.get("decision_class") == "HISTORICAL_PREDECESSOR_NO_ACTION":
            if decision.get("human_ripe") is not False or decision.get("decision_state") != "CLOSED_NO_ACTION" or decision.get("owner") != "NONE" or decision.get("allowed_decisions") != []:
                errors.append(f"historical_predecessor_boundary_broken:{did}")

    queues = ledger.get("queues", {})
    if queues.get("human_ripe") != []:
        errors.append("human_ripe_queue_must_be_empty")
    hist = by_id.get("DEC::CODEX07-R43-RETURN-PLANE-V2", {})
    if not (
        hist.get("decision_class") == "HISTORICAL_PREDECESSOR_NO_ACTION"
        and hist.get("decision_state") == "CLOSED_NO_ACTION"
        and hist.get("semantic_status") == "ACCEPTED"
        and hist.get("apply_status") == "NOT_APPLIED"
        and hist.get("gate") == "NONE_STALE_PREDECESSOR_R59_ACTIVE"
        and hist.get("human_ripe") is False
    ):
        errors.append("return_plane_historical_decision_contract_mismatch")

    if any(a.get("human_ripe") for a in ledger.get("compressed_operator_attention", [])):
        errors.append("operator_attention_contains_stale_human_gate")

    summary = ledger.get("summary", {})
    expected_counts = {
        "decision_objects_total": 14,
        "human_ripe_count": 0,
        "control_center_semantic_queue_count": 8,
        "project_owner_queue_count": 2,
        "historical_no_action_count": 1,
        "effects_authorized": 0,
        "executions_authorized": 0,
    }
    for key, value in expected_counts.items():
        if summary.get(key) != value:
            errors.append(f"summary_mismatch:{key}")
    return errors


def main() -> int:
    errors = validate(load(LIFECYCLE), load(LEDGER))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
