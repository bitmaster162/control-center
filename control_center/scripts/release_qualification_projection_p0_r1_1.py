from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

QUALIFICATION_SCHEMA = "bitevo.p0_release_qualification_receipt.v1_1"
PROJECTION_SCHEMA = "control_center.shadow_p0_release_qualification_projection.v1_1"

EXPECTED_QUALIFICATION_SHA256 = "426c5cf16e3e366e727f855186fd8265300fbc44f3370f4ed1354e3cd5d54c9c"
EXPECTED_LIVE_SNAPSHOT_SHA256 = "42d9564b3a8f2f2c00e9ae21d4128fbe09be34c44a9a41848ca8da8a8d7075f1"

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


class P0ReleaseQualificationProjectionR11Error(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise P0ReleaseQualificationProjectionR11Error(f"{field}_must_be_sha256")
    return value.lower()


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise P0ReleaseQualificationProjectionR11Error(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise P0ReleaseQualificationProjectionR11Error(code)
    return supplied


def build_p0_release_qualification_projection_r1_1(
    qualification_receipt: Mapping[str, Any],
    *,
    expected_qualification_sha256: str = EXPECTED_QUALIFICATION_SHA256,
    expected_live_snapshot_sha256: str = EXPECTED_LIVE_SNAPSHOT_SHA256,
) -> dict[str, Any]:
    if not isinstance(qualification_receipt, Mapping) or qualification_receipt.get("schema") != QUALIFICATION_SCHEMA:
        raise P0ReleaseQualificationProjectionR11Error("qualification_schema_mismatch")

    digest = _verify_hash(
        qualification_receipt,
        "release_qualification_sha256",
        "qualification_hash_mismatch",
    )
    if digest != _sha(expected_qualification_sha256, "expected_qualification_sha256"):
        raise P0ReleaseQualificationProjectionR11Error("qualification_external_digest_mismatch")
    if qualification_receipt.get("independent_live_snapshot_sha256") != _sha(
        expected_live_snapshot_sha256,
        "expected_live_snapshot_sha256",
    ):
        raise P0ReleaseQualificationProjectionR11Error("live_snapshot_external_digest_mismatch")

    if qualification_receipt.get("status") != "P0_RELEASE_CANDIDATE_R1_1_QUALIFIED_FOR_INDEPENDENT_FINAL_REVIEW_WITH_CONDITIONS":
        raise P0ReleaseQualificationProjectionR11Error("qualification_status_invalid")
    if qualification_receipt.get("decision") != "HOLD" or qualification_receipt.get("action") != "WAIT":
        raise P0ReleaseQualificationProjectionR11Error("qualification_gate_widening_forbidden")

    required_true = (
        "global_invariants_verified",
        "schema_compatibility_verified",
        "manifest_snapshot_hash_bound",
        "independent_live_review_reference_bound",
        "p0_architecture_closed_for_candidate_review",
        "final_independent_review_required",
    )
    for field in required_true:
        if qualification_receipt.get(field) is not True:
            raise P0ReleaseQualificationProjectionR11Error(f"qualification_guard_missing:{field}")

    if qualification_receipt.get("cross_repo_state_live_read_performed_by_qualifier") is not False:
        raise P0ReleaseQualificationProjectionR11Error("qualifier_live_read_overclaim")

    required_false = (
        "production_qualified",
        "release_ready",
        "merge_ready",
        "deploy_ready",
        "runtime_ready",
        "current_truth_promotion_allowed",
        "can_execute",
        "can_trade",
    )
    for field in required_false:
        if qualification_receipt.get(field) is not False:
            raise P0ReleaseQualificationProjectionR11Error(f"qualification_false_guard_breached:{field}")

    if qualification_receipt.get("semantic_acceptance") != "NOT_PERFORMED":
        raise P0ReleaseQualificationProjectionR11Error("semantic_acceptance_breached")
    if qualification_receipt.get("execution_authority") != "NONE":
        raise P0ReleaseQualificationProjectionR11Error("execution_authority_breached")
    if qualification_receipt.get("capital_permission") != "DENY":
        raise P0ReleaseQualificationProjectionR11Error("capital_permission_breached")

    blocked = tuple(qualification_receipt.get("ci_blocked_surfaces") or ())
    green = tuple(qualification_receipt.get("ci_green_surfaces") or ())
    if qualification_receipt.get("ci_blocked_surface_count") != 7 or len(blocked) != 7:
        raise P0ReleaseQualificationProjectionR11Error("blocked_surface_count_mismatch")
    if qualification_receipt.get("ci_green_surface_count") != 2 or len(green) != 2:
        raise P0ReleaseQualificationProjectionR11Error("green_surface_count_mismatch")
    if "control_center_authority" not in blocked:
        raise P0ReleaseQualificationProjectionR11Error("control_center_authority_blocker_missing")
    if set(green) != {"sct_p0", "continuityos_history_p0"}:
        raise P0ReleaseQualificationProjectionR11Error("green_surface_partition_mismatch")

    body = {
        "schema": PROJECTION_SCHEMA,
        "release_qualification_sha256": digest,
        "manifest_sha256": _sha(qualification_receipt.get("manifest_sha256"), "manifest_sha256"),
        "independent_live_snapshot_sha256": _sha(
            qualification_receipt.get("independent_live_snapshot_sha256"),
            "independent_live_snapshot_sha256",
        ),
        "independent_live_snapshot_commit_sha": qualification_receipt.get("independent_live_snapshot_commit_sha"),
        "qualified_input_parent_sha": qualification_receipt.get("qualified_input_parent_sha"),
        "projection_kind": "NON_AUTHORITY_P0_RELEASE_QUALIFICATION_R1_1_PROJECTION",
        "candidate_status": "QUALIFIED_FOR_INDEPENDENT_FINAL_REVIEW_WITH_CONDITIONS",
        "architecture_closed_for_candidate_review": True,
        "final_independent_review_required": True,
        "manifest_snapshot_hash_bound": True,
        "independent_live_review_reference_bound": True,
        "qualifier_live_read_claim": False,
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
        "ci_blocked_surfaces": blocked,
        "ci_green_surfaces": green,
        "known_conditions": tuple(qualification_receipt.get("known_conditions") or ()),
        "effects": dict(REQUIRED_EFFECTS),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
