from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

QUALIFICATION_SCHEMA = "bitevo.p0_release_qualification_receipt.v1"
PROJECTION_SCHEMA = "control_center.shadow_p0_release_qualification_projection.v1"

REQUIRED_EFFECTS = {
    "current_truth_apply": False,
    "decision_ledger_write": False,
    "command_queue_write": False,
    "human_gate_write": False,
    "credential_registry_write": False,
    "nonce_registry_write": False,
    "lease_registry_write": False,
    "commit_receipt_registry_write": False,
    "backend_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "external_message": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}

class P0ReleaseQualificationProjectionError(ValueError):
    pass

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise P0ReleaseQualificationProjectionError(f"{field}_must_be_sha256")
    return value.lower()

def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise P0ReleaseQualificationProjectionError(code)
    supplied = _sha(record.get(field), field)
    computed = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != computed:
        raise P0ReleaseQualificationProjectionError(code)
    return supplied

def build_p0_release_qualification_projection(
    qualification_receipt: Mapping[str, Any],
    *,
    expected_qualification_sha256: str,
) -> dict[str, Any]:
    if not isinstance(qualification_receipt, Mapping) or qualification_receipt.get("schema") != QUALIFICATION_SCHEMA:
        raise P0ReleaseQualificationProjectionError("qualification_schema_mismatch")
    digest = _verify_hash(
        qualification_receipt,
        "release_qualification_sha256",
        "qualification_hash_mismatch",
    )
    if digest != _sha(expected_qualification_sha256, "expected_qualification_sha256"):
        raise P0ReleaseQualificationProjectionError("qualification_external_digest_mismatch")

    if qualification_receipt.get("status") != "P0_RELEASE_CANDIDATE_QUALIFIED_WITH_CONDITIONS":
        raise P0ReleaseQualificationProjectionError("qualification_status_invalid")
    if qualification_receipt.get("decision") != "HOLD" or qualification_receipt.get("action") != "WAIT":
        raise P0ReleaseQualificationProjectionError("qualification_gate_widening_forbidden")
    for field in (
        "global_invariants_verified",
        "schema_compatibility_verified",
        "cross_repo_snapshot_bound",
        "p0_architecture_closed_for_candidate_review",
    ):
        if qualification_receipt.get(field) is not True:
            raise P0ReleaseQualificationProjectionError(f"qualification_guard_missing:{field}")
    for field in (
        "production_qualified",
        "release_ready",
        "merge_ready",
        "deploy_ready",
        "runtime_ready",
        "current_truth_promotion_allowed",
        "can_execute",
        "can_trade",
    ):
        if qualification_receipt.get(field) is not False:
            raise P0ReleaseQualificationProjectionError(f"qualification_false_guard_breached:{field}")
    if qualification_receipt.get("semantic_acceptance") != "NOT_PERFORMED":
        raise P0ReleaseQualificationProjectionError("qualification_semantic_acceptance_breached")
    if qualification_receipt.get("execution_authority") != "NONE":
        raise P0ReleaseQualificationProjectionError("qualification_execution_authority_breached")
    if qualification_receipt.get("capital_permission") != "DENY":
        raise P0ReleaseQualificationProjectionError("qualification_capital_permission_breached")
    blockers = qualification_receipt.get("ci_blocked_surfaces")
    if not isinstance(blockers, (list, tuple)) or not blockers:
        raise P0ReleaseQualificationProjectionError("qualification_ci_blockers_missing")
    if qualification_receipt.get("ci_blocked_surface_count") != len(blockers):
        raise P0ReleaseQualificationProjectionError("qualification_ci_blocker_count_mismatch")

    body = {
        "schema": PROJECTION_SCHEMA,
        "release_qualification_sha256": digest,
        "manifest_sha256": _sha(qualification_receipt.get("manifest_sha256"), "manifest_sha256"),
        "qualified_input_parent_sha": qualification_receipt["qualified_input_parent_sha"],
        "projection_kind": "NON_AUTHORITY_P0_RELEASE_QUALIFICATION_PROJECTION",
        "candidate_status": "QUALIFIED_WITH_CONDITIONS",
        "architecture_closed_for_candidate_review": True,
        "production_qualified": False,
        "release_ready": False,
        "merge_ready": False,
        "deploy_ready": False,
        "runtime_ready": False,
        "decision": "HOLD",
        "action": "WAIT",
        "current_truth_promotion_allowed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "execution_authority": "NONE",
        "can_execute": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "ci_blocked_surfaces": tuple(blockers),
        "known_conditions": tuple(qualification_receipt.get("known_conditions") or ()),
        "effects": dict(REQUIRED_EFFECTS),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
