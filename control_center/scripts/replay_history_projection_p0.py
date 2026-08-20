from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

HISTORY_SCHEMA = "bitevo.shadow_history_replay_verification.v1"
PROJECTION_SCHEMA = "control_center.shadow_replay_history_projection.v1"

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


class ReplayHistoryProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ReplayHistoryProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ReplayHistoryProjectionError(f"{field}_must_be_sha256")
    return text


def build_replay_history_projection(history: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(history, Mapping) or history.get("schema") != HISTORY_SCHEMA:
        raise ReplayHistoryProjectionError("history_schema_mismatch")
    supplied = _sha(history.get("history_verification_sha256"), "history_verification_sha256")
    expected = sha256_obj({k: v for k, v in history.items() if k != "history_verification_sha256"})
    if supplied != expected:
        raise ReplayHistoryProjectionError("history_hash_mismatch")
    if history.get("status") != "HISTORY_CHAIN_VERIFIED_SHADOW_ONLY":
        raise ReplayHistoryProjectionError("history_status_not_verified")
    if history.get("history_write_performed") is not False:
        raise ReplayHistoryProjectionError("history_write_boundary_breached")
    if history.get("semantic_acceptance") != "NOT_PERFORMED":
        raise ReplayHistoryProjectionError("history_semantic_acceptance_overclaim")
    if history.get("execution_authority") != "NONE":
        raise ReplayHistoryProjectionError("history_authority_breached")
    effects = history.get("effects")
    if not isinstance(effects, Mapping):
        raise ReplayHistoryProjectionError("history_effects_missing")
    for key in REQUIRED_FALSE_EFFECTS:
        if effects.get(key) is not False:
            raise ReplayHistoryProjectionError(f"history_effect_boundary_breached:{key}")
    safety = history.get("safety")
    if not isinstance(safety, Mapping):
        raise ReplayHistoryProjectionError("history_safety_missing")
    for key, expected_value in REQUIRED_SAFETY.items():
        if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
            raise ReplayHistoryProjectionError(f"unsafe_history:{key}")
    if history.get("human_reveal_count") != 1:
        raise ReplayHistoryProjectionError("history_reveal_count_invalid")
    if history.get("return_intake_count") != 1:
        raise ReplayHistoryProjectionError("history_return_count_invalid")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_HISTORY_REPLAY_PROJECTION",
        "source_history_verification_sha256": supplied,
        "case_id": history.get("case_id"),
        "case_sha256": _sha(history.get("case_sha256"), "case_sha256"),
        "case_binding_sha256": _sha(history.get("case_binding_sha256"), "case_binding_sha256"),
        "final_ledger_sha256": _sha(history.get("final_ledger_sha256"), "final_ledger_sha256"),
        "final_head_event_sha256": _sha(history.get("final_head_event_sha256"), "final_head_event_sha256"),
        "history_integrity": "VERIFIED_SHADOW_ONLY",
        "one_case_one_reveal": True,
        "one_return_intake": True,
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
            "history_verification_is_not_current_truth": True,
            "history_projection_is_not_semantic_acceptance": True,
            "external_expected_heads_remain_required": True,
            "projection_cannot_repair_a_fork": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
