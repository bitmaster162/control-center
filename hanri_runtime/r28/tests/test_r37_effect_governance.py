from __future__ import annotations

import json
from pathlib import Path

from hanri.effect_governance import (
    action_hash,
    approval_matches,
    evaluate_action,
    evaluate_actions,
    load_policy,
    make_approval_record,
)

APP_ROOT = Path(__file__).parents[1]
POLICY_PATH = APP_ROOT / "config" / "r37.effect-policy.json"
FIXTURE_PATH = APP_ROOT / "data" / "r37_control_center_effect_candidates.json"
NOW = "2026-08-11T20:00:00Z"


def load_fixture_actions() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["actions"]


def test_control_center_shadow_policy_matrix() -> None:
    policy = load_policy(POLICY_PATH)
    receipt = evaluate_actions(load_fixture_actions(), policy, now=NOW)
    decisions = {row["action"]["action_id"]: row for row in receipt["decisions"]}

    assert decisions["CC-R37-READ-001"]["policy_verdict"] == "ALLOW"
    assert decisions["CC-R37-WRITE-001"]["policy_verdict"] == "HUMAN_APPROVAL"
    assert decisions["CC-R37-EXTERNAL-001"]["policy_verdict"] == "HUMAN_APPROVAL"
    assert decisions["CC-R37-AUTHORITY-001"]["policy_verdict"] == "DENY"
    assert decisions["CC-R37-CAPITAL-001"]["policy_verdict"] == "DENY"
    assert receipt["verdict_counts"] == {"ALLOW": 1, "DENY": 2, "HUMAN_APPROVAL": 2}


def test_shadow_mode_never_authorizes_execution() -> None:
    policy = load_policy(POLICY_PATH)
    receipt = evaluate_actions(load_fixture_actions(), policy, now=NOW)
    assert receipt["enforcement_mode"] == "SHADOW_ONLY"
    assert receipt["execution_effects_performed"] == 0
    assert all(row["execution_authorized"] is False for row in receipt["decisions"])
    assert all(row["invariants"]["can_trade"] is False for row in receipt["decisions"])
    assert all(row["invariants"]["capital_permission"] == "DENY" for row in receipt["decisions"])


def test_action_hash_is_stable_across_mapping_order() -> None:
    action_a = {
        "action_id": "HASH-1",
        "actor": "HANRI",
        "operation": "update_projection",
        "target": "dashboard",
        "args": {"b": 2, "a": 1},
        "scope": {"z": True, "x": False},
    }
    action_b = {
        "target": "dashboard",
        "operation": "update_projection",
        "actor": "HANRI",
        "action_id": "HASH-1",
        "scope": {"x": False, "z": True},
        "args": {"a": 1, "b": 2},
    }
    assert action_hash(action_a)[0] == action_hash(action_b)[0]


def test_action_mutation_invalidates_prior_approval() -> None:
    policy = load_policy(POLICY_PATH)
    original = {
        "action_id": "APPROVE-1",
        "actor": "GPT_RUNTIME_CURRENT",
        "operation": "update_dashboard_projection",
        "target": "dashboard",
        "effect_class": "WRITE_REVERSIBLE",
        "args": {"snapshot": "A"},
    }
    decision = evaluate_action(original, policy, now=NOW)
    approval = make_approval_record(
        decision,
        approver="ROBERT",
        issued_at="2026-08-11T20:00:01Z",
        expires_at="2026-08-11T20:10:01Z",
    )
    assert approval_matches(
        decision,
        approval,
        now="2026-08-11T20:05:00Z",
        expected_approver="ROBERT",
    )

    mutated = dict(original)
    mutated["args"] = {"snapshot": "B"}
    mutated_decision = evaluate_action(mutated, policy, now=NOW)
    assert mutated_decision["action_hash"] != decision["action_hash"]
    assert not approval_matches(
        mutated_decision,
        approval,
        now="2026-08-11T20:05:00Z",
        expected_approver="ROBERT",
    )


def test_approval_expiry_and_approver_are_fail_closed() -> None:
    policy = load_policy(POLICY_PATH)
    decision = evaluate_action(load_fixture_actions()[1], policy, now=NOW)
    approval = make_approval_record(
        decision,
        approver="ROBERT",
        issued_at="2026-08-11T20:00:00Z",
        expires_at="2026-08-11T20:01:00Z",
    )
    assert not approval_matches(
        decision,
        approval,
        now="2026-08-11T20:00:30Z",
        expected_approver="NOT_ROBERT",
    )
    assert not approval_matches(
        decision,
        approval,
        now="2026-08-11T20:01:00Z",
        expected_approver="ROBERT",
    )


def test_unknown_effect_fails_closed() -> None:
    policy = load_policy(POLICY_PATH)
    decision = evaluate_action(
        {
            "action_id": "UNKNOWN-1",
            "actor": "HANRI",
            "operation": "quantum_magic",
            "target": "mystery",
            "args": {},
        },
        policy,
        now=NOW,
    )
    assert decision["action"]["effect_class"] == "UNKNOWN"
    assert decision["policy_verdict"] == "DENY"
    assert decision["risk"] == "CRITICAL"


def test_sensitive_args_are_fingerprinted_not_persisted_raw() -> None:
    policy = load_policy(POLICY_PATH)
    raw_secret = "super-secret-value-123"
    decision = evaluate_action(
        {
            "action_id": "SECRET-1",
            "actor": "HANRI",
            "operation": "update_projection",
            "target": "dashboard",
            "effect_class": "WRITE_REVERSIBLE",
            "args": {"api_key": raw_secret},
        },
        policy,
        now=NOW,
    )
    rendered = json.dumps(decision, sort_keys=True)
    assert raw_secret not in rendered
    assert "REDACTED:SENSITIVE_FIELD:api_key" in rendered
    assert decision["action"]["secret_boundary"]["finding_count"] == 1


def test_producer_cannot_downgrade_effect_class() -> None:
    policy = load_policy(POLICY_PATH)
    external = evaluate_action(
        {
            "action_id": "SPOOF-EXTERNAL",
            "actor": "UNTRUSTED_PRODUCER",
            "operation": "send_message",
            "target": "external-recipient",
            "effect_class": "READ_ONLY",
            "args": {"body": "hello"},
        },
        policy,
        now=NOW,
    )
    assert external["action"]["effect_class"] == "WRITE_EXTERNAL"
    assert external["policy_verdict"] == "HUMAN_APPROVAL"

    capital = evaluate_action(
        {
            "action_id": "SPOOF-CAPITAL",
            "actor": "UNTRUSTED_PRODUCER",
            "operation": "place_trade_order",
            "target": "exchange/BTCUSDT",
            "effect_class": "READ_ONLY",
            "args": {"side": "BUY"},
        },
        policy,
        now=NOW,
    )
    assert capital["action"]["effect_class"] == "CAPITAL"
    assert capital["policy_verdict"] == "DENY"
