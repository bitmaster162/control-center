from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/decision_governor_requal.py"
OBSERVED = ROOT / "data/decision_governor.r38.3.observed.json"

spec = importlib.util.spec_from_file_location("decision_governor_requal", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
qualify = module.qualify


def observed() -> dict:
    return json.loads(OBSERVED.read_text(encoding="utf-8"))


def complete_bundle() -> dict:
    payload = observed()
    for index, name in enumerate(("current_pointer", "current_state", "role_index", "role_views"), start=1):
        payload["roots"][name] = {
            "provider_readback": True,
            "freshness": "CURRENT",
            "sha256": f"{index:x}" * 64,
            "evidence_ref": f"provider-root-{name}",
        }
    return payload


def test_observed_bundle_is_blocked_not_fake_current():
    result = qualify(observed())
    assert result["status"] == "BLOCKED_MISSING_CURRENT_ROOTS"
    assert result["root_bundle_complete"] is False
    assert result["promotion_eligible"] is False
    assert result["current_claim_allowed"] is False
    assert result["decision_count"] == 0


def test_closed_d1_closed_d4_and_waiting_d5_are_suppressed():
    result = qualify(observed())
    assert result["suppressions"] == [
        {"id": "D1", "reason": "ALREADY_CLOSED"},
        {"id": "D4", "reason": "ALREADY_CLOSED"},
        {"id": "D5", "reason": "WAITING_REPLY_NO_REPEAT_OUTREACH"},
    ]
    assert result["decisions"] == []
    assert result["effects"]["external_messages"] == 0


def test_complete_current_root_bundle_can_qualify_with_zero_pending_cards():
    result = qualify(complete_bundle())
    assert result["status"] == "PASS"
    assert result["root_bundle_complete"] is True
    assert result["root_errors"] == []
    assert result["decision_count"] == 0
    assert result["promotion_eligible"] is True
    assert result["current_claim_allowed"] is True


def test_reopened_d4_creates_human_only_card():
    payload = complete_bundle()
    d4 = next(item for item in payload["decisions"] if item["id"] == "D4")
    d4["implementation_status"] = "OPEN"
    d4["detail"] = "Contradictory provider evidence reopened P0 closure."
    result = qualify(payload)
    assert result["status"] == "PASS"
    assert result["decision_count"] == 1
    card = result["decisions"][0]
    assert card["decision_id"] == "D4"
    assert card["status"] == "HUMAN_DECISION_REQUIRED"
    assert "AUTO_EXECUTION" in card["blocked_effects"]


def test_waiting_reply_never_turns_into_repeat_send():
    payload = complete_bundle()
    result = qualify(payload)
    assert all(card["decision_id"] != "D5" for card in result["decisions"])
    assert {"id": "D5", "reason": "WAITING_REPLY_NO_REPEAT_OUTREACH"} in result["suppressions"]
    assert result["effects"]["external_messages"] == 0


def test_safety_ceiling_mismatch_fails_closed():
    payload = complete_bundle()
    payload["effect_ceiling"]["can_trade"] = True
    result = qualify(payload)
    assert result["status"] == "FAIL_SAFETY_CEILING"
    assert result["promotion_eligible"] is False
    assert result["current_claim_allowed"] is False
    assert any("can_trade" in item for item in result["safety_errors"])


def test_external_messages_cannot_be_unconditionally_allowed():
    payload = complete_bundle()
    payload["effect_ceiling"]["external_messages"] = "ALLOW"
    result = qualify(payload)
    assert result["status"] == "FAIL_SAFETY_CEILING"
    assert "effect_ceiling.external_messages:MUST_REMAIN_HUMAN_GATED" in result["safety_errors"]


def test_each_current_root_requires_durable_sha_and_evidence_ref():
    payload = complete_bundle()
    payload["roots"]["role_views"]["sha256"] = None
    payload["roots"]["role_views"]["evidence_ref"] = ""
    result = qualify(payload)
    assert result["status"] == "BLOCKED_MISSING_CURRENT_ROOTS"
    assert "role_views:SHA256_MISSING_OR_INVALID" in result["root_errors"]
    assert "role_views:EVIDENCE_REF_MISSING" in result["root_errors"]


def test_zero_effects_are_constant_even_when_a_card_exists():
    payload = complete_bundle()
    d1 = next(item for item in payload["decisions"] if item["id"] == "D1")
    d1["implementation_status"] = "OPEN"
    result = qualify(payload)
    assert result["decision_count"] == 1
    assert result["effects"] == {
        "drive_writes": 0,
        "scheduler_changes": 0,
        "external_messages": 0,
        "external_model_api_calls": 0,
        "source_repository_writes_at_runtime": False,
        "auto_dispatch": False,
        "auto_execution": False,
        "self_application": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }
