from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

OBSERVED_SCHEMA = "hanri.codex05-freshness.observed/v1"
QUALIFICATION_SCHEMA = "hanri.codex05-freshness.qualification/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _parse_time(value: Any) -> datetime | None:
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


def _effect_gaps(observed: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    invariants = observed.get("invariants") or {}
    expected = {
        "do_not_touch": True,
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
        "auto_dispatch": False,
        "auto_promotion": False,
    }
    for key, expected_value in expected.items():
        if invariants.get(key) != expected_value:
            gaps.append(f"effect ceiling drift: invariants.{key}")

    effects = observed.get("effects") or {}
    for key in (
        "writes_to_codex05",
        "writes_to_tradingos",
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
    if observed.get("surface") != "codex-05":
        gaps.append("surface must be codex-05")

    precedence = observed.get("source_precedence") or {}
    if not precedence.get("current_return_registry"):
        gaps.append("current return registry source is not bound")
    if precedence.get("dashboard_role") != "PROJECTION_REFERENCE_ONLY_NOT_SLOT_RUNTIME_PROOF":
        gaps.append("dashboard source-precedence boundary is missing or widened")
    if precedence.get("tradingos_source_visibility_role") != "SOURCE_CUSTODY_REFERENCE_NOT_CODEX05_RUNTIME_PROOF":
        gaps.append("TradingOS source visibility is conflated with CODEX-05 runtime freshness")

    gaps.extend(_effect_gaps(observed))

    cutoff = _parse_time(observed.get("freshness_cutoff"))
    if cutoff is None:
        gaps.append("freshness cutoff is missing or invalid")

    receipt = observed.get("current_slot_runtime_receipt") or {}
    if receipt.get("present") is not True:
        gaps.append("fresh CODEX-05 slot/runtime receipt is missing")
    if receipt.get("provider_readback_present") is not True:
        gaps.append("provider readback of CODEX-05 slot/runtime receipt is missing")
    if receipt.get("slot_id") != "CODEX-05":
        gaps.append("current slot identity is not exactly CODEX-05")
    if receipt.get("role_binding_present") is not True:
        gaps.append("current CODEX-05 role binding is missing")
    if receipt.get("tradingos_target_binding_present") is not True:
        gaps.append("current TradingOS target binding is missing")
    if receipt.get("do_not_touch_preserved") is not True:
        gaps.append("DO_NOT_TOUCH is not preserved")
    if receipt.get("no_inferred_execution_authority") is not True:
        gaps.append("current CODEX-05 readback widens or infers execution authority")

    receipt_sha = receipt.get("receipt_sha256")
    if not _is_sha256(receipt_sha):
        gaps.append("current CODEX-05 receipt SHA-256 is missing or invalid")

    receipt_at = _parse_time(receipt.get("observed_at"))
    if receipt_at is None:
        gaps.append("current CODEX-05 receipt observed_at is missing or invalid")
    elif cutoff is not None and receipt_at <= cutoff:
        gaps.append("current CODEX-05 receipt is not fresh for the qualification cutoff")

    if receipt.get("independent_readback_present") is not True:
        gaps.append("independent CODEX-05 receipt readback is missing")
    independent_sha = receipt.get("independent_receipt_sha256")
    if not _is_sha256(independent_sha):
        gaps.append("independent CODEX-05 receipt SHA-256 is missing or invalid")
    elif _is_sha256(receipt_sha) and independent_sha != receipt_sha:
        gaps.append("independent CODEX-05 receipt SHA-256 does not match provider receipt")

    proof_pass = not gaps
    superseded = receipt.get("exact_supersession_authorized") is True

    return {
        "schema": QUALIFICATION_SCHEMA,
        "surface": "codex-05",
        "observed_at": observed.get("observed_at"),
        "status": "PASS" if proof_pass else "BLOCKED_REVERIFY",
        "operational_status": "OPERATIONAL" if proof_pass and superseded else "DO_NOT_TOUCH",
        "freshness": "CURRENT" if proof_pass else "STALE",
        "current_claim_allowed": proof_pass,
        "promotion_eligible": proof_pass and superseded,
        "do_not_touch_preserved": not superseded,
        "proof_gap": gaps,
        "claim_ceiling": {
            "property": "CODEX05_SLOT_RUNTIME_AND_TRADINGOS_TARGET_BINDING",
            "source_custody_visibility_is_runtime_proof": False,
            "historical_return_is_current_runtime_proof": False,
            "historical_work_order_is_current_completion_proof": False,
            "freshness_pass_authorizes_dispatch": False,
            "freshness_pass_authorizes_tradingos_mutation": False,
            "freshness_pass_authorizes_trading": False,
            "operational_promotion_requires_exact_supersession": True,
        },
        "effects": {
            "writes_to_codex05": 0,
            "writes_to_tradingos": 0,
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
