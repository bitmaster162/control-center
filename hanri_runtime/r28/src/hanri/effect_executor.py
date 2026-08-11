from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .effect_governance import (
    EffectGovernanceError,
    approval_matches,
    canonical_json,
    iso_utc,
)

EXECUTOR_POLICY_VERSION = "37.1.0-bounded-projection-executor-v1"
UTC = dt.timezone.utc


class ProjectionAdapter(Protocol):
    def read(self) -> bytes: ...
    def write(self, payload: bytes) -> None: ...


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_executor_policy(path: str | Path) -> dict[str, Any]:
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if policy.get("policy_version") != EXECUTOR_POLICY_VERSION:
        raise EffectGovernanceError(
            f"expected policy_version={EXECUTOR_POLICY_VERSION}; got {policy.get('policy_version')!r}"
        )
    if policy.get("execution_mode") != "APPROVAL_REQUIRED":
        raise EffectGovernanceError("R37 phase 2 requires execution_mode=APPROVAL_REQUIRED")
    if policy.get("can_trade") is not False or policy.get("capital_permission") != "DENY":
        raise EffectGovernanceError("R37 phase 2 capital ceiling mismatch")
    return policy


def _require_exact_action_scope(
    decision: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> Mapping[str, Any]:
    if decision.get("policy_verdict") != "HUMAN_APPROVAL":
        raise EffectGovernanceError("phase-2 executor requires a HUMAN_APPROVAL decision")
    action = decision.get("action")
    if not isinstance(action, Mapping):
        raise EffectGovernanceError("decision action missing")

    if action.get("effect_class") != policy.get("allowed_effect_class"):
        raise EffectGovernanceError("effect class is outside the phase-2 executor scope")
    if action.get("operation") != policy.get("allowed_operation"):
        raise EffectGovernanceError("operation is outside the phase-2 executor scope")
    if action.get("target") != policy.get("allowed_target"):
        raise EffectGovernanceError("target is outside the phase-2 executor scope")

    metadata = action.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise EffectGovernanceError("action metadata must be an object")
    if metadata.get("provider") != policy.get("allowed_provider"):
        raise EffectGovernanceError("provider mismatch")
    if metadata.get("provider_target_id") != policy.get("allowed_target_id"):
        raise EffectGovernanceError("provider target id mismatch")

    scope = action.get("scope", {})
    if not isinstance(scope, Mapping):
        raise EffectGovernanceError("action scope must be an object")
    if scope.get("stable_roots_modified") is not False:
        raise EffectGovernanceError("stable root mutation is forbidden")
    if scope.get("authority_generation") is True:
        raise EffectGovernanceError("authority-generation mutation is forbidden")

    return action


def make_projection_action(
    policy: Mapping[str, Any],
    *,
    before_bytes: bytes,
    desired_bytes: bytes,
    snapshot_id: str,
    actor: str = "HANRI_EFFECT_GATEWAY",
) -> dict[str, Any]:
    before_sha = sha256_bytes(before_bytes)
    after_sha = sha256_bytes(desired_bytes)
    if before_sha == after_sha:
        raise EffectGovernanceError("projection candidate requires a material byte delta")
    if not snapshot_id.strip():
        raise EffectGovernanceError("snapshot_id is required")
    return {
        "action_id": f"R37-PROJECTION-{after_sha[:16]}",
        "actor": actor,
        "operation": policy["allowed_operation"],
        "target": policy["allowed_target"],
        "effect_class": policy["allowed_effect_class"],
        "args": {
            "snapshot_id": snapshot_id.strip(),
            "before_sha256": before_sha,
            "after_sha256": after_sha,
        },
        "scope": {
            "stable_roots_modified": False,
            "authority_generation": False,
            "projection_only": True,
        },
        "metadata": {
            "provider": policy["allowed_provider"],
            "provider_target_id": policy["allowed_target_id"],
        },
    }


def prepare_execution(
    decision: Mapping[str, Any],
    approval: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    before_bytes: bytes,
    desired_bytes: bytes,
    now: str | dt.datetime,
) -> dict[str, Any]:
    action = _require_exact_action_scope(decision, policy)

    if not approval_matches(
        decision,
        approval,
        now=now,
        expected_approver=str(policy.get("expected_approver", "ROBERT")),
    ):
        raise EffectGovernanceError("exact hash-bound approval is missing, invalid, or expired")

    before_sha = sha256_bytes(before_bytes)
    after_sha = sha256_bytes(desired_bytes)
    if before_sha == after_sha:
        raise EffectGovernanceError("phase-2 execution requires a material byte delta")

    args = action.get("args", {})
    if not isinstance(args, Mapping):
        raise EffectGovernanceError("action args must be an object")
    if args.get("before_sha256") != before_sha:
        raise EffectGovernanceError("approved before_sha256 does not match supplied before bytes")
    if args.get("after_sha256") != after_sha:
        raise EffectGovernanceError("approved after_sha256 does not match supplied desired bytes")

    plan = {
        "schema_version": 1,
        "policy_version": policy["policy_version"],
        "prepared_at": iso_utc(now),
        "execution_mode": policy["execution_mode"],
        "action_hash": decision["action_hash"],
        "approval_record_sha256": approval["approval_record_sha256"],
        "operation": action["operation"],
        "target": action["target"],
        "provider": policy["allowed_provider"],
        "provider_target_id": policy["allowed_target_id"],
        "expected_before_sha256": before_sha,
        "expected_after_sha256": after_sha,
        "rollback_sha256": before_sha,
        "execution_authorized": True,
        "invariants": {
            "bounded_projection_only": True,
            "stable_roots_modified": False,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }
    plan["plan_sha256"] = hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()
    return plan


def _receipt(base: dict[str, Any]) -> dict[str, Any]:
    receipt = dict(base)
    receipt["receipt_sha256"] = hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()
    return receipt


def execute_projection(
    plan: Mapping[str, Any],
    adapter: ProjectionAdapter,
    *,
    before_bytes: bytes,
    desired_bytes: bytes,
    now: str | dt.datetime,
) -> dict[str, Any]:
    if plan.get("execution_authorized") is not True:
        raise EffectGovernanceError("execution plan is not authorized")
    if plan.get("policy_version") != EXECUTOR_POLICY_VERSION:
        raise EffectGovernanceError("execution plan policy mismatch")

    expected_before = str(plan["expected_before_sha256"])
    expected_after = str(plan["expected_after_sha256"])
    if sha256_bytes(before_bytes) != expected_before:
        raise EffectGovernanceError("before bytes do not match execution plan")
    if sha256_bytes(desired_bytes) != expected_after:
        raise EffectGovernanceError("desired bytes do not match execution plan")

    observed_before = adapter.read()
    observed_before_sha = sha256_bytes(observed_before)
    if observed_before_sha != expected_before:
        return _receipt(
            {
                "schema_version": 1,
                "policy_version": plan["policy_version"],
                "generated_at": iso_utc(now),
                "status": "PRECONDITION_FAILED",
                "effect_rung": "TARGET_READBACK",
                "action_hash": plan["action_hash"],
                "plan_sha256": plan["plan_sha256"],
                "provider_target_id": plan["provider_target_id"],
                "expected_before_sha256": expected_before,
                "observed_before_sha256": observed_before_sha,
                "expected_after_sha256": expected_after,
                "observed_after_sha256": None,
                "rollback_attempted": False,
                "rollback_verified": False,
                "execution_effects_performed": 0,
                "can_trade": False,
                "capital_permission": "DENY",
            }
        )

    write_invoked = False
    write_error: str | None = None
    observed_after_sha: str | None = None
    try:
        write_invoked = True
        adapter.write(desired_bytes)
        observed_after_sha = sha256_bytes(adapter.read())
        if observed_after_sha == expected_after:
            return _receipt(
                {
                    "schema_version": 1,
                    "policy_version": plan["policy_version"],
                    "generated_at": iso_utc(now),
                    "status": "PASS",
                    "effect_rung": "SEMANTIC_EFFECT_VERIFIED",
                    "action_hash": plan["action_hash"],
                    "plan_sha256": plan["plan_sha256"],
                    "provider_target_id": plan["provider_target_id"],
                    "expected_before_sha256": expected_before,
                    "observed_before_sha256": observed_before_sha,
                    "expected_after_sha256": expected_after,
                    "observed_after_sha256": observed_after_sha,
                    "rollback_attempted": False,
                    "rollback_verified": False,
                    "execution_effects_performed": 1,
                    "can_trade": False,
                    "capital_permission": "DENY",
                }
            )
    except Exception as exc:
        write_error = f"{type(exc).__name__}: {exc}"

    rollback_verified = False
    rollback_observed_sha: str | None = None
    rollback_error: str | None = None
    try:
        adapter.write(before_bytes)
        rollback_observed_sha = sha256_bytes(adapter.read())
        rollback_verified = rollback_observed_sha == expected_before
    except Exception as exc:
        rollback_error = f"{type(exc).__name__}: {exc}"

    return _receipt(
        {
            "schema_version": 1,
            "policy_version": plan["policy_version"],
            "generated_at": iso_utc(now),
            "status": "ROLLED_BACK" if rollback_verified else "ROLLBACK_FAILED",
            "effect_rung": "TARGET_READBACK",
            "action_hash": plan["action_hash"],
            "plan_sha256": plan["plan_sha256"],
            "provider_target_id": plan["provider_target_id"],
            "expected_before_sha256": expected_before,
            "observed_before_sha256": observed_before_sha,
            "expected_after_sha256": expected_after,
            "observed_after_sha256": observed_after_sha,
            "write_invoked": write_invoked,
            "write_error": write_error,
            "rollback_attempted": True,
            "rollback_verified": rollback_verified,
            "rollback_observed_sha256": rollback_observed_sha,
            "rollback_error": rollback_error,
            "execution_effects_performed": 2 if write_invoked else 1,
            "can_trade": False,
            "capital_permission": "DENY",
        }
    )
