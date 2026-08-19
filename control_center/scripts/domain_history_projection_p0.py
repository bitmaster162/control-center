from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

DOMAIN_HISTORY_SCHEMA = "bitevo.shadow_domain_history_closure.v1"
PROJECTION_SCHEMA = "control_center.shadow_domain_history_projection.v1"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

REQUIRED_FALSE_EFFECTS = (
    "registry_write",
    "ledger_write",
    "return_index_write",
    "current_truth_apply",
    "runtime_activation",
    "executor_dispatch",
    "signal",
    "order",
    "capital_effect",
)


class DomainHistoryProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise DomainHistoryProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise DomainHistoryProjectionError(f"{field}_must_be_sha256")
    return text


def build_domain_history_projection(domain_history: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(domain_history, Mapping) or domain_history.get("schema") != DOMAIN_HISTORY_SCHEMA:
        raise DomainHistoryProjectionError("domain_history_schema_mismatch")
    supplied = _sha(domain_history.get("domain_history_closure_sha256"), "domain_history_closure_sha256")
    expected = sha256_obj({k: v for k, v in domain_history.items() if k != "domain_history_closure_sha256"})
    if supplied != expected:
        raise DomainHistoryProjectionError("domain_history_hash_mismatch")
    if domain_history.get("status") != "DOMAIN_HISTORY_CLOSED_SHADOW_ONLY":
        raise DomainHistoryProjectionError("domain_history_status_invalid")
    if domain_history.get("subject_binding_complete") is not True:
        raise DomainHistoryProjectionError("domain_subject_binding_incomplete")
    if domain_history.get("admission_binding_complete") is not True:
        raise DomainHistoryProjectionError("domain_admission_binding_incomplete")
    if domain_history.get("history_write_performed") is not False:
        raise DomainHistoryProjectionError("domain_history_write_boundary_breached")
    if domain_history.get("semantic_acceptance") != "NOT_PERFORMED":
        raise DomainHistoryProjectionError("domain_history_semantic_acceptance_overclaim")
    if domain_history.get("execution_authority") != "NONE":
        raise DomainHistoryProjectionError("domain_history_authority_breached")

    effects = domain_history.get("effects")
    if not isinstance(effects, Mapping):
        raise DomainHistoryProjectionError("domain_history_effects_missing")
    for key in REQUIRED_FALSE_EFFECTS:
        if effects.get(key) is not False:
            raise DomainHistoryProjectionError(f"domain_history_effect_boundary_breached:{key}")

    safety = domain_history.get("safety")
    if not isinstance(safety, Mapping):
        raise DomainHistoryProjectionError("domain_history_safety_missing")
    for key, expected_value in REQUIRED_SAFETY.items():
        if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
            raise DomainHistoryProjectionError(f"unsafe_domain_history:{key}")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_DOMAIN_HISTORY_PROJECTION",
        "source_domain_history_closure_sha256": supplied,
        "case_id": domain_history.get("case_id"),
        "case_sha256": _sha(domain_history.get("case_sha256"), "case_sha256"),
        "case_binding_sha256": _sha(domain_history.get("case_binding_sha256"), "case_binding_sha256"),
        "case_qualified_replay_input_sha256": _sha(
            domain_history.get("case_qualified_replay_input_sha256"),
            "case_qualified_replay_input_sha256",
        ),
        "domain_subject_integrity": "VERIFIED_SHADOW_ONLY",
        "admission_integrity": "VERIFIED_SHADOW_ONLY",
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
            "domain_subject_binding_is_not_current_truth": True,
            "domain_history_projection_is_not_semantic_acceptance": True,
            "human_reveal_receipt_is_not_human_identity_signature": True,
            "projection_cannot_create_missing_custody": True,
            "projection_cannot_widen_hold_to_pass": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
