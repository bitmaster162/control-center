from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

ASYMMETRIC_REVEAL_CLOSURE_SCHEMA = "bitevo.shadow_asymmetric_reveal_closure.v1"
PROJECTION_SCHEMA = "control_center.shadow_asymmetric_reveal_projection.v1"

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
    "registry_write",
    "ledger_write",
    "return_index_write",
    "current_truth_apply",
    "runtime_activation",
    "executor_dispatch",
    "signal",
    "order",
    "capital_effect",
}


class AsymmetricRevealProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AsymmetricRevealProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AsymmetricRevealProjectionError(f"{field}_must_be_sha256")
    return text


def build_asymmetric_reveal_projection(closure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(closure, Mapping) or closure.get("schema") != ASYMMETRIC_REVEAL_CLOSURE_SCHEMA:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_schema_mismatch")
    supplied = _sha(closure.get("asymmetric_reveal_closure_sha256"), "asymmetric_reveal_closure_sha256")
    expected = sha256_obj({k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"})
    if supplied != expected:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_hash_mismatch")
    if closure.get("authentication_status") != "ASYMMETRIC_CUSTODY_VERIFIED_SHADOW_ONLY":
        raise AsymmetricRevealProjectionError("asymmetric_reveal_status_invalid")
    if closure.get("human_identity_scope") != "CREDENTIAL_SUBJECT_ASSERTION_ONLY":
        raise AsymmetricRevealProjectionError("asymmetric_reveal_identity_scope_invalid")
    if closure.get("cryptographic_property") != "EXTERNAL_ASYMMETRIC_SIGNATURE_VERIFIER_ASSERTION":
        raise AsymmetricRevealProjectionError("asymmetric_reveal_crypto_property_invalid")
    if closure.get("local_signature_math_verified") is not False:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_local_crypto_overclaim")
    if closure.get("physical_human_presence_proven") is not False:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_physical_presence_overclaim")
    if closure.get("single_use_nonce_candidate_verified") is not True:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_nonce_guard_missing")
    if closure.get("credential_epoch_verified") is not True:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_credential_epoch_guard_missing")
    if closure.get("current_truth_promotion_allowed") is not False:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_current_truth_promotion_forbidden")
    if closure.get("history_write_performed") is not False or closure.get("human_gate_write_performed") is not False:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_write_boundary_breached")
    if closure.get("semantic_acceptance") != "NOT_PERFORMED" or closure.get("apply_allowed") is not False:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_acceptance_or_apply_breached")
    if closure.get("execution_authority") != "NONE" or closure.get("can_execute") is not False:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_authority_breached")

    effects = closure.get("effects")
    if not isinstance(effects, Mapping) or set(effects) != REQUIRED_FALSE_EFFECTS:
        raise AsymmetricRevealProjectionError("asymmetric_reveal_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in REQUIRED_FALSE_EFFECTS):
        raise AsymmetricRevealProjectionError("asymmetric_reveal_effect_boundary_breached")
    safety = closure.get("safety")
    if not isinstance(safety, Mapping):
        raise AsymmetricRevealProjectionError("asymmetric_reveal_safety_missing")
    for key, expected_value in REQUIRED_SAFETY.items():
        if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
            raise AsymmetricRevealProjectionError(f"unsafe_asymmetric_reveal:{key}")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_ASYMMETRIC_REVEAL_PROJECTION",
        "source_asymmetric_reveal_closure_sha256": supplied,
        "case_id": closure.get("case_id"),
        "case_sha256": _sha(closure.get("case_sha256"), "case_sha256"),
        "reveal_sha256": _sha(closure.get("reveal_sha256"), "reveal_sha256"),
        "asymmetric_approval_verification_sha256": _sha(
            closure.get("asymmetric_approval_verification_sha256"),
            "asymmetric_approval_verification_sha256",
        ),
        "challenge_id": _sha(closure.get("challenge_id"), "challenge_id"),
        "human_subject_id": closure.get("human_subject_id"),
        "session_id": closure.get("session_id"),
        "device_id": closure.get("device_id"),
        "custody_provider_id": closure.get("custody_provider_id"),
        "credential_id_sha256": _sha(closure.get("credential_id_sha256"), "credential_id_sha256"),
        "public_key_sha256": _sha(closure.get("public_key_sha256"), "public_key_sha256"),
        "algorithm": closure.get("algorithm"),
        "key_epoch": closure.get("key_epoch"),
        "actual_choice": closure.get("actual_choice"),
        "decided_at": closure.get("decided_at"),
        "asymmetric_custody": "VERIFIED_BY_EXTERNAL_ASYMMETRIC_VERIFIER_SHADOW_ONLY",
        "local_signature_math": "NOT_VERIFIED_HERE",
        "physical_human_presence": "NOT_PROVEN",
        "approval_scope": "HUMAN_REVEAL_ONLY",
        "nonce_state": "CUMULATIVE_REGISTRY_CANDIDATE_VERIFIED_NO_WRITE",
        "credential_state": "ACTIVE_EPOCH_CANDIDATE_VERIFIED_NO_WRITE",
        "current_truth_promotion_allowed": False,
        "apply": False,
        "mutations": {
            "current_truth": False,
            "command_queue": False,
            "decision_ledger": False,
            "return_registry": False,
            "human_gate": False,
            "credential_registry": False,
            "nonce_registry": False,
            "runtime": False,
            "trading": False,
            "capital": False,
        },
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "semantics": {
            "asymmetric_verifier_assertion_is_not_local_signature_verification": True,
            "authenticator_user_verification_is_not_legal_identity": True,
            "nonce_candidate_is_not_durable_single_use_enforcement": True,
            "credential_epoch_candidate_is_not_registry_write": True,
            "authenticated_reveal_is_not_current_truth": True,
            "authenticated_reveal_is_not_execution_permission": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
