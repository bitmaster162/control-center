from __future__ import annotations

from pathlib import Path

import pytest

from hanri.effect_governance import evaluate_action, load_policy, make_approval_record
from hanri.effect_executor import (
    EffectGovernanceError,
    execute_projection,
    load_executor_policy,
    make_projection_action,
    prepare_execution,
)

APP_ROOT = Path(__file__).parents[1]
EFFECT_POLICY = load_policy(APP_ROOT / "config" / "r37.effect-policy.json")
EXECUTOR_POLICY = load_executor_policy(APP_ROOT / "config" / "r37.phase2.executor-policy.json")
NOW = "2026-08-12T03:20:00Z"


class MemoryAdapter:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.writes: list[bytes] = []
        self.corrupt_after_write = False
        self.raise_after_write = False

    def read(self) -> bytes:
        return self.payload

    def write(self, payload: bytes) -> None:
        self.writes.append(payload)
        self.payload = payload
        if self.raise_after_write:
            self.raise_after_write = False
            raise RuntimeError("simulated provider interruption")
        if self.corrupt_after_write:
            self.corrupt_after_write = False
            self.payload = payload + b"-CORRUPT"


def build_valid() -> tuple[bytes, bytes, dict, dict, dict]:
    before = b"<html>R36 LIVE</html>"
    desired = b"<html>R36 LIVE / R37 PHASE1 CLOSED</html>"
    action = make_projection_action(
        EXECUTOR_POLICY,
        before_bytes=before,
        desired_bytes=desired,
        snapshot_id="R64-P4-R37-PHASE1-CLOSED",
    )
    decision = evaluate_action(action, EFFECT_POLICY, now=NOW)
    approval = make_approval_record(
        decision,
        approver="ROBERT",
        issued_at="2026-08-12T03:20:01Z",
        expires_at="2026-08-12T03:30:01Z",
    )
    return before, desired, action, decision, approval


def test_exact_projection_candidate_requires_human_approval() -> None:
    before, desired, action, decision, _ = build_valid()
    assert decision["policy_verdict"] == "HUMAN_APPROVAL"
    assert action["args"]["before_sha256"] != action["args"]["after_sha256"]
    assert action["metadata"]["provider_target_id"] == EXECUTOR_POLICY["allowed_target_id"]


def test_exact_approval_and_bytes_prepare_authorized_plan() -> None:
    before, desired, _, decision, approval = build_valid()
    plan = prepare_execution(
        decision,
        approval,
        EXECUTOR_POLICY,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:21:00Z",
    )
    assert plan["execution_authorized"] is True
    assert plan["expected_before_sha256"] == decision["action"]["args"]["before_sha256"]
    assert plan["expected_after_sha256"] == decision["action"]["args"]["after_sha256"]
    assert plan["invariants"]["stable_roots_modified"] is False
    assert plan["invariants"]["can_trade"] is False


def test_payload_substitution_after_approval_is_rejected() -> None:
    before, desired, _, decision, approval = build_valid()
    with pytest.raises(EffectGovernanceError, match="after_sha256"):
        prepare_execution(
            decision,
            approval,
            EXECUTOR_POLICY,
            before_bytes=before,
            desired_bytes=desired + b"CHANGED",
            now="2026-08-12T03:21:00Z",
        )


def test_wrong_provider_target_id_is_rejected() -> None:
    before, desired, action, _, _ = build_valid()
    action["metadata"]["provider_target_id"] = "OTHER_FILE"
    decision = evaluate_action(action, EFFECT_POLICY, now=NOW)
    approval = make_approval_record(
        decision,
        approver="ROBERT",
        issued_at="2026-08-12T03:20:01Z",
        expires_at="2026-08-12T03:30:01Z",
    )
    with pytest.raises(EffectGovernanceError, match="provider target id"):
        prepare_execution(
            decision,
            approval,
            EXECUTOR_POLICY,
            before_bytes=before,
            desired_bytes=desired,
            now="2026-08-12T03:21:00Z",
        )


def test_expired_approval_is_rejected_before_execution() -> None:
    before, desired, _, decision, approval = build_valid()
    with pytest.raises(EffectGovernanceError, match="approval"):
        prepare_execution(
            decision,
            approval,
            EXECUTOR_POLICY,
            before_bytes=before,
            desired_bytes=desired,
            now="2026-08-12T03:31:00Z",
        )


def test_target_precondition_drift_causes_zero_writes() -> None:
    before, desired, _, decision, approval = build_valid()
    plan = prepare_execution(
        decision,
        approval,
        EXECUTOR_POLICY,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:21:00Z",
    )
    adapter = MemoryAdapter(b"<html>someone changed target</html>")
    receipt = execute_projection(
        plan,
        adapter,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:22:00Z",
    )
    assert receipt["status"] == "PRECONDITION_FAILED"
    assert receipt["execution_effects_performed"] == 0
    assert adapter.writes == []


def test_success_requires_independent_readback() -> None:
    before, desired, _, decision, approval = build_valid()
    plan = prepare_execution(
        decision,
        approval,
        EXECUTOR_POLICY,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:21:00Z",
    )
    adapter = MemoryAdapter(before)
    receipt = execute_projection(
        plan,
        adapter,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:22:00Z",
    )
    assert receipt["status"] == "PASS"
    assert receipt["effect_rung"] == "SEMANTIC_EFFECT_VERIFIED"
    assert receipt["observed_after_sha256"] == receipt["expected_after_sha256"]
    assert receipt["execution_effects_performed"] == 1
    assert adapter.payload == desired


def test_corrupt_postwrite_readback_triggers_verified_rollback() -> None:
    before, desired, _, decision, approval = build_valid()
    plan = prepare_execution(
        decision,
        approval,
        EXECUTOR_POLICY,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:21:00Z",
    )
    adapter = MemoryAdapter(before)
    adapter.corrupt_after_write = True
    receipt = execute_projection(
        plan,
        adapter,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:22:00Z",
    )
    assert receipt["status"] == "ROLLED_BACK"
    assert receipt["rollback_attempted"] is True
    assert receipt["rollback_verified"] is True
    assert adapter.payload == before
    assert len(adapter.writes) == 2


def test_provider_interruption_after_write_triggers_rollback() -> None:
    before, desired, _, decision, approval = build_valid()
    plan = prepare_execution(
        decision,
        approval,
        EXECUTOR_POLICY,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:21:00Z",
    )
    adapter = MemoryAdapter(before)
    adapter.raise_after_write = True
    receipt = execute_projection(
        plan,
        adapter,
        before_bytes=before,
        desired_bytes=desired,
        now="2026-08-12T03:22:00Z",
    )
    assert receipt["status"] == "ROLLED_BACK"
    assert receipt["write_error"].startswith("RuntimeError:")
    assert receipt["rollback_verified"] is True
    assert adapter.payload == before
