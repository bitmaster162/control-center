from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

OID_RE = re.compile(r"^[0-9a-f]{40}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_NODEID = "tests/test_product_demo.py::test_continuity_demo_recovers_in_fresh_process_and_cleans"
REQUIRED_PROPERTY = "DURABLE_STATE_RECOVERED_ACROSS_FRESH_PROCESS"


def _is_oid(value: Any) -> bool:
    return isinstance(value, str) and bool(OID_RE.fullmatch(value))


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def qualify(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    target = payload.get("target") if isinstance(payload.get("target"), Mapping) else {}
    review = payload.get("review_evidence") if isinstance(payload.get("review_evidence"), Mapping) else {}
    recovery = payload.get("recovery_contract") if isinstance(payload.get("recovery_contract"), Mapping) else {}
    ceiling = payload.get("claim_ceiling") if isinstance(payload.get("claim_ceiling"), Mapping) else {}
    effects = payload.get("effects") if isinstance(payload.get("effects"), Mapping) else {}

    if target.get("repository") != "bitmaster162/continuityos":
        errors.append("target.repository:UNEXPECTED")
    if target.get("branch") != "master":
        errors.append("target.branch:UNEXPECTED")
    if target.get("provider_readback") is not True:
        errors.append("target.provider_readback:REQUIRED")
    if not _is_oid(target.get("head")):
        errors.append("target.head:INVALID")
    if not _is_oid(target.get("tree")):
        errors.append("target.tree:INVALID")
    if target.get("merge_signature_verified") is not True:
        errors.append("target.merge_signature_verified:REQUIRED")
    if target.get("merge_signature_reason") != "valid":
        errors.append("target.merge_signature_reason:NOT_VALID")

    target_tree = target.get("tree")
    source_tree = review.get("source_tree")
    synthetic_tree = review.get("synthetic_merge_tree")
    if target_tree != source_tree:
        errors.append("tree_binding:SOURCE_TREE_MISMATCH")
    if target_tree != synthetic_tree:
        errors.append("tree_binding:SYNTHETIC_MERGE_TREE_MISMATCH")
    if review.get("workflow_status") != "completed" or review.get("workflow_conclusion") != "success":
        errors.append("review_evidence.workflow:NOT_SUCCESS")
    if review.get("synthetic_merge_signature_verified") is not True:
        errors.append("review_evidence.synthetic_merge_signature:REQUIRED")

    for platform in ("ubuntu", "windows"):
        item = review.get(platform) if isinstance(review.get(platform), Mapping) else {}
        if item.get("conclusion") != "success":
            errors.append(f"review_evidence.{platform}.job:NOT_SUCCESS")
        if not _is_sha(item.get("artifact_sha256")):
            errors.append(f"review_evidence.{platform}.artifact_sha256:INVALID")
        if item.get("node_count") != 1004:
            errors.append(f"review_evidence.{platform}.node_count:UNEXPECTED")
        if item.get("nodeids_sha256") != "ab57a67f0d5f7ce5154dd21b1410c81a38fd252bfca92acb1b726a6277ef5541":
            errors.append(f"review_evidence.{platform}.nodeids_sha256:MISMATCH")
        if item.get("wheel_only_status") != "PASS":
            errors.append(f"review_evidence.{platform}.wheel_only:NOT_PASS")
        if item.get("release_hardening") != "10/10 PASS":
            errors.append(f"review_evidence.{platform}.release_hardening:NOT_PASS")

    if recovery.get("test_path") != "tests/test_product_demo.py":
        errors.append("recovery_contract.test_path:UNEXPECTED")
    if not _is_oid(recovery.get("test_blob")):
        errors.append("recovery_contract.test_blob:INVALID")
    if recovery.get("nodeid") != REQUIRED_NODEID or recovery.get("nodeid_collected") is not True:
        errors.append("recovery_contract.nodeid:NOT_BOUND")
    if recovery.get("terminal") != "COS_DEMO_CONTINUITY_PASS":
        errors.append("recovery_contract.terminal:NOT_PASS")
    if recovery.get("reason") != REQUIRED_PROPERTY:
        errors.append("recovery_contract.reason:MISMATCH")
    if recovery.get("session_boundary") != "separate_python_process":
        errors.append("recovery_contract.session_boundary:NOT_FRESH_PROCESS")
    for key in (
        "requires_distinct_process_id",
        "requires_doctor_healthy",
        "requires_all_recovery_checks",
        "requires_temporary_cleanup",
        "requires_user_db_untouched",
    ):
        if recovery.get(key) is not True:
            errors.append(f"recovery_contract.{key}:REQUIRED")
    if recovery.get("network_effect") is not False:
        errors.append("recovery_contract.network_effect:MUST_BE_FALSE")
    if recovery.get("external_model_call") is not False:
        errors.append("recovery_contract.external_model_call:MUST_BE_FALSE")

    if ceiling.get("bounded_property") != REQUIRED_PROPERTY:
        errors.append("claim_ceiling.bounded_property:MISMATCH")
    for key in (
        "production_runtime_deployment_claim",
        "mandatory_broker_enforcement_claim",
        "behavioral_identity_claim",
        "universal_tool_interception_claim",
        "host_daemon_liveness_claim",
    ):
        if ceiling.get(key) is not False:
            errors.append(f"claim_ceiling.{key}:MUST_BE_FALSE")

    expected_effects = {
        "drive_writes": 0,
        "repository_writes_at_runtime": 0,
        "scheduler_changes": 0,
        "external_messages": 0,
        "external_model_calls": 0,
        "trading": False,
        "capital_permission": "DENY",
        "can_trade": False,
        "self_application": False,
    }
    for key, wanted in expected_effects.items():
        if effects.get(key) != wanted:
            errors.append(f"effects.{key}:EXPECTED_{wanted!r}_GOT_{effects.get(key)!r}")

    status = "PASS" if not errors else "BLOCKED"
    return {
        "schema": "hanri.continuityos.freshness-qualification.v1",
        "status": status,
        "errors": errors,
        "target": {
            "repository": target.get("repository"),
            "branch": target.get("branch"),
            "head": target.get("head"),
            "tree": target.get("tree"),
        },
        "bounded_property": REQUIRED_PROPERTY,
        "recovery_evidence": {
            "workflow_run_id": review.get("workflow_run_id"),
            "workflow_run_number": review.get("workflow_run_number"),
            "exact_tree_bound": target_tree == source_tree == synthetic_tree,
            "ubuntu_success": (review.get("ubuntu") or {}).get("conclusion") == "success",
            "windows_success": (review.get("windows") or {}).get("conclusion") == "success",
            "nodeid": REQUIRED_NODEID,
            "nodeid_collected": recovery.get("nodeid_collected") is True,
        },
        "operational_status": "OPERATIONAL" if not errors else "UNKNOWN",
        "freshness": "CURRENT" if not errors else "STALE",
        "current_claim_allowed": not errors,
        "promotion_eligible": not errors,
        "claim_ceiling": dict(ceiling),
        "effects": dict(effects),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify bounded ContinuityOS continuity/recovery freshness")
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.bundle.read_text(encoding="utf-8-sig"))
    result = qualify(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
