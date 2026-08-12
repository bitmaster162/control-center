from __future__ import annotations

import copy

import pytest

from hanri.attention_cadence import POLICY_VERSION, choose_interval, decide_wake


def policy(**overrides):
    p = {
        "policy_version": POLICY_VERSION,
        "heartbeat_minutes": 5,
        "urgent_minutes": 5,
        "proposal_minutes": 10,
        "normal_minutes": 15,
        "quiet_minutes": 30,
        "deep_quiet_minutes": 60,
        "quiet_streak": 3,
        "deep_quiet_streak": 6,
        "lease_minutes": 10,
    }
    p.update(overrides)
    return p


def loop(**overrides):
    row = {
        "transition": "NO_DELTA",
        "no_delta_streak": 1,
        "coverage_complete": True,
        "blind_spots": [],
        "active_proposal_count": 0,
        "unresolved_negative_outcomes": [],
        "semantic_digest": "a" * 64,
        "evidence_set_sha256": "b" * 64,
        "effect_boundary": {
            "proposal_only": True,
            "local_state_write_only": True,
            "provider_calls": False,
            "scheduler_install": False,
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
    row.update(overrides)
    return row


def test_normal_cadence_is_15_minutes():
    out = choose_interval(loop(), policy())
    assert out["mode"] == "NORMAL"
    assert out["interval_minutes"] == 15


def test_quiet_and_deep_quiet_backoff():
    assert choose_interval(loop(no_delta_streak=3), policy())["interval_minutes"] == 30
    deep = choose_interval(loop(no_delta_streak=6), policy())
    assert deep["mode"] == "DEEP_QUIET"
    assert deep["interval_minutes"] == 60


def test_coverage_loss_is_urgent():
    out = choose_interval(loop(coverage_complete=False, blind_spots=["OPERATOR"]), policy())
    assert out["mode"] == "URGENT_COVERAGE_REPAIR"
    assert out["interval_minutes"] == 5


def test_negative_outcome_preempts_everything():
    out = choose_interval(loop(no_delta_streak=99, unresolved_negative_outcomes=["R39-X"]), policy())
    assert out["mode"] == "URGENT_SELF_REVIEW"
    assert out["interval_minutes"] == 5


def test_active_proposal_uses_10_minutes():
    out = choose_interval(loop(active_proposal_count=2), policy())
    assert out["mode"] == "PROPOSAL_REVIEW"
    assert out["interval_minutes"] == 10


def test_fixed_heartbeat_can_skip_until_full_scan_due():
    first = decide_wake(loop_receipt=loop(), prior_cadence_state=None, policy=policy(), now="2026-08-12T00:00:00Z")
    assert first["receipt"]["action"] == "RUN_FULL_ATTENTION"
    assert first["receipt"]["next_full_attention_at"] == "2026-08-12T00:15:00Z"
    second = decide_wake(loop_receipt=loop(), prior_cadence_state=first["state"], policy=policy(), now="2026-08-12T00:05:00Z")
    assert second["receipt"]["action"] == "SKIP_NOT_DUE"
    third = decide_wake(loop_receipt=loop(), prior_cadence_state=second["state"], policy=policy(), now="2026-08-12T00:15:00Z")
    assert third["receipt"]["action"] == "RUN_FULL_ATTENTION"
    assert third["state"]["full_attention_run_count"] == 2


def test_overlap_is_skipped_not_executed():
    first = decide_wake(loop_receipt=loop(), prior_cadence_state=None, policy=policy(), now="2026-08-12T00:00:00Z")
    overlap = decide_wake(loop_receipt=loop(), prior_cadence_state=first["state"], policy=policy(), now="2026-08-12T00:05:00Z", lease_active=True)
    assert overlap["receipt"]["action"] == "SKIP_OVERLAP"
    assert overlap["state"]["full_attention_run_count"] == 1
    assert overlap["state"]["overlap_skip_count"] == 1


def test_tampered_cadence_state_fails_closed():
    first = decide_wake(loop_receipt=loop(), prior_cadence_state=None, policy=policy(), now="2026-08-12T00:00:00Z")
    bad = copy.deepcopy(first["state"])
    bad["heartbeat_count"] = 999
    with pytest.raises(ValueError, match="prior cadence state SHA mismatch"):
        decide_wake(loop_receipt=loop(), prior_cadence_state=bad, policy=policy(), now="2026-08-12T00:05:00Z")


def test_unsafe_loop_receipt_fails_closed():
    bad = loop()
    bad["effect_boundary"]["can_trade"] = True
    with pytest.raises(ValueError, match="can_trade must remain false"):
        choose_interval(bad, policy())


def test_policy_rejects_non_monotonic_cadence():
    with pytest.raises(ValueError, match="cadence minutes must be monotonic"):
        choose_interval(loop(), policy(proposal_minutes=20, normal_minutes=15))


def test_effect_boundary_never_authorizes_scheduler_or_effects():
    out = decide_wake(loop_receipt=loop(), prior_cadence_state=None, policy=policy(), now="2026-08-12T00:00:00Z")
    boundary = out["receipt"]["effect_boundary"]
    assert boundary["scheduler_install"] is False
    assert boundary["scheduler_modify"] is False
    assert boundary["provider_calls"] is False
    assert boundary["self_apply"] is False
    assert boundary["auto_dispatch"] is False
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"
    assert out["receipt"]["execution_effects_performed"] == 0
