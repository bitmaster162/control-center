from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .guarded_cli import enhanced_sanitize

POLICY_VERSION = "37.0.0-effect-governance-v1"
EFFECT_CLASSES = {
    "READ_ONLY",
    "WRITE_REVERSIBLE",
    "WRITE_EXTERNAL",
    "AUTHORITY_CHANGE",
    "IRREVERSIBLE",
    "CAPITAL",
    "UNKNOWN",
}
VERDICTS = {"ALLOW", "DENY", "HUMAN_APPROVAL"}
UTC = dt.timezone.utc


class EffectGovernanceError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_time(value: str | dt.datetime) -> dt.datetime:
    if isinstance(value, dt.datetime):
        parsed = value
    else:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso_utc(value: str | dt.datetime | None = None) -> str:
    parsed = parse_time(value or dt.datetime.now(UTC))
    return parsed.isoformat().replace("+00:00", "Z")


def load_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if policy.get("policy_version") != POLICY_VERSION:
        raise EffectGovernanceError(
            f"expected policy_version={POLICY_VERSION}; got {policy.get('policy_version')!r}"
        )
    if policy.get("enforcement_mode") != "SHADOW_ONLY":
        raise EffectGovernanceError("R37 pilot requires enforcement_mode=SHADOW_ONLY")
    return policy


def _operation_token(action: Mapping[str, Any]) -> str:
    return str(action.get("operation", "")).strip().lower().replace("-", "_")


def infer_effect_class(action: Mapping[str, Any]) -> str:
    explicit = str(action.get("effect_class", "")).strip().upper()
    if explicit:
        return explicit if explicit in EFFECT_CLASSES else "UNKNOWN"

    operation = _operation_token(action)
    if any(token in operation for token in ("trade", "order", "transfer_funds", "withdraw", "deposit", "capital")):
        return "CAPITAL"
    if any(token in operation for token in ("permission", "authority", "credential", "rotate_secret", "role_change")):
        return "AUTHORITY_CHANGE"
    if any(token in operation for token in ("delete", "destroy", "purge", "revoke")):
        return "IRREVERSIBLE"
    if any(token in operation for token in ("send", "email", "message", "publish", "post_external")):
        return "WRITE_EXTERNAL"
    if any(token in operation for token in ("create", "update", "write", "patch", "commit", "merge", "deploy", "register")):
        return "WRITE_REVERSIBLE"
    if any(token in operation for token in ("read", "get", "fetch", "list", "search", "inspect", "verify")):
        return "READ_ONLY"
    return "UNKNOWN"


def normalize_action(action: Mapping[str, Any]) -> dict[str, Any]:
    required = ("action_id", "actor", "operation", "target")
    missing = [name for name in required if not str(action.get(name, "")).strip()]
    if missing:
        raise EffectGovernanceError(f"missing required action fields: {', '.join(missing)}")

    findings: list[dict[str, str]] = []
    normalized = {
        "action_id": str(action["action_id"]).strip(),
        "actor": str(action["actor"]).strip(),
        "operation": str(action["operation"]).strip(),
        "target": str(action["target"]).strip(),
        "effect_class": infer_effect_class(action),
        "args": action.get("args", {}),
        "scope": action.get("scope", {}),
        "metadata": action.get("metadata", {}),
    }
    sanitized = enhanced_sanitize(normalized, findings)
    sanitized["secret_boundary"] = {
        "finding_count": len(findings),
        "raw_values_persisted": False,
    }
    return sanitized


