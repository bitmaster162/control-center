from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

OBSERVED_SCHEMA = "hanri.codex01-freshness.observed/v1"
QUALIFICATION_SCHEMA = "hanri.codex01-freshness.qualification/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_BINDING_KINDS = {"GIT_WORKTREE", "RETURN_BROKER_ARTIFACT"}


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
    expected = {
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
        "auto_dispatch": False,
        "auto_promotion": False,
    }
    invariants = observed.get("invariants") or {}
    for key, value in expected.items():
        if invariants.get(key) != value:
            gaps.append(f"effect ceiling drift: invariants.{key}")

    effects = observed.get("effects") or {}
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
    if observed.get("surface") != "codex-01":
        gaps.append("surface must be codex-01")

    precedence = observed.get("source_precedence") or {}
    if precedence.get("continuityos_role") != "PRODUCT_PROOF_NOT_AGENT_SLOT_PROOF":
        gaps.append("ContinuityOS product proof is conflated with CODEX-01 slot proof")
    if precedence.get("dashboard_role") != "PROJECTION_REFERENCE_ONLY_NOT_SLOT_PROOF":
        gaps.append("dashboard source-precedence boundary is missing or widened")
    if precedence.get("historical_work_orders_role") != "HISTORICAL_TASK_DEFINITION_NOT_CURRENT_COMPLETION_RECEIPT":
        gaps.append("historical work-order boundary is missing or widened")

    gaps.extend(_effect_gaps(observed))

    cutoff = _parse_time(observed.get("freshness_cutoff"))
    if cutoff is None:
        gaps.append("freshness cutoff is missing or invalid")

    receipt = observed.get("current_slot_artifact_receipt") or {}
    if receipt.get("present") is not True:
        gaps.append("fresh CODEX-01 slot/artifact receipt is missing")
    if receipt.get("provider_readback_present") is not True:
        gaps.append("provider readback of CODEX-01 slot/artifact receipt is missing")
    if receipt.get("slot_id") != "CODEX-01":
        gaps.append("current slot identity is not exactly CODEX-01")
    if receipt.get("role_binding_present") is not True:
        gaps.append("current CODEX-01 role binding is missing")
    if receipt.get("current_artifact_state_bound") is not True:
        gaps.append("current CODEX-01 artifact/worktree state binding is missing")
    if receipt.get("binding_kind") not in ALLOWED_BINDING_KINDS:
        gaps.append("current CODEX-01 binding kind must be GIT_WORKTREE or RETURN_BROKER_ARTIFACT")
    if receipt.get("clean_baseline_or_strict_return_bound") is not True:
        gaps.append("clean worktree baseline or strict return identity is not bound")
    if receipt.get("no_inferred_execution_authority") is not True:
        gaps.append("current CODEX-01 readback widens or infers execution authority")

    receipt_sha = receipt.get("receipt_sha256")
    if not _is_sha256(receipt_sha):
        gaps.append("current CODEX-01 receipt SHA-256 is missing or invalid")

    observed_at = _parse_time(receipt.get("observed_at"))
    if observed_at is None:
        gaps.append("current CODEX-01 receipt observed_at is missing or invalid")
    elif cutoff is not None and observed_at <= cutoff:
        gaps.append("current CODEX-01 receipt is not fresh for the qualification cutoff")

    if receipt.get("independent_readback_present") is not True:
        gaps.append("independent CODEX-01 receipt readback is missing")
    independent_sha = receipt.get("independent_receipt_sha256")
    if not _is_sha256(independent_sha):
        gaps.append("independent CODEX-01 receipt SHA-256 is missing or invalid")
    elif _is_sha256(receipt_sha) and independent_sha != receipt_sha:
        gaps.append("independent CODEX-01 receipt SHA-256 does not match provider receipt")

    passed = not gaps
    return {
        "schema": QUALIFICATION_SCHEMA,
        "surface": "codex-01",
        "observed_at": observed.get("observed_at"),
        "status": "PASS" if passed else "BLOCKED_REVERIFY",
        "operational_status": "OPERATIONAL" if passed else "BLOCKED_REVERIFY",
        "freshness": "CURRENT" if passed else "STALE",
        "current_claim_allowed": passed,
        "promotion_eligible": passed,
        "proof_gap": gaps,
        "claim_ceiling": {
            "property": "CODEX01_SLOT_AND_CURRENT_ARTIFACT_STATE_BINDING",
            "continuityos_product_current_implies_slot_current": False,
            "dashboard_projection_is_slot_proof": False,
            "historical_work_order_is_completion_proof": False,
            "runtime_activation_claim": False,
            "agent_dispatch_authority_claim": False,
            "execution_authority_claim": False,
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
