from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

SOURCE_SCHEMA = "bitevo.shadow_human_gate_consume_closure.v1"
PROJECTION_SCHEMA = "control_center.shadow_human_gate_consume_projection.v1"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

SOURCE_EFFECTS = {
    "human_gate_write": False,
    "credential_registry_write": False,
    "nonce_registry_write": False,
    "current_truth_apply": False,
    "registry_write": False,
    "ledger_write": False,
    "return_index_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}


class AtomicConsumeProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AtomicConsumeProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AtomicConsumeProjectionError(f"{field}_must_be_sha256")
    return text


def build_atomic_consume_projection(source: Mapping[str, Any], *, expected_source_sha256: str) -> dict[str, Any]:
    if not isinstance(source, Mapping) or source.get("schema") != SOURCE_SCHEMA:
        raise AtomicConsumeProjectionError("atomic_consume_source_schema_mismatch")
    supplied = _sha(source.get("human_gate_consume_closure_sha256"), "human_gate_consume_closure_sha256")
    expected = sha256_obj({k: v for k, v in source.items() if k != "human_gate_consume_closure_sha256"})
    if supplied != expected:
        raise AtomicConsumeProjectionError("atomic_consume_source_hash_mismatch")
    if supplied != _sha(expected_source_sha256, "expected_source_sha256"):
        raise AtomicConsumeProjectionError("atomic_consume_external_digest_mismatch")
    if source.get("status") != "HUMAN_GATE_CONSUME_BOUND_SHADOW_ONLY":
        raise AtomicConsumeProjectionError("atomic_consume_status_invalid")
    if source.get("toctou_guard_model") != "COMPARE_AND_SWAP_PRECONDITION":
        raise AtomicConsumeProjectionError("atomic_consume_cas_guard_missing")
    if source.get("single_use_protocol") != "BOUND_BUT_NOT_DURABLY_COMMITTED":
        raise AtomicConsumeProjectionError("atomic_consume_single_use_semantics_invalid")
    if source.get("durable_commit_proven") is not False or source.get("human_gate_write_performed") is not False:
        raise AtomicConsumeProjectionError("atomic_consume_durable_commit_overclaim")
    if source.get("current_truth_promotion_allowed") is not False:
        raise AtomicConsumeProjectionError("atomic_consume_truth_promotion_forbidden")
    if source.get("semantic_acceptance") != "NOT_PERFORMED" or source.get("apply_allowed") is not False:
        raise AtomicConsumeProjectionError("atomic_consume_acceptance_or_apply_breached")
    if source.get("execution_authority") != "NONE" or source.get("can_execute") is not False:
        raise AtomicConsumeProjectionError("atomic_consume_authority_breached")
    if source.get("decision") != "HOLD" or source.get("action") != "WAIT":
        raise AtomicConsumeProjectionError("atomic_consume_decision_must_remain_hold_wait")
    effects = source.get("effects")
    if not isinstance(effects, Mapping) or set(effects) != set(SOURCE_EFFECTS) or any(value is not False for value in effects.values()):
        raise AtomicConsumeProjectionError("atomic_consume_effect_boundary_breached")
    safety = source.get("safety")
    if not isinstance(safety, Mapping):
        raise AtomicConsumeProjectionError("atomic_consume_safety_missing")
    for key, expected_value in REQUIRED_SAFETY.items():
        if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
            raise AtomicConsumeProjectionError(f"unsafe_atomic_consume:{key}")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_ATOMIC_CONSUME_PROJECTION",
        "source_human_gate_consume_closure_sha256": supplied,
        "case_id": source.get("case_id"),
        "case_sha256": _sha(source.get("case_sha256"), "case_sha256"),
        "challenge_id": _sha(source.get("challenge_id"), "challenge_id"),
        "prior_human_gate_state_sha256": _sha(source.get("prior_human_gate_state_sha256"), "prior_human_gate_state_sha256"),
        "next_human_gate_state_candidate_sha256": _sha(source.get("next_human_gate_state_candidate_sha256"), "next_human_gate_state_candidate_sha256"),
        "cas_generation_from": source.get("cas_generation_from"),
        "cas_generation_to": source.get("cas_generation_to"),
        "atomic_consume_protocol": "VERIFIED_SHADOW_ONLY",
        "durable_commit": "NOT_PERFORMED",
        "single_use_enforcement": "NOT_DURABLE_IN_P0",
        "current_truth_promotion_allowed": False,
        "apply": False,
        "mutations": {
            "human_gate": False,
            "credential_registry": False,
            "nonce_registry": False,
            "current_truth": False,
            "decision_ledger": False,
            "command_queue": False,
            "runtime": False,
            "trading": False,
            "capital": False,
        },
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "decision": "HOLD",
        "action": "WAIT",
        "semantics": {
            "cas_candidate_is_not_durable_commit": True,
            "single_use_candidate_is_not_global_enforcement": True,
            "authenticated_reveal_is_not_execution_permission": True,
            "verified_protocol_is_not_current_truth": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
