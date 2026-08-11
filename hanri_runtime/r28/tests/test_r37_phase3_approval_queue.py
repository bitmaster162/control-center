from __future__ import annotations

import json
from pathlib import Path

from hanri.approval_queue import approval_command, build_queue_projection, project_queue_item
from hanri.effect_governance import evaluate_action, load_policy, make_approval_record

APP_ROOT = Path(__file__).parents[1]
REPO_ROOT = APP_ROOT.parents[1]
POLICY_PATH = APP_ROOT / "config" / "r37.effect-policy.json"
NOW = "2026-08-11T20:50:00Z"


def projection_decision() -> dict:
    policy = load_policy(POLICY_PATH)
    return evaluate_action(
        {
            "action_id": "QUEUE-1",
            "actor": "HANRI_EFFECT_GATEWAY",
            "operation": "update_dashboard_projection",
            "target": "Control canter/00_DASHBOARD_CURRENT/HANRI_R64_DASHBOARD_CURRENT_R36_FULL_VERIFIED.html",
            "effect_class": "WRITE_REVERSIBLE",
            "args": {
                "snapshot_id": "R64-P4-TEST",
                "before_sha256": "a" * 64,
                "after_sha256": "b" * 64,
                "api_key": "must-never-appear",
            },
            "scope": {
                "stable_roots_modified": False,
                "authority_generation": False,
                "projection_only": True,
            },
            "metadata": {
                "provider": "GOOGLE_DRIVE",
                "provider_target_id": "15GG9ElRV6Ed0gzGkB2b02JumHS58jU2r",
            },
        },
        policy,
        now=NOW,
    )


def test_pending_queue_item_exposes_exact_command_but_not_arbitrary_args() -> None:
    decision = projection_decision()
    item = project_queue_item(
        decision,
        now=NOW,
        approval_expires_at="2026-08-11T21:05:00Z",
    )
    assert item["status"] == "PENDING_APPROVAL"
    assert item["approval_command"] == approval_command(decision["action_hash"])
    rendered = json.dumps(item, sort_keys=True)
    assert "must-never-appear" not in rendered
    assert item["before_sha256"] == "a" * 64
    assert item["after_sha256"] == "b" * 64
    assert item["replay_allowed"] is False


def test_expired_pending_candidate_has_no_replay_command() -> None:
    item = project_queue_item(
        projection_decision(),
        now="2026-08-11T21:06:00Z",
        approval_expires_at="2026-08-11T21:05:00Z",
    )
    assert item["status"] == "EXPIRED"
    assert item["approval_command"] is None


def test_valid_approval_projects_approved_not_executed_without_copy_command() -> None:
    decision = projection_decision()
    approval = make_approval_record(
        decision,
        approver="ROBERT",
        issued_at="2026-08-11T20:50:01Z",
        expires_at="2026-08-11T21:05:00Z",
    )
    item = project_queue_item(decision, approval=approval, now="2026-08-11T20:55:00Z")
    assert item["status"] == "APPROVED_NOT_EXECUTED"
    assert item["approval_command"] is None


def test_verified_execution_suppresses_replay_command_and_binds_receipt() -> None:
    decision = projection_decision()
    receipt = {
        "status": "PASS",
        "effect_rung": "SEMANTIC_EFFECT_VERIFIED",
        "action_hash": decision["action_hash"],
        "receipt_sha256": "c" * 64,
    }
    item = project_queue_item(decision, execution_receipt=receipt, now=NOW)
    assert item["status"] == "EXECUTED_VERIFIED"
    assert item["approval_command"] is None
    assert item["receipt_sha256"] == "c" * 64
    assert item["replay_allowed"] is False


def test_queue_projection_is_read_only_and_capital_denied() -> None:
    item = project_queue_item(
        projection_decision(),
        now=NOW,
        approval_expires_at="2026-08-11T21:05:00Z",
    )
    queue = build_queue_projection([item], generated_at=NOW)
    assert queue["mode"] == "READ_ONLY_PROJECTION"
    assert queue["sovereign_channel"] == "EXACT_HUMAN_GATE"
    assert queue["auto_approval"] is False
    assert queue["auto_execution"] is False
    assert queue["can_trade"] is False
    assert queue["capital_permission"] == "DENY"
    assert queue["summary"]["pending"] == 1


def test_dashboard_ui_is_copy_only_no_execution_transport() -> None:
    index = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    app = (REPO_ROOT / "assets" / "app.js").read_text(encoding="utf-8")
    assert 'data-view="approvals"' in index
    assert 'id="approval-queue-list"' in index
    assert 'data/approval_queue.js' in index
    assert "navigator.clipboard.writeText" in app
    assert "APPROVE_R37_EFFECT:" not in app
    assert "fetch(" not in app
    assert "XMLHttpRequest" not in app
    assert "auto_approval" in app
    assert "auto_execution" in app
