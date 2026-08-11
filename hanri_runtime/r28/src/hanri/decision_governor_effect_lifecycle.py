from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .decision_governor_pilot import build_decision_governor_pilot

PILOT_VERSION = "decision-governor-pilot-02-effect-lifecycle"
RECEIPT_SCHEMA = "control_canter.p0_closure_receipt.v1"
P0_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "P0-1": (
        "firewall_rule_removed_or_block_added_id",
        "external_connect_test=REFUSED",
        "listen_addresses=localhost",
        "password_rotated_at_utc",
        "operator_identity",
    ),
    "P0-2": (
        "old_token_revoked_at_utc",
        "issuer_confirmation",
        "redeploy_identity_and_time",
        "grep_receipt_zero_credential_literals",
    ),
    "P0-3": (
        "rotation_timestamps_both",
        "old_secret_negative_login_test=DENIED",
        "purged_from_HANDOFF_OPUS_4.8_and_scripts",
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _filled(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        return False
    return True


def inspect_p0_receipts(receipts_dir: Path | None) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    failures: list[str] = []

    for p0_id, required_keys in P0_REQUIREMENTS.items():
        receipt_path = receipts_dir / f"{p0_id}_CLOSURE.json" if receipts_dir is not None else None
        if receipt_path is None or not receipt_path.exists():
            items.append({
                "p0_id": p0_id,
                "status": "OPEN",
                "receipt_present": False,
                "completed_evidence": [],
                "missing_evidence": list(required_keys),
                "off_host_negative_test_attached": False,
                "receipt_path": str(receipt_path) if receipt_path is not None else None,
            })
            continue

        try:
            receipt = _load_json(receipt_path)
        except Exception as exc:
            failures.append(f"{p0_id}:INVALID_JSON:{exc}")
            items.append({
                "p0_id": p0_id,
                "status": "INVALID_RECEIPT",
                "receipt_present": True,
                "completed_evidence": [],
                "missing_evidence": list(required_keys),
                "off_host_negative_test_attached": False,
                "receipt_path": str(receipt_path),
            })
            continue

        evidence = receipt.get("required_evidence") if isinstance(receipt.get("required_evidence"), dict) else {}
        completed = [key for key in required_keys if _filled(evidence.get(key))]
        missing = [key for key in required_keys if key not in completed]
        schema_ok = receipt.get("schema") == RECEIPT_SCHEMA
        id_ok = receipt.get("p0_id") == p0_id
        safety_ok = receipt.get("can_trade") is False and receipt.get("capital_permission") == "DENY"
        off_host_ok = receipt.get("off_host_negative_test_attached") is True
        closure_meta_ok = _filled(receipt.get("closed_by")) and _filled(receipt.get("closed_at_utc"))
        declared_closed = str(receipt.get("status", "")).upper() in {"CLOSED", "VERIFIED_CLOSED", "RECEIPTED_CLOSED"}
        complete = bool(schema_ok and id_ok and safety_ok and off_host_ok and closure_meta_ok and not missing and declared_closed)

        if complete:
            status = "RECEIPTED_CLOSED"
        elif completed or off_host_ok or closure_meta_ok or declared_closed:
            status = "VERIFIED_PARTIAL"
        else:
            status = "OPEN"

        if not schema_ok:
            failures.append(f"{p0_id}:SCHEMA_MISMATCH")
        if not id_ok:
            failures.append(f"{p0_id}:ID_MISMATCH")
        if not safety_ok:
            failures.append(f"{p0_id}:SAFETY_CEILING_MISMATCH")

        items.append({
            "p0_id": p0_id,
            "status": status,
            "receipt_present": True,
            "completed_evidence": completed,
            "missing_evidence": missing,
            "off_host_negative_test_attached": off_host_ok,
            "receipt_path": str(receipt_path),
        })

    all_closed = all(item["status"] == "RECEIPTED_CLOSED" for item in items)
    first_incomplete = next((item["p0_id"] for item in items if item["status"] != "RECEIPTED_CLOSED"), None)
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "all_closed": all_closed,
        "first_incomplete": first_incomplete,
        "items": items,
    }


def build_effect_lifecycle_governor(
    pointer: Mapping[str, Any],
    state: Mapping[str, Any],
    role_views: Mapping[str, Any],
    decision_queue_text: str,
    r28_digest_text: str,
    *,
    receipts_dir: Path | None = None,
    accepted_decisions: set[str] | None = None,
) -> dict[str, Any]:
    accepted_decisions = set(accepted_decisions or set())
    base = build_decision_governor_pilot(pointer, state, role_views, decision_queue_text, r28_digest_text)
    lifecycle = inspect_p0_receipts(receipts_dir)

    cards = [dict(card) for card in base.get("decisions", [])]
    d4 = next((card for card in cards if card.get("decision_id") == "D4_P0_SECURITY_CLOSURE_WINDOW"), None)

    if lifecycle["all_closed"]:
        cards = [card for card in cards if card.get("decision_id") != "D4_P0_SECURITY_CLOSURE_WINDOW"]
    elif d4 is not None:
        first_incomplete = lifecycle["first_incomplete"] or "UNKNOWN"
        p0_item = next(item for item in lifecycle["items"] if item["p0_id"] == first_incomplete)
        d4["causal_interpretation"] = (
            f"D4 security effect lifecycle is active. First incomplete item is {first_incomplete} with status "
            f"{p0_item['status']}. Missing evidence: {', '.join(p0_item['missing_evidence']) or 'none'}. "
            "Do not repeat a remediation that is already evidenced; collect only the missing readback/receipt fields."
        )
        d4["evidence_refs"] = list(d4.get("evidence_refs", [])) + [f"P0_RECEIPTS/{first_incomplete}_CLOSURE.json"]
        d4["minimal_effect_if_approved"] = (
            f"Advance only {first_incomplete} to the next missing evidence field or bounded defensive fix. "
            "No unrelated deployment or authority change."
        )
        if "D4" in accepted_decisions:
            d4["status"] = "EFFECT_READBACK_REQUIRED"
            d4["human_choices"] = ["CONTINUE_READBACK", "HOLD", "REVISE"]
            d4["recommended_choice"] = "CONTINUE_READBACK"

    cards = cards[:3]
    failures = [f for f in base.get("failures", []) if f != "NO_ACTIONABLE_DECISION_CARDS"]
    failures.extend(lifecycle["failures"])
    if len(cards) > 3:
        failures.append("DECISION_CARD_LIMIT_EXCEEDED")

    result = dict(base)
    result.update({
        "schema_version": 2,
        "pilot_version": PILOT_VERSION,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_delta": "DECISION_TO_EFFECT_TO_VERIFIED_CLOSURE_LIFECYCLE",
        "decision_count": len(cards),
        "decisions": cards,
        "p0_effect_lifecycle": lifecycle,
        "accepted_decisions_input": sorted(accepted_decisions),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only HANRI Decision Governor Pilot 02 effect lifecycle")
    parser.add_argument("--current-pointer", type=Path, required=True)
    parser.add_argument("--current-state", type=Path, required=True)
    parser.add_argument("--role-views", type=Path, required=True)
    parser.add_argument("--decision-queue", type=Path, required=True)
    parser.add_argument("--r28-digest", type=Path, required=True)
    parser.add_argument("--p0-receipts-dir", type=Path)
    parser.add_argument("--accepted-decision", action="append", default=[])
    args = parser.parse_args(argv)

    result = build_effect_lifecycle_governor(
        _load_json(args.current_pointer),
        _load_json(args.current_state),
        _load_json(args.role_views),
        args.decision_queue.read_text(encoding="utf-8-sig"),
        args.r28_digest.read_text(encoding="utf-8-sig"),
        receipts_dir=args.p0_receipts_dir,
        accepted_decisions=set(args.accepted_decision),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
