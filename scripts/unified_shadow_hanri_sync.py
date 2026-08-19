from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

TRANSACTION_SCHEMA = "bitevo.unified_shadow_transaction.v2"
ARCHIVEOS_QUAL_SCHEMA = "hanri.archiveos-freshness.qualification/v1"
HANRI_RECEIPT_SCHEMA = "hanri.shadow-evidence-governor.receipt/v1"

EXPECTED_HANRI_BRANCH = "hanri/r37-product-pilot-accepted"
EXPECTED_HANRI_HEAD = "ef5c504179de8ae8c16bd70c168b14b79bd2f466"
EXPECTED_ARCHIVE_TOOLING_HANDOFF_SHA256 = "af9f06b74fa380a1b3e9c6bf69b871d17228abd70ae6c13f77ca8984836e0856"
EXPECTED_NODE_COUNT = 63

R64_AUTHORITY = {
    "generation": "R64",
    "current_pointer_sha256": "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3",
    "current_state_sha256": "701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68",
    "role_index_sha256": "e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567",
    "role_views_sha256": "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148",
}

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

REQUIRED_FALSE_EFFECTS = (
    "executor_enabled",
    "current_truth_apply",
    "continuity_write",
    "runtime_registration",
    "external_model_call",
    "exchange_call",
    "signal",
    "order",
    "credential_mutation",
    "merge",
    "deploy",
)


