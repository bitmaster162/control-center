from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

R8_CLOSURE_SCHEMA = "bitevo.shadow_writer_fencing_recovery_closure.v1"
PROJECTION_SCHEMA = "control_center.shadow_writer_recovery_projection.v1"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

REQUIRED_FALSE_EFFECTS = {
    "human_gate_write",
    "credential_registry_write",
    "nonce_registry_write",
    "lease_registry_write",
    "commit_receipt_registry_write",
    "backend_write",
    "current_truth_apply",
    "registry_write",
    "ledger_write",
    "return_index_write",
    "runtime_activation",
    "executor_dispatch",
    "signal",
    "order",
    "capital_effect",
}


class WriterRecoveryProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise WriterRecoveryProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise WriterRecoveryProjectionError(f"{field}_must_be_sha256")
    return text


def build_writer_recovery_projection(closure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(closure, Mapping) or closure.get("schema") != R8_CLOSURE_SCHEMA:
        raise WriterRecoveryProjectionError("writer_recovery_closure_schema_mismatch")
    supplied = _sha(closure.get("writer_fencing_recovery_closure_sha256"), "writer_fencing_recovery_closure_sha256")
    expected = sha256_obj({k: v for k, v in closure.items() if k != "writer_fencing_recovery_closure_sha256"})
    if supplied != expected:
        raise WriterRecoveryProjectionError("writer_recovery_closure_hash_mismatch")
    if closure.get("status") != "WRITER_FENCING_RECOVERY_BOUND_SHADOW_ONLY":
        raise WriterRecoveryProjectionError("writer_recovery_status_invalid")
    if closure.get("decision") != "HOLD" or closure.get("action") != "WAIT":
        raise WriterRecoveryProjectionError("writer_recovery_gate_widening_forbidden")
    if closure.get("fencing_model") != "MONOTONIC_FENCING_TOKEN_PLUS_LEASE_DIGEST":
        raise WriterRecoveryProjectionError("writer_recovery_fencing_model_invalid")
    if closure.get("crash_recovery_protocol") != "READBACK_PLUS_RECEIPT_INDEX_DEDUP":
        raise WriterRecoveryProjectionError("writer_recovery_protocol_invalid")
    if closure.get("live_writer_backend_proven") is not False or closure.get("durable_commit_proven") is not False:
        raise WriterRecoveryProjectionError("writer_recovery_durability_overclaim")
    if closure.get("human_gate_write_performed") is not False or closure.get("current_truth_promotion_allowed") is not False:
        raise WriterRecoveryProjectionError("writer_recovery_write_or_truth_breached")
    if closure.get("semantic_acceptance") != "NOT_PERFORMED" or closure.get("apply_allowed") is not False:
        raise WriterRecoveryProjectionError("writer_recovery_acceptance_or_apply_breached")
    if closure.get("execution_authority") != "NONE" or closure.get("can_execute") is not False:
        raise WriterRecoveryProjectionError("writer_recovery_authority_breached")

    effects = closure.get("effects")
    if not isinstance(effects, Mapping) or set(effects) != REQUIRED_FALSE_EFFECTS:
        raise WriterRecoveryProjectionError("writer_recovery_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in REQUIRED_FALSE_EFFECTS):
        raise WriterRecoveryProjectionError("writer_recovery_effect_boundary_breached")
    safety = closure.get("safety")
    if not isinstance(safety, Mapping):
        raise WriterRecoveryProjectionError("writer_recovery_safety_missing")
    for key, expected_value in REQUIRED_SAFETY.items():
        if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
            raise WriterRecoveryProjectionError(f"unsafe_writer_recovery:{key}")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_WRITER_RECOVERY_PROJECTION",
        "source_writer_fencing_recovery_closure_sha256": supplied,
        "case_id": closure.get("case_id"),
        "case_sha256": _sha(closure.get("case_sha256"), "case_sha256"),
        "challenge_id": _sha(closure.get("challenge_id"), "challenge_id"),
        "writer_fencing": "VERIFIED_SHADOW_ONLY",
        "crash_recovery": "VERIFIED_SHADOW_ONLY",
        "durability": "NOT_PROVEN",
        "live_writer_backend": "NOT_PROVEN",
        "recovery_status": closure.get("recovery_status"),
        "recovery_action": closure.get("recovery_action"),
        "decision": "HOLD",
        "action": "WAIT",
        "current_truth_promotion_allowed": False,
        "apply": False,
        "mutations": {
            "current_truth": False,
            "human_gate": False,
            "credential_registry": False,
            "nonce_registry": False,
            "lease_registry": False,
            "commit_receipt_registry": False,
            "runtime": False,
            "trading": False,
            "capital": False,
        },
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "semantics": {
            "fencing_protocol_is_not_live_writer": True,
            "receipt_candidate_is_not_durable_receipt": True,
            "recovery_verification_is_not_current_truth": True,
            "authenticated_reveal_is_not_execution_permission": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
