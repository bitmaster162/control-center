from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

OBSERVED_SCHEMA = "hanri.fable5-freshness.observed/v1"
QUALIFICATION_SCHEMA = "hanri.fable5-freshness.qualification/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _require_effect_ceiling(observed: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    invariants = observed.get("invariants") or {}
    effects = observed.get("effects") or {}

    expected_invariants = {
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
        "auto_dispatch": False,
        "auto_promotion": False,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) != expected:
            gaps.append(f"effect ceiling drift: invariants.{key}")

    for key in (
        "writes",
        "runtime_mutations",
        "provider_mutations",
        "external_messages",
        "trading_effects",
    ):
        if effects.get(key) != 0:
            gaps.append(f"effect ceiling drift: effects.{key}")
    return gaps


def qualify(observed: dict[str, Any]) -> dict[str, Any]:
    gaps: list[str] = []

    if observed.get("schema") != OBSERVED_SCHEMA:
        gaps.append("observed schema mismatch")
    if observed.get("surface") != "fable-5":
        gaps.append("surface must be fable-5")

    precedence = observed.get("source_precedence") or {}
    if not precedence.get("dedicated_fable5_root"):
        gaps.append("dedicated FABLE-5 source root is not bound")
    if precedence.get("dashboard_role") != "PROJECTION_REFERENCE_ONLY_NOT_SLOT_RUNTIME_PROOF":
        gaps.append("dashboard source-precedence boundary is missing or widened")

    gaps.extend(_require_effect_ceiling(observed))

    cutoff = _parse_utc(observed.get("freshness_cutoff"))
    if cutoff is None:
        gaps.append("freshness cutoff is missing or invalid")

    receipt = observed.get("current_slot_runtime_receipt") or {}
    if receipt.get("present") is not True:
        gaps.append("fresh FABLE-5 slot/runtime receipt is missing")
    if receipt.get("provider_readback_present") is not True:
        gaps.append("provider readback of the FABLE-5 slot/runtime receipt is missing")
    if receipt.get("slot_id") != "FABLE-5":
        gaps.append("current slot identity is not exactly FABLE-5")
    if receipt.get("host_bridge_status_present") is not True:
        gaps.append("fresh host-bridge status is missing")
    if receipt.get("current_role_runtime_readback_present") is not True:
        gaps.append("current role/runtime readback is missing")
    if receipt.get("no_inferred_execution_authority") is not True:
        gaps.append("current readback widens or infers execution authority")

    receipt_sha = receipt.get("receipt_sha256")
    if not _is_sha256(receipt_sha):
        gaps.append("current slot/runtime receipt SHA-256 is missing or invalid")

    receipt_at = _parse_utc(receipt.get("observed_at"))
    if receipt_at is None:
        gaps.append("current slot/runtime receipt observed_at is missing or invalid")
    elif cutoff is not None and receipt_at <= cutoff:
        gaps.append("current slot/runtime receipt is not fresh for the qualification cutoff")

    if receipt.get("independent_readback_present") is not True:
        gaps.append("independent FABLE-5 slot/runtime readback is missing")

    independent_sha = receipt.get("independent_receipt_sha256")
    if not _is_sha256(independent_sha):
        gaps.append("independent slot/runtime receipt SHA-256 is missing or invalid")
    elif _is_sha256(receipt_sha) and independent_sha != receipt_sha:
        gaps.append("independent slot/runtime receipt SHA-256 does not match provider receipt")

    passed = not gaps
    status = "PASS" if passed else "BLOCKED_REVERIFY"

    return {
        "schema": QUALIFICATION_SCHEMA,
        "surface": "fable-5",
        "observed_at": observed.get("observed_at"),
        "status": status,
        "operational_status": "OPERATIONAL" if passed else "BLOCKED_REVERIFY",
        "freshness": "CURRENT" if passed else "STALE",
        "current_claim_allowed": passed,
        "promotion_eligible": passed,
        "proof_gap": gaps,
        "claim_ceiling": {
            "property": "FABLE5_SLOT_IDENTITY_AND_BOUNDED_HOST_BRIDGE_STATUS",
            "dashboard_projection_is_runtime_proof": False,
            "historical_audit_is_current_runtime_proof": False,
            "model_quality_claim": False,
            "provider_global_availability_claim": False,
            "execution_authority_claim": False,
            "runtime_deployment_claim": False,
            "external_message_authority_claim": False,
        },
        "effects": {
            "writes": 0,
            "runtime_mutations": 0,
            "provider_mutations": 0,
            "external_messages": 0,
            "trading_effects": 0,
        },
        "invariants": {
            "can_trade": False,
            "capital_permission": "DENY",
            "self_application": False,
            "auto_dispatch": False,
            "auto_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    observed = json.loads(Path(args.observed).read_text(encoding="utf-8"))
    result = qualify(observed)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
