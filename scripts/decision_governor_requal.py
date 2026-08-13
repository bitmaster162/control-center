from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

REQUIRED_ROOTS = ("current_pointer", "current_state", "role_index", "role_views")
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


def qualify(bundle: Mapping[str, Any]) -> dict[str, Any]:
    root_errors = _root_errors(bundle)
    safety_errors = _safety_errors(bundle)
    decisions = _decision_index(bundle)

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
    else:
        status = "PASS"

    promotion_eligible = status == "PASS"
    return {
        "schema": "hanri.decision-governor.requalification.v1",
        "status": status,
        "root_bundle_complete": not root_errors,
        "root_errors": root_errors,
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
    if result["status"] == "BLOCKED_MISSING_CURRENT_ROOTS":
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
