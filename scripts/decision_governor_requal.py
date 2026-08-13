from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

REQUIRED_ROOTS = ("current_pointer", "current_state", "role_index", "role_views")
POINTER_BOUND_ROOTS = ("current_state", "role_index", "role_views")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _root_errors(bundle: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    roots = bundle.get("roots") if isinstance(bundle.get("roots"), Mapping) else {}
    for name in REQUIRED_ROOTS:
        item = roots.get(name) if isinstance(roots.get(name), Mapping) else None
        if item is None:
            errors.append(f"{name}:MISSING")
            continue
        if item.get("provider_readback") is not True:
            errors.append(f"{name}:NO_PROVIDER_READBACK")
        if item.get("freshness") != "CURRENT":
            errors.append(f"{name}:NOT_CURRENT")
        sha = str(item.get("sha256") or "")
        if not SHA256_RE.fullmatch(sha):
            errors.append(f"{name}:SHA256_MISSING_OR_INVALID")
        if not str(item.get("evidence_ref") or "").strip():
            errors.append(f"{name}:EVIDENCE_REF_MISSING")
    return errors


def _root_binding_errors(bundle: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    roots = bundle.get("roots") if isinstance(bundle.get("roots"), Mapping) else {}
    bindings = bundle.get("pointer_bindings") if isinstance(bundle.get("pointer_bindings"), Mapping) else {}
    authority = bundle.get("authority") if isinstance(bundle.get("authority"), Mapping) else {}

    if authority.get("generation") != "R64":
        errors.append("authority.generation:MUST_BE_R64")
    if authority.get("pointer_reseal_status") != "ACTIVE_RESEALED_AFTER_EXACT_PROVIDER_READBACK":
        errors.append("authority.pointer_reseal_status:NOT_ACTIVE_RESEALED")

    for name in POINTER_BOUND_ROOTS:
        actual = ""
        item = roots.get(name)
        if isinstance(item, Mapping):
            actual = str(item.get("sha256") or "")
        expected = str(bindings.get(name) or "")
        if not SHA256_RE.fullmatch(expected):
            errors.append(f"pointer_bindings.{name}:MISSING_OR_INVALID")
        elif actual != expected:
            errors.append(f"pointer_bindings.{name}:HASH_MISMATCH")
    return errors


def _safety_errors(bundle: Mapping[str, Any]) -> list[str]:
    effects = bundle.get("effect_ceiling") if isinstance(bundle.get("effect_ceiling"), Mapping) else {}
    expected = {
        "auto_dispatch": False,
        "auto_execution": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
    }
    errors: list[str] = []
    for key, wanted in expected.items():
        if effects.get(key) != wanted:
            errors.append(f"effect_ceiling.{key}:EXPECTED_{wanted!r}_GOT_{effects.get(key)!r}")
    external = str(effects.get("external_messages", "DENY"))
    if external == "ALLOW":
        errors.append("effect_ceiling.external_messages:MUST_REMAIN_HUMAN_GATED")
    return errors


def _decision_index(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    items = bundle.get("decisions") if isinstance(bundle.get("decisions"), list) else []
    result: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if isinstance(item, Mapping) and str(item.get("id") or ""):
            result[str(item["id"])] = item
    return result


def _decision_evidence_errors(bundle: Mapping[str, Any], decisions: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    evidence = bundle.get("decision_evidence") if isinstance(bundle.get("decision_evidence"), Mapping) else {}

    for decision_id in ("D1", "D4"):
        decision = decisions.get(decision_id)
        if decision is None or decision.get("implementation_status") != "CLOSED":
            continue
        item = evidence.get(decision_id) if isinstance(evidence.get(decision_id), Mapping) else None
        if item is None:
            errors.append(f"{decision_id}:CLOSED_WITHOUT_SUPERSESSION_EVIDENCE")
            continue
        if item.get("provider_readback") is not True:
            errors.append(f"{decision_id}:NO_PROVIDER_READBACK")
        if item.get("evidence_state") not in {"RECEIPTED", "HASH_VERIFIED"}:
            errors.append(f"{decision_id}:EVIDENCE_NOT_DURABLE")
        if item.get("outcome") != "CLOSED":
            errors.append(f"{decision_id}:EVIDENCE_OUTCOME_NOT_CLOSED")
        if item.get("supersession") not in {"ADDITIVE_OPERATIONAL_CLOSURE", "ADDITIVE_CURRENT_STATE_DELTA"}:
            errors.append(f"{decision_id}:SUPERSESSION_KIND_INVALID")
        if not str(item.get("evidence_ref") or "").strip():
            errors.append(f"{decision_id}:EVIDENCE_REF_MISSING")

    d5 = decisions.get("D5")
    if d5 is not None and d5.get("implementation_status") == "PENDING" and "WAITING_REPLY" in str(d5.get("detail", "")):
        item = evidence.get("D5") if isinstance(evidence.get("D5"), Mapping) else None
        if item is None:
            errors.append("D5:WAITING_REPLY_WITHOUT_CURRENT_EVIDENCE")
        else:
            if item.get("provider_readback") is not True:
                errors.append("D5:NO_PROVIDER_PROJECTION_READBACK")
            if item.get("evidence_state") not in {"SOURCE_BACKED", "RECEIPTED", "HASH_VERIFIED"}:
                errors.append("D5:EVIDENCE_STATE_INVALID")
            if item.get("outcome") != "WAITING_REPLY":
                errors.append("D5:EVIDENCE_OUTCOME_NOT_WAITING_REPLY")
            if item.get("repeat_outreach_authorized") is not False:
                errors.append("D5:REPEAT_OUTREACH_MUST_BE_FALSE")
            if not str(item.get("evidence_ref") or "").strip():
                errors.append("D5:EVIDENCE_REF_MISSING")
    return errors


def qualify(bundle: Mapping[str, Any]) -> dict[str, Any]:
    root_errors = _root_errors(bundle)
    root_binding_errors = _root_binding_errors(bundle)
    safety_errors = _safety_errors(bundle)
    decisions = _decision_index(bundle)
    decision_evidence_errors = _decision_evidence_errors(bundle, decisions)

    suppressions: list[dict[str, str]] = []
    cards: list[dict[str, Any]] = []

    d1 = decisions.get("D1")
    if d1 is not None:
        if d1.get("implementation_status") == "CLOSED":
            suppressions.append({"id": "D1", "reason": "ALREADY_CLOSED"})
        else:
            cards.append({
                "decision_id": "D1",
                "status": "HUMAN_DECISION_REQUIRED",
                "reason": "D1_NOT_PROVEN_CLOSED",
                "blocked_effects": ["DIRECT_REGISTRY_EDIT", "AUTO_DISPATCH", "TRADING", "CAPITAL_USE"],
            })

    d4 = decisions.get("D4")
    if d4 is not None:
        if d4.get("implementation_status") == "CLOSED":
            suppressions.append({"id": "D4", "reason": "ALREADY_CLOSED"})
        else:
            cards.append({
                "decision_id": "D4",
                "status": "HUMAN_DECISION_REQUIRED",
                "reason": "P0_CLOSURE_NOT_PROVEN",
                "blocked_effects": ["AUTO_EXECUTION", "DEPLOYMENT_EXPANSION", "TRADING", "CAPITAL_USE"],
            })

    d5 = decisions.get("D5")
    if d5 is not None:
        if d5.get("implementation_status") == "PENDING" and "WAITING_REPLY" in str(d5.get("detail", "")):
            suppressions.append({"id": "D5", "reason": "WAITING_REPLY_NO_REPEAT_OUTREACH"})
        elif d5.get("implementation_status") == "CLOSED":
            suppressions.append({"id": "D5", "reason": "ALREADY_CLOSED"})
        else:
            cards.append({
                "decision_id": "D5",
                "status": "HUMAN_DECISION_REQUIRED",
                "reason": "OUTREACH_STATE_UNRESOLVED",
                "blocked_effects": ["SEND_WITHOUT_EXACT_APPROVAL", "AUTO_FOLLOWUP", "BULK_OUTREACH"],
            })

    cards = cards[:3]
    if safety_errors:
        status = "FAIL_SAFETY_CEILING"
    elif root_errors:
        status = "BLOCKED_MISSING_CURRENT_ROOTS"
    elif root_binding_errors:
        status = "BLOCKED_ROOT_BINDING_MISMATCH"
    elif decision_evidence_errors:
        status = "BLOCKED_MISSING_CURRENT_EVIDENCE"
    else:
        status = "PASS"

    promotion_eligible = status == "PASS"
    return {
        "schema": "hanri.decision-governor.requalification.v1",
        "status": status,
        "root_bundle_complete": not root_errors,
        "root_errors": root_errors,
        "root_binding_errors": root_binding_errors,
        "decision_evidence_errors": decision_evidence_errors,
        "safety_errors": safety_errors,
        "decision_count": len(cards),
        "decisions": cards,
        "suppressions": suppressions,
        "promotion_eligible": promotion_eligible,
        "current_claim_allowed": promotion_eligible,
        "effects": {
            "drive_writes": 0,
            "scheduler_changes": 0,
            "external_messages": 0,
            "external_model_api_calls": 0,
            "source_repository_writes_at_runtime": False,
            "auto_dispatch": False,
            "auto_execution": False,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Decision Governor current requalification")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.bundle.read_text(encoding="utf-8-sig"))
    result = qualify(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["status"] == "PASS":
        return 0
    if result["status"].startswith("BLOCKED_"):
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
