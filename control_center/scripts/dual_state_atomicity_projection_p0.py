from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

ATOMICITY_SCHEMA = "control_center.shadow_human_gate_dual_state_atomicity_verification.v1"
PROJECTION_SCHEMA = "control_center.shadow_dual_state_atomicity_projection.v1"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}
NO_EFFECTS = {
    "human_gate_write": False,
    "credential_registry_write": False,
    "nonce_registry_write": False,
    "lease_registry_write": False,
    "commit_receipt_registry_write": False,
    "backend_write": False,
    "current_truth_apply": False,
    "decision_ledger_write": False,
    "command_queue_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}

class DualStateProjectionError(ValueError):
    pass

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise DualStateProjectionError(f"{field}_must_be_sha256")
    return value.lower()

def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise DualStateProjectionError(code)
    return supplied

def build_dual_state_atomicity_projection(atomicity_verification: Mapping[str, Any], *, expected_atomicity_verification_sha256: str) -> dict[str, Any]:
    if not isinstance(atomicity_verification, Mapping) or atomicity_verification.get("schema") != ATOMICITY_SCHEMA:
        raise DualStateProjectionError("atomicity_schema_mismatch")
    digest = _verify_hash(atomicity_verification, "atomicity_verification_sha256", "atomicity_hash_mismatch")
    if digest != _sha(expected_atomicity_verification_sha256, "expected_atomicity_verification_sha256"):
        raise DualStateProjectionError("atomicity_external_digest_mismatch")
    if atomicity_verification.get("protocol_status") != "DUAL_STATE_ATOMICITY_VERIFIED_SHADOW_ONLY":
        raise DualStateProjectionError("atomicity_status_invalid")
    if atomicity_verification.get("split_state_rejected") is not True:
        raise DualStateProjectionError("split_state_guard_missing")
    if atomicity_verification.get("lease_epoch_lineage_verified") is not True or atomicity_verification.get("aba_guard_verified") is not True:
        raise DualStateProjectionError("lease_lineage_guard_missing")
    if atomicity_verification.get("durability_status") != "PROTOCOL_VERIFIED_NO_DURABLE_BACKEND":
        raise DualStateProjectionError("durability_status_invalid")
    if atomicity_verification.get("write_performed") is not False or atomicity_verification.get("durable_commit_proven") is not False:
        raise DualStateProjectionError("durable_write_overclaim")
    if atomicity_verification.get("current_truth_promotion_allowed") is not False or atomicity_verification.get("apply_allowed") is not False:
        raise DualStateProjectionError("truth_or_apply_breached")
    if atomicity_verification.get("execution_authority") != "NONE" or atomicity_verification.get("can_execute") is not False:
        raise DualStateProjectionError("execution_authority_breached")
    if atomicity_verification.get("safety") != REQUIRED_SAFETY or atomicity_verification.get("effects") != NO_EFFECTS:
        raise DualStateProjectionError("safety_or_effect_boundary_mismatch")
    body = {
        "schema": PROJECTION_SCHEMA,
        "atomicity_verification_sha256": digest,
        "authority_root_sha256": atomicity_verification["authority_root_sha256"],
        "case_id": atomicity_verification["case_id"],
        "case_sha256": atomicity_verification["case_sha256"],
        "challenge_id": atomicity_verification["challenge_id"],
        "projection_kind": "NON_AUTHORITY_DUAL_STATE_ATOMICITY_PROJECTION",
        "dual_state_atomicity": "VERIFIED_SHADOW_ONLY",
        "durable_backend": "NOT_PROVEN",
        "decision": "HOLD",
        "action": "WAIT",
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "execution_authority": "NONE",
        "can_trade": False,
        "capital_permission": "DENY",
        "effects": dict(NO_EFFECTS),
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