def action_hash(action: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    normalized = normalize_action(action)
    return sha256_text(canonical_json(normalized)), normalized


def _target_override(target: str, policy: Mapping[str, Any]) -> dict[str, Any] | None:
    target_lower = target.lower()
    for rule in policy.get("target_overrides", []):
        prefix = str(rule.get("prefix", "")).lower()
        if prefix and target_lower.startswith(prefix):
            return dict(rule)
    return None


def evaluate_action(
    action: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    now: str | dt.datetime | None = None,
) -> dict[str, Any]:
    digest, normalized = action_hash(action)
    effect_class = normalized["effect_class"]
    class_policy = dict(policy.get("effect_classes", {}).get(effect_class, {}))
    verdict = str(class_policy.get("verdict", policy.get("default_verdict", "DENY"))).upper()
    risk = str(class_policy.get("risk", "CRITICAL")).upper()
    reason = str(class_policy.get("reason", "No matching effect policy; fail closed."))

    override = _target_override(normalized["target"], policy)
    if override is not None:
        verdict = str(override.get("verdict", verdict)).upper()
        risk = str(override.get("risk", risk)).upper()
        reason = str(override.get("reason", reason))

    if effect_class == "CAPITAL" and policy.get("capital_permission") == "DENY":
        verdict = "DENY"
        risk = "CRITICAL"
        reason = "Capital effects are hard-denied by current authority ceiling."

    if verdict not in VERDICTS:
        raise EffectGovernanceError(f"invalid verdict from policy: {verdict}")

    approval = None
    if verdict == "HUMAN_APPROVAL":
        approval = {
            "required": True,
            "human_sovereign": policy.get("human_sovereign", "ROBERT"),
            "bind_to": ["action_hash", "actor", "operation", "target", "args", "scope"],
            "default_expiry_seconds": int(policy.get("approval_expiry_seconds", 900)),
        }

    return {
        "schema_version": 1,
        "policy_version": policy["policy_version"],
        "evaluated_at": iso_utc(now),
        "enforcement_mode": policy["enforcement_mode"],
        "action_hash": digest,
        "action": normalized,
        "risk": risk,
        "policy_verdict": verdict,
        "execution_authorized": False,
        "approval": approval,
        "reason": reason,
        "invariants": {
            "shadow_only": True,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }


def evaluate_actions(
    actions: Iterable[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    now: str | dt.datetime | None = None,
) -> dict[str, Any]:
    decisions = [evaluate_action(action, policy, now=now) for action in actions]
    counts = {verdict: 0 for verdict in sorted(VERDICTS)}
    for decision in decisions:
        counts[decision["policy_verdict"]] += 1
    receipt = {
        "schema_version": 1,
        "policy_version": policy["policy_version"],
        "generated_at": iso_utc(now),
        "enforcement_mode": policy["enforcement_mode"],
        "decision_count": len(decisions),
        "verdict_counts": counts,
        "decisions": decisions,
        "execution_effects_performed": 0,
    }
    receipt["receipt_sha256"] = sha256_text(canonical_json(receipt))
    return receipt


def make_approval_record(
    decision: Mapping[str, Any],
    *,
    approver: str,
    issued_at: str | dt.datetime,
    expires_at: str | dt.datetime,
    scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if decision.get("policy_verdict") != "HUMAN_APPROVAL":
        raise EffectGovernanceError("approval records are only valid for HUMAN_APPROVAL decisions")
    issued = parse_time(issued_at)
    expires = parse_time(expires_at)
    if expires <= issued:
        raise EffectGovernanceError("approval expiry must be after issue time")
    record = {
        "schema_version": 1,
        "approval_type": "HASH_BOUND_HUMAN_APPROVAL",
        "action_hash": decision["action_hash"],
        "approver": approver,
        "decision": "APPROVE",
        "issued_at": iso_utc(issued),
        "expires_at": iso_utc(expires),
        "scope": dict(scope or {}),
    }
    record["approval_record_sha256"] = sha256_text(canonical_json(record))
    return record


def approval_matches(
    decision: Mapping[str, Any],
    approval: Mapping[str, Any],
    *,
    now: str | dt.datetime,
    expected_approver: str,
) -> bool:
    if decision.get("policy_verdict") != "HUMAN_APPROVAL":
        return False
    if approval.get("approval_type") != "HASH_BOUND_HUMAN_APPROVAL":
        return False
    if approval.get("decision") != "APPROVE":
        return False
    if approval.get("action_hash") != decision.get("action_hash"):
        return False
    if approval.get("approver") != expected_approver:
        return False
    if parse_time(now) >= parse_time(str(approval.get("expires_at", "1970-01-01T00:00:00Z"))):
        return False

    unsigned = dict(approval)
    claimed = str(unsigned.pop("approval_record_sha256", ""))
    return claimed == sha256_text(canonical_json(unsigned))
