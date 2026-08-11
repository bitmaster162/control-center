from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, Mapping

from .effect_governance import EffectGovernanceError, approval_matches, canonical_json, iso_utc

APPROVAL_QUEUE_POLICY_VERSION = "37.2.0-approval-queue-v1"
UTC = dt.timezone.utc


def _parse_time(value: str | dt.datetime) -> dt.datetime:
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _require_sha(value: Any, field: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise EffectGovernanceError(f"{field} must be a lowercase SHA-256")
    return text


def approval_command(action_hash: str) -> str:
    return f"APPROVE_R37_EFFECT:{_require_sha(action_hash, 'action_hash')}"


def _safe_action_summary(action: Mapping[str, Any]) -> dict[str, Any]:
    args = action.get("args", {})
    metadata = action.get("metadata", {})
    if not isinstance(args, Mapping):
        args = {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    summary = {
        "actor": str(action.get("actor", "UNKNOWN")),
        "operation": str(action.get("operation", "UNKNOWN")),
        "effect_class": str(action.get("effect_class", "UNKNOWN")),
        "target": str(action.get("target", "UNKNOWN")),
        "provider": str(metadata.get("provider", "UNKNOWN")),
        "provider_target_id": str(metadata.get("provider_target_id", "")),
        "snapshot_id": args.get("snapshot_id"),
        "before_sha256": args.get("before_sha256"),
        "after_sha256": args.get("after_sha256"),
    }
    # Never project arbitrary args. Queue projection is a minimal display surface.
    return summary


def project_queue_item(
    decision: Mapping[str, Any],
    *,
    now: str | dt.datetime,
    approval: Mapping[str, Any] | None = None,
    execution_receipt: Mapping[str, Any] | None = None,
    approval_expires_at: str | dt.datetime | None = None,
    expected_approver: str = "ROBERT",
) -> dict[str, Any]:
    action = decision.get("action")
    if not isinstance(action, Mapping):
        raise EffectGovernanceError("decision action missing")
    action_hash_value = _require_sha(decision.get("action_hash"), "action_hash")
    now_dt = _parse_time(now)
    verdict = str(decision.get("policy_verdict", "DENY"))

    status: str
    command: str | None = None
    expires_at: str | None = None
    receipt_status: str | None = None
    receipt_sha256: str | None = None

    if execution_receipt is not None:
        receipt_hash = _require_sha(execution_receipt.get("action_hash"), "execution_receipt.action_hash")
        if receipt_hash != action_hash_value:
            raise EffectGovernanceError("execution receipt action_hash mismatch")
        receipt_status = str(execution_receipt.get("status", "UNKNOWN"))
        if execution_receipt.get("receipt_sha256"):
            receipt_sha256 = _require_sha(execution_receipt.get("receipt_sha256"), "receipt_sha256")
        if receipt_status == "PASS" and execution_receipt.get("effect_rung") == "SEMANTIC_EFFECT_VERIFIED":
            status = "EXECUTED_VERIFIED"
        elif receipt_status == "ROLLED_BACK":
            status = "ROLLED_BACK"
        elif receipt_status == "ROLLBACK_FAILED":
            status = "FAILED"
        else:
            status = "FAILED"
    elif verdict == "DENY":
        status = "DENIED"
    elif verdict != "HUMAN_APPROVAL":
        status = "NOT_APPLICABLE"
    elif approval is not None and approval_matches(
        decision,
        approval,
        now=now_dt,
        expected_approver=expected_approver,
    ):
        status = "APPROVED_NOT_EXECUTED"
        expires_at = str(approval.get("expires_at") or "") or None
    else:
        if approval_expires_at is None:
            raise EffectGovernanceError("pending approval projection requires approval_expires_at")
        expiry_dt = _parse_time(approval_expires_at)
        expires_at = iso_utc(expiry_dt)
        if now_dt >= expiry_dt:
            status = "EXPIRED"
        else:
            status = "PENDING_APPROVAL"
            command = approval_command(action_hash_value)

    safe = _safe_action_summary(action)
    item = {
        "queue_id": f"AQ-{action_hash_value[:16]}",
        "status": status,
        "action_hash": action_hash_value,
        **safe,
        "approval_required": verdict == "HUMAN_APPROVAL",
        "approval_command": command,
        "expires_at": expires_at,
        "receipt_status": receipt_status,
        "receipt_sha256": receipt_sha256,
        "replay_allowed": False,
        "evidence_state": "HASH_VERIFIED" if status in {"EXECUTED_VERIFIED", "ROLLED_BACK"} else "RECEIPTED",
    }
    return item


def build_queue_projection(items: list[Mapping[str, Any]], *, generated_at: str | dt.datetime) -> dict[str, Any]:
    rows = [dict(item) for item in items]
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status", "UNKNOWN"))
        counts[status] = counts.get(status, 0) + 1
    projection = {
        "schema_version": 1,
        "policy_version": APPROVAL_QUEUE_POLICY_VERSION,
        "generated_at": iso_utc(generated_at),
        "mode": "READ_ONLY_PROJECTION",
        "sovereign_channel": "EXACT_HUMAN_GATE",
        "auto_approval": False,
        "auto_execution": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "summary": {
            "total": len(rows),
            "pending": counts.get("PENDING_APPROVAL", 0),
            "approved_not_executed": counts.get("APPROVED_NOT_EXECUTED", 0),
            "executed_verified": counts.get("EXECUTED_VERIFIED", 0),
            "denied": counts.get("DENIED", 0),
            "expired": counts.get("EXPIRED", 0),
            "rolled_back": counts.get("ROLLED_BACK", 0),
            "failed": counts.get("FAILED", 0),
        },
        "items": rows,
    }
    projection["projection_sha256"] = hashlib.sha256(canonical_json(projection).encode("utf-8")).hexdigest()
    return projection