class HanriShadowError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hex(value: Any, length: int, field: str) -> str:
    if not isinstance(value, str):
        raise HanriShadowError(f"{field}_must_be_hex{length}")
    text = value.lower()
    if len(text) != length or any(ch not in "0123456789abcdef" for ch in text):
        raise HanriShadowError(f"{field}_must_be_hex{length}")
    return text


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise HanriShadowError(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise HanriShadowError(f"unsafe_{field}:{key}")


def _validate_transaction(transaction: Mapping[str, Any]) -> str:
    if not isinstance(transaction, Mapping) or transaction.get("schema") != TRANSACTION_SCHEMA:
        raise HanriShadowError("transaction_schema_mismatch")
    if transaction.get("registered_node_count") != EXPECTED_NODE_COUNT:
        raise HanriShadowError("transaction_registry_count_mismatch")
    _verify_safety(transaction, "transaction")
    effects = transaction.get("effect_boundary")
    if not isinstance(effects, Mapping):
        raise HanriShadowError("transaction_effect_boundary_missing")
    for key in REQUIRED_FALSE_EFFECTS:
        if effects.get(key) is not False:
            raise HanriShadowError(f"transaction_effect_boundary_breached:{key}")
    tx_sha = _hex(transaction.get("transaction_sha256"), 64, "transaction_sha256")
    expected = sha256_obj({k: v for k, v in transaction.items() if k != "transaction_sha256"})
    if tx_sha != expected:
        raise HanriShadowError("transaction_hash_mismatch")
    if transaction.get("control_gate") not in {"PASS_SHADOW", "HOLD"}:
        raise HanriShadowError("transaction_control_gate_invalid")
    if transaction.get("control_gate") == "HOLD" and transaction.get("control_plane_action") != "WAIT":
        raise HanriShadowError("transaction_hold_must_force_wait")
    return tx_sha


def _validate_archiveos(qualification: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(qualification, Mapping) or qualification.get("schema") != ARCHIVEOS_QUAL_SCHEMA:
        raise HanriShadowError("archiveos_qualification_schema_mismatch")
    if qualification.get("surface") != "archive-os":
        raise HanriShadowError("archiveos_surface_mismatch")
    status = qualification.get("status")
    freshness = qualification.get("freshness")
    current_claim_allowed = qualification.get("current_claim_allowed")
    promotion_eligible = qualification.get("promotion_eligible")
    if status not in {"PASS", "BLOCKED_REVERIFY"}:
        raise HanriShadowError("archiveos_status_invalid")
    if status == "PASS":
        if freshness != "CURRENT" or current_claim_allowed is not True or promotion_eligible is not True:
            raise HanriShadowError("archiveos_pass_inconsistent")
    else:
        if freshness != "STALE" or current_claim_allowed is not False or promotion_eligible is not False:
            raise HanriShadowError("archiveos_blocked_inconsistent")

    effects = qualification.get("effects") or {}
    for key in ("writes", "runtime_mutations", "provider_mutations", "external_messages", "trading_effects"):
        if effects.get(key) != 0:
            raise HanriShadowError(f"archiveos_effect_ceiling_breached:{key}")
    invariants = qualification.get("invariants") or {}
    expected_invariants = {
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
        "auto_dispatch": False,
        "auto_promotion": False,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) != expected:
            raise HanriShadowError(f"archiveos_invariant_drift:{key}")

    ceiling = qualification.get("claim_ceiling") or {}
    if ceiling.get("drive_mirror_is_authority") is not False:
        raise HanriShadowError("archiveos_drive_authority_overclaim")
    if ceiling.get("archive_tooling_is_archive_engine") is not False:
        raise HanriShadowError("archive_tooling_role_overclaim")
    if ceiling.get("runtime_deployment_claim") is not False:
        raise HanriShadowError("archiveos_runtime_overclaim")

    return {
        "status": status,
        "freshness": freshness,
        "current_claim_allowed": current_claim_allowed,
        "promotion_eligible": promotion_eligible,
        "proof_gap": list(qualification.get("proof_gap") or []),
    }


def build_hanri_shadow_evidence_receipt(
    transaction: Mapping[str, Any],
    archiveos_qualification: Mapping[str, Any],
    *,
    hanri_branch: str,
    hanri_head: str,
    generated_at: str,
) -> dict[str, Any]:
    """Bind HANRI + ArchiveOS evidence state to one P0 transaction without promotion or effects."""
    tx_sha = _validate_transaction(transaction)
    archive = _validate_archiveos(archiveos_qualification)

    if hanri_branch != EXPECTED_HANRI_BRANCH:
        raise HanriShadowError("hanri_branch_mismatch")
    head = _hex(hanri_head, 40, "hanri_head")
    if head != EXPECTED_HANRI_HEAD:
        raise HanriShadowError("hanri_head_mismatch")

    upstream_hold = transaction.get("control_gate") == "HOLD"
    archive_hold = archive["status"] != "PASS"
    governor_hold = upstream_hold or archive_hold
    governor_gate = "HOLD" if governor_hold else "PASS_SHADOW"
    governor_action = "WAIT" if governor_hold else str(transaction.get("control_plane_action"))

    hold_reasons: list[str] = []
    if upstream_hold:
        hold_reasons.append("UPSTREAM_CONTROL_GATE_HOLD")
    if archive_hold:
        hold_reasons.append("ARCHIVEOS_BLOCKED_REVERIFY")

    body = {
        "schema": HANRI_RECEIPT_SCHEMA,
        "generated_at": str(generated_at),
        "source_transaction_sha256": tx_sha,
        "case_id": transaction.get("case_id"),
        "human_sovereign": True,
        "authority_reference": dict(R64_AUTHORITY),
        "hanri_source": {
            "repo": "bitmaster162/control-center",
            "branch": EXPECTED_HANRI_BRANCH,
            "head_sha": head,
            "role": "BOUNDED_RUNTIME_ATTENTION_GOVERNOR_PROJECTION",
            "authority_root": False,
            "can_promote_self": False,
        },
        "archiveos": {
            **archive,
            "role": "NON_AUTHORITATIVE_EVIDENCE_VAULT",
            "canonical_root": "C:\\PROJECTS\\archiveos_api",
            "drive_role": "MIRROR_EVIDENCE_ONLY",
        },
        "archive_tooling": {
            "role": "ARTIFACT_COMPILER_NOT_ARCHIVE_ENGINE",
            "historical_handoff_sha256": EXPECTED_ARCHIVE_TOOLING_HANDOFF_SHA256,
            "authoritative_archive_engine": False,
            "semantic_acceptance_authority": False,
        },
        "knowledge_memory": {
            "claim_admission": "NOT_PERFORMED",
            "durable_memory_write": False,
            "project_canon_write": False,
            "current_truth_write": False,
            "reasoning_derivative_is_evidence": False,
            "memory_is_permission": False,
            "archive_bytes_are_current_truth": False,
        },
        "governor": {
            "gate": governor_gate,
            "action": governor_action,
            "hold_reasons": hold_reasons,
            "attention_required": governor_hold,
            "promotion_eligible": False,
            "auto_promotion": False,
        },
        "source_precedence": [
            "HUMAN_SOVEREIGN",
            "R64_CONTROL_CENTER_AUTHORITY",
            "ACCEPTED_SEMANTIC_ADJUDICATIONS",
            "HANRI_BOUNDED_REPOSITORY_EVIDENCE",
            "LIVE_RUNTIME_RECEIPTS_FOR_RUNTIME_CLAIMS",
            "DASHBOARD_PROJECTION_ONLY",
        ],
        "effects": {
            "github_write": False,
            "drive_write": False,
            "archiveos_write": False,
            "knowledge_write": False,
            "memory_write": False,
            "current_truth_apply": False,
            "runtime_write": False,
            "scheduler_write": False,
            "external_message": False,
            "signal": False,
            "order": False,
            "capital_effect": False,
        },
        "semantics": {
            "hanri_is_not_second_authority_root": True,
            "repository_capability_is_not_live_runtime": True,
            "drive_projection_is_not_current_truth": True,
            "archive_tooling_is_not_archiveos_core": True,
            "archive_freshness_is_required_for_current_archive_claim": True,
            "knowledge_admission_is_separate_from_archive_custody": True,
            "durable_memory_is_separate_from_current_truth": True,
            "freshness_never_supersedes_do_not_touch": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["hanri_receipt_sha256"] = sha256_obj(body)
    return body
