from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

AUTHENTICATED_REVEAL_SCHEMA = "bitevo.shadow_authenticated_reveal_closure.v1"
PROJECTION_SCHEMA = "control_center.shadow_authenticated_reveal_projection.v1"

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


class AuthenticatedRevealProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AuthenticatedRevealProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AuthenticatedRevealProjectionError(f"{field}_must_be_sha256")
    return text


def build_authenticated_reveal_projection(closure: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(closure, Mapping) or closure.get("schema") != AUTHENTICATED_REVEAL_SCHEMA:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_schema_mismatch")
    supplied = _sha(closure.get("authenticated_reveal_closure_sha256"), "authenticated_reveal_closure_sha256")
    expected = sha256_obj({k: v for k, v in closure.items() if k != "authenticated_reveal_closure_sha256"})
    if supplied != expected:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_hash_mismatch")
    if closure.get("authentication_status") != "TRUSTED_CUSTODY_ATTESTED_SHADOW_ONLY":
        raise AuthenticatedRevealProjectionError("authenticated_reveal_status_invalid")
    if closure.get("human_identity_scope") != "CUSTODY_PROVIDER_SUBJECT_ASSERTION_ONLY":
        raise AuthenticatedRevealProjectionError("authenticated_reveal_identity_scope_invalid")
    if closure.get("cryptographic_property") != "HMAC_SHA256_VERIFIER_KEY_POSSESSION":
        raise AuthenticatedRevealProjectionError("authenticated_reveal_crypto_property_invalid")
    if closure.get("physical_human_presence_proven") is not False:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_physical_presence_overclaim")
    if closure.get("single_use_registry_candidate_verified") is not True:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_single_use_guard_missing")
    if closure.get("current_truth_promotion_allowed") is not False:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_current_truth_promotion_forbidden")
    if closure.get("history_write_performed") is not False or closure.get("human_gate_write_performed") is not False:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_write_boundary_breached")
    if closure.get("semantic_acceptance") != "NOT_PERFORMED" or closure.get("apply_allowed") is not False:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_acceptance_or_apply_breached")
    if closure.get("execution_authority") != "NONE" or closure.get("can_execute") is not False:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_authority_breached")

    effects = closure.get("effects")
    if not isinstance(effects, Mapping) or set(effects) != REQUIRED_FALSE_EFFECTS:
        raise AuthenticatedRevealProjectionError("authenticated_reveal_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in REQUIRED_FALSE_EFFECTS):
        raise AuthenticatedRevealProjectionError("authenticated_reveal_effect_boundary_breached")
    safety = closure.get("safety")
    if not isinstance(safety, Mapping):
        raise AuthenticatedRevealProjectionError("authenticated_reveal_safety_missing")
    for key, expected_value in REQUIRED_SAFETY.items():
        if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
            raise AuthenticatedRevealProjectionError(f"unsafe_authenticated_reveal:{key}")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_AUTHENTICATED_REVEAL_PROJECTION",
        "source_authenticated_reveal_closure_sha256": supplied,
        "case_id": closure.get("case_id"),
        "case_sha256": _sha(closure.get("case_sha256"), "case_sha256"),
        "reveal_sha256": _sha(closure.get("reveal_sha256"), "reveal_sha256"),
        "approval_verification_sha256": _sha(closure.get("approval_verification_sha256"), "approval_verification_sha256"),
        "challenge_id": _sha(closure.get("challenge_id"), "challenge_id"),
        "human_subject_id": closure.get("human_subject_id"),
        "session_id": closure.get("session_id"),
        "device_id": closure.get("device_id"),
        "custody_provider_id": closure.get("custody_provider_id"),
        "verifier_id": closure.get("verifier_id"),
        "verifier_key_id": closure.get("verifier_key_id"),
        "actual_choice": closure.get("actual_choice"),
        "decided_at": closure.get("decided_at"),
        "custody_authentication": "VERIFIED_SHADOW_ONLY",
        "physical_human_presence": "NOT_PROVEN",
        "approval_scope": "HUMAN_REVEAL_ONLY",
        "single_use_state": "CANDIDATE_VERIFIED_NO_WRITE",
        "current_truth_promotion_allowed": False,
        "apply": False,
        "mutations": {
            "current_truth": False,
            "command_queue": False,
            "decision_ledger": False,
            "return_registry": False,
            "human_gate": False,
            "runtime": False,
            "trading": False,
            "capital": False,
        },
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "semantics": {
            "custody_attestation_is_not_physical_presence": True,
            "approval_is_reveal_only_not_execution_permission": True,
            "single_use_candidate_is_not_registry_write": True,
            "authenticated_reveal_is_not_current_truth": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
