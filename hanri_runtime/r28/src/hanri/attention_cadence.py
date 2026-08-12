from __future__ import annotations

import copy
import datetime as dt
from typing import Any, Mapping

from hanri.attention_governor import canonical_sha256

POLICY_VERSION = "39.3.2-attention-cadence-v1"
UTC = dt.timezone.utc


def _parse_time(value: str) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _safe_loop_boundary(loop_receipt: Mapping[str, Any]) -> None:
    boundary = dict(loop_receipt.get("effect_boundary", {}))
    if bool(boundary.get("can_trade", False)):
        raise ValueError("loop receipt can_trade must remain false")
    if str(boundary.get("capital_permission", "DENY")).upper() != "DENY":
        raise ValueError("loop receipt capital_permission must remain DENY")
    for key in (
        "provider_calls", "scheduler_install", "human_decision_execution",
        "self_apply", "skill_install", "system_write", "operator_message",
        "auto_dispatch", "external_messages",
    ):
        if bool(boundary.get(key, False)):
            raise ValueError(f"loop receipt {key} must remain false")


def _validate_policy(policy: Mapping[str, Any]) -> dict[str, int]:
    if str(policy.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    values = {
        "heartbeat_minutes": int(policy.get("heartbeat_minutes", 5)),
        "urgent_minutes": int(policy.get("urgent_minutes", 5)),
        "proposal_minutes": int(policy.get("proposal_minutes", 10)),
        "normal_minutes": int(policy.get("normal_minutes", 15)),
        "quiet_minutes": int(policy.get("quiet_minutes", 30)),
        "deep_quiet_minutes": int(policy.get("deep_quiet_minutes", 60)),
        "quiet_streak": int(policy.get("quiet_streak", 3)),
        "deep_quiet_streak": int(policy.get("deep_quiet_streak", 6)),
        "lease_minutes": int(policy.get("lease_minutes", 10)),
    }
    for key, value in values.items():
        if value < 1:
            raise ValueError(f"{key} must be >= 1")
    if values["heartbeat_minutes"] > values["urgent_minutes"]:
        raise ValueError("heartbeat_minutes cannot exceed urgent_minutes")
    if not (
        values["urgent_minutes"] <= values["proposal_minutes"] <= values["normal_minutes"]
        <= values["quiet_minutes"] <= values["deep_quiet_minutes"]
    ):
        raise ValueError("cadence minutes must be monotonic")
    if values["quiet_streak"] >= values["deep_quiet_streak"]:
        raise ValueError("quiet_streak must be less than deep_quiet_streak")
    return values


def choose_interval(loop_receipt: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    values = _validate_policy(policy)
    _safe_loop_boundary(loop_receipt)
    coverage_complete = bool(loop_receipt.get("coverage_complete", False))
    blind_spots = sorted({str(x).strip().upper() for x in loop_receipt.get("blind_spots", []) if str(x).strip()})
    active_proposals = max(0, int(loop_receipt.get("active_proposal_count", 0)))
    negative_outcomes = sorted({str(x).strip() for x in loop_receipt.get("unresolved_negative_outcomes", []) if str(x).strip()})
    no_delta_streak = max(0, int(loop_receipt.get("no_delta_streak", 0)))
    transition = str(loop_receipt.get("transition", "UNKNOWN")).strip().upper()

    if negative_outcomes:
        return {"mode": "URGENT_SELF_REVIEW", "interval_minutes": values["urgent_minutes"], "reason": "unresolved negative recommendation outcome"}
    if not coverage_complete or blind_spots:
        return {"mode": "URGENT_COVERAGE_REPAIR", "interval_minutes": values["urgent_minutes"], "reason": "attention coverage is incomplete"}
    if active_proposals > 0:
        return {"mode": "PROPOSAL_REVIEW", "interval_minutes": values["proposal_minutes"], "reason": "material improvement proposal is active"}
    if no_delta_streak >= values["deep_quiet_streak"]:
        return {"mode": "DEEP_QUIET", "interval_minutes": values["deep_quiet_minutes"], "reason": "repeated semantic no-delta wakes"}
    if no_delta_streak >= values["quiet_streak"]:
        return {"mode": "QUIET", "interval_minutes": values["quiet_minutes"], "reason": "stable semantic evidence set"}
    if transition == "SEMANTIC_DELTA":
        return {"mode": "POST_DELTA_OBSERVE", "interval_minutes": values["normal_minutes"], "reason": "semantic evidence changed; keep normal observation cadence"}
    return {"mode": "NORMAL", "interval_minutes": values["normal_minutes"], "reason": "balanced coverage with no material findings"}


def decide_wake(*, loop_receipt: Mapping[str, Any], prior_cadence_state: Mapping[str, Any] | None, policy: Mapping[str, Any], now: str, lease_active: bool = False) -> dict[str, Any]:
    values = _validate_policy(policy)
    _safe_loop_boundary(loop_receipt)
    current = _parse_time(now)
    cadence = choose_interval(loop_receipt, policy)
    prior = copy.deepcopy(dict(prior_cadence_state or {}))
    if prior:
        if str(prior.get("policy_version", "")) != POLICY_VERSION:
            raise ValueError("prior cadence state policy_version mismatch")
        expected = canonical_sha256({k: v for k, v in prior.items() if k != "state_sha256"})
        if str(prior.get("state_sha256", "")) != expected:
            raise ValueError("prior cadence state SHA mismatch")

    if lease_active:
        action, due, reason = "SKIP_OVERLAP", False, "an attention cycle lease is already active"
    else:
        next_due_text = str(prior.get("next_full_attention_at", "")) if prior else ""
        due_at = _parse_time(next_due_text) if next_due_text else None
        due = due_at is None or current >= due_at
        action = "RUN_FULL_ATTENTION" if due else "SKIP_NOT_DUE"
        reason = cadence["reason"] if due else "heartbeat arrived before adaptive full-attention due time"

    heartbeat_count = int(prior.get("heartbeat_count", 0)) + 1 if prior else 1
    full_run_count = int(prior.get("full_attention_run_count", 0)) + (1 if action == "RUN_FULL_ATTENTION" else 0)
    overlap_skip_count = int(prior.get("overlap_skip_count", 0)) + (1 if action == "SKIP_OVERLAP" else 0)
    not_due_skip_count = int(prior.get("not_due_skip_count", 0)) + (1 if action == "SKIP_NOT_DUE" else 0)

    if action == "RUN_FULL_ATTENTION":
        next_full = current + dt.timedelta(minutes=int(cadence["interval_minutes"]))
        last_full = current
    else:
        next_full = _parse_time(str(prior.get("next_full_attention_at"))) if prior.get("next_full_attention_at") else current
        last_full_text = str(prior.get("last_full_attention_at", "")) if prior else ""
        last_full = _parse_time(last_full_text) if last_full_text else None

    state = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": _iso(current),
        "heartbeat_minutes": values["heartbeat_minutes"],
        "heartbeat_count": heartbeat_count,
        "full_attention_run_count": full_run_count,
        "overlap_skip_count": overlap_skip_count,
        "not_due_skip_count": not_due_skip_count,
        "last_action": action,
        "last_mode": cadence["mode"],
        "last_interval_minutes": int(cadence["interval_minutes"]),
        "last_full_attention_at": _iso(last_full) if last_full else None,
        "next_full_attention_at": _iso(next_full),
        "last_loop_semantic_digest": str(loop_receipt.get("semantic_digest", "")),
        "last_loop_evidence_set_sha256": str(loop_receipt.get("evidence_set_sha256", "")),
        "effect_boundary": {
            "advisory_only": True,
            "local_state_write_only": True,
            "scheduler_install": False,
            "scheduler_modify": False,
            "provider_calls": False,
            "human_decision_execution": False,
            "self_apply": False,
            "skill_install": False,
            "system_write": False,
            "operator_message": False,
            "auto_dispatch": False,
            "external_messages": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }
    state["state_sha256"] = canonical_sha256(state)
    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": _iso(current),
        "action": action,
        "due": due,
        "mode": cadence["mode"],
        "interval_minutes": int(cadence["interval_minutes"]),
        "reason": reason,
        "heartbeat_minutes": values["heartbeat_minutes"],
        "next_full_attention_at": state["next_full_attention_at"],
        "lease_minutes": values["lease_minutes"],
        "lease_active": bool(lease_active),
        "heartbeat_count": heartbeat_count,
        "full_attention_run_count": full_run_count,
        "overlap_skip_count": overlap_skip_count,
        "not_due_skip_count": not_due_skip_count,
        "state_sha256": state["state_sha256"],
        "effect_boundary": copy.deepcopy(state["effect_boundary"]),
        "execution_effects_performed": 0,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"state": state, "receipt": receipt}


__all__ = ["POLICY_VERSION", "choose_interval", "decide_wake"]
