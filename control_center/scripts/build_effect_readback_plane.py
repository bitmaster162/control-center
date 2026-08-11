from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "control_center.effect_readback_plane.v1"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(decisions: dict[str, Any], receipts: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    anchor = decisions.get("authority_anchor", {})
    policy = decisions.get("policy", {})
    if decisions.get("schema") != "control_center.decision_effect_ledger.v1":
        errors.append("decision_ledger_schema_mismatch")
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE":
        errors.append("r64_anchor_mismatch")
    if anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA or anchor.get("provider_readback") != "all_exact":
        errors.append("pointer_binding_mismatch")
    if policy.get("auto_apply") is not False or policy.get("self_approval") is not False:
        errors.append("decision_policy_must_fail_closed")
    if receipts.get("schema") != "control_center.effect_receipts_source.v1":
        errors.append("receipt_source_schema_mismatch")
    if receipts.get("source_kind") != "NON_AUTHORITY_RECEIPT_OBSERVATION":
        errors.append("receipt_source_must_be_non_authority")
    if errors:
        raise ValueError(";".join(errors))

    decision_rows = {str(d.get("decision_id")): d for d in decisions.get("decisions", []) if d.get("decision_id")}
    execution_receipts = {str(r.get("receipt_id")): r for r in receipts.get("execution_receipts", []) if r.get("receipt_id")}
    readback_receipts = {str(r.get("receipt_id")): r for r in receipts.get("readback_receipts", []) if r.get("receipt_id")}

    for receipt in execution_receipts.values():
        decision = decision_rows.get(str(receipt.get("decision_id")))
        if not decision:
            errors.append(f"orphan_execution_receipt:{receipt.get('receipt_id')}")
            continue
        if decision.get("effect_authorized") is not True or decision.get("execution_authorized") is not True:
            errors.append(f"unauthorized_execution_receipt:{receipt.get('receipt_id')}")
    for receipt in readback_receipts.values():
        decision = decision_rows.get(str(receipt.get("decision_id")))
        execution_id = str(receipt.get("execution_receipt_id") or "")
        if not decision:
            errors.append(f"orphan_readback_receipt:{receipt.get('receipt_id')}")
        if execution_id not in execution_receipts:
            errors.append(f"readback_without_execution_receipt:{receipt.get('receipt_id')}")
    if errors:
        raise ValueError(";".join(errors))

    candidates: list[dict[str, Any]] = []
    for decision in decisions.get("decisions", []):
        if decision.get("decision_class") != "HUMAN_EFFECT_AUTHORIZATION":
            continue
        decision_id = str(decision["decision_id"])
        ex = next((r for r in execution_receipts.values() if str(r.get("decision_id")) == decision_id), None)
        rb = next((r for r in readback_receipts.values() if str(r.get("decision_id")) == decision_id), None)
        effect_authorized = decision.get("effect_authorized") is True
        execution_authorized = decision.get("execution_authorized") is True
        if not effect_authorized:
            stage = "AWAITING_HUMAN_EFFECT_AUTHORIZATION"
        elif not execution_authorized:
            stage = "EFFECT_AUTHORIZED_EXECUTION_NOT_AUTHORIZED"
        elif not ex:
            stage = "EXECUTION_RECEIPT_REQUIRED"
        elif not rb:
            stage = "READBACK_REQUIRED"
        else:
            stage = "CLOSED_AFTER_READBACK"
        candidates.append({
            "decision_id": decision_id,
            "work_order": decision.get("work_order"),
            "slot": decision.get("slot"),
            "project": decision.get("project"),
            "gate": decision.get("gate"),
            "decision_state": decision.get("decision_state"),
            "decision_outcome": decision.get("decision_outcome"),
            "effect_authorized": effect_authorized,
            "execution_authorized": execution_authorized,
            "apply_status": decision.get("apply_status"),
            "execution_receipt_id": ex.get("receipt_id") if ex else None,
            "readback_receipt_id": rb.get("receipt_id") if rb else None,
            "stage": stage,
        })

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": receipts.get("observed_at") or decisions.get("observed_at"),
        "authority_anchor": anchor,
        "policy": {
            "receipt_never_grants_authority": True,
            "effect_authorization_does_not_execute": True,
            "execution_requires_explicit_authorization": True,
            "execution_requires_receipt": True,
            "readback_required_after_execution": True,
            "closure_requires_readback": True,
            "auto_apply": False,
            "self_application": False,
        },
        "summary": {
            "decision_objects_total": len(decision_rows),
            "effect_candidates_total": len(candidates),
            "effects_authorized": sum(1 for c in candidates if c["effect_authorized"]),
            "executions_authorized": sum(1 for c in candidates if c["execution_authorized"]),
            "execution_receipts": len(execution_receipts),
            "readback_receipts": len(readback_receipts),
            "closed_after_readback": sum(1 for c in candidates if c["stage"] == "CLOSED_AFTER_READBACK"),
        },
        "effect_candidates": candidates,
        "execution_receipts": list(execution_receipts.values()),
        "readback_receipts": list(readback_receipts.values()),
        "invariants": {
            "no_receipt_can_authorize_effect": True,
            "no_execution_without_prior_authority": True,
            "no_closure_without_readback": True,
            "tradingos_not_effect_candidate_without_owner_authority": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fail-closed effect execution/readback plane.")
    parser.add_argument("decision_ledger", type=Path)
    parser.add_argument("receipt_source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        output = build(load(args.decision_ledger), load(args.receipt_source))
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
