from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_NETWORK = ROOT / "data/build_network.r40.example.json"


def load_network() -> dict:
    return json.loads(BUILD_NETWORK.read_text(encoding="utf-8"))


def test_raw4ik_collaboration_is_provider_verified_and_live():
    data = load_network()
    gateway = data["collaboration_gateway"]
    collaborator = gateway["collaborator"]
    assert gateway["status"] == "ACTIVE_COLLABORATOR_VERIFIED"
    assert gateway["collaboration_live"] is True
    assert collaborator["github_login"] == "Raw4ik"
    assert collaborator["github_user_id"] == 123095009
    assert collaborator["identity_verified"] is True
    assert collaborator["repository_permission"] == "write"
    assert collaborator["invite_status"] == "ACCEPTED_PROVIDER_VERIFIED"
    assert collaborator["email_persisted"] is False


def test_raw4ik_has_no_direct_canonical_write():
    data = load_network()
    assert data["canonical"]["friend_write_access"] is False
    lane = data["tradingos_builder_lane"]
    assert lane["raw4ik_direct_source_custody_permission"] == "none"
    assert lane["direct_canonical_write"] is False


def test_tradingos_wp001_is_assigned_without_effect_authority():
    lane = load_network()["tradingos_builder_lane"]
    assert lane["status"] == "ACTIVE_WORK_PACKAGE_ASSIGNED"
    assert lane["first_work_package"] == "WP001_TRADINGOS_DECISION_BRIEF_EVIDENCE"
    assert lane["builder_head_after_wp001_assignment"] == "6e971aa4ec6ad8af888792426a2634ad191a2e0d"
    assert lane["builder_head_current"] == "ee266f15e4621d89284d6ed66fff2c4916f7550e"
    assert lane["acceptance_test_initial_state"] == "EXPECTED_FAIL_UNTIL_RAW4IK_IMPLEMENTATION"
    assert lane["runtime_registration"] is False
    assert lane["deployment"] is False
    assert lane["signals"] is False
    assert lane["orders"] is False
    assert lane["credentials"] is False


def test_collab_promotion_remains_human_gated():
    policy = load_network()["promotion_policy"]
    assert policy["collab_merge_is_canonical_acceptance"] is False
    assert policy["independent_diff_required"] is True
    assert policy["tests_required"] is True
    assert policy["canonical_candidate_branch_required"] is True
    assert policy["canonical_pr_required"] is True
    assert policy["exact_human_merge_gate_required"] is True
    assert policy["auto_merge"] is False
    assert policy["auto_deploy"] is False


def test_effect_ceiling_remains_closed():
    invariants = load_network()["invariants"]
    assert invariants["can_trade"] is False
    assert invariants["capital_permission"] == "DENY"
    assert invariants["self_application"] is False
    assert invariants["tradingos"] == "DO_NOT_TOUCH"
