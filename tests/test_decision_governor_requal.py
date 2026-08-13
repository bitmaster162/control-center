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


def test_observed_provider_bundle_qualifies_current_with_zero_pending_cards():
    result = qualify(observed())
    assert result["status"] == "PASS"
    assert result["root_bundle_complete"] is True
    assert result["root_errors"] == []
    assert result["root_binding_errors"] == []
    assert result["decision_evidence_errors"] == []
    assert result["decision_count"] == 0
    assert result["promotion_eligible"] is True
    assert result["current_claim_allowed"] is True


def test_closed_d1_closed_d4_and_waiting_d5_are_suppressed():
    result = qualify(observed())
    assert result["suppressions"] == [
        {"id": "D1", "reason": "ALREADY_CLOSED"},
        {"id": "D4", "reason": "ALREADY_CLOSED"},
        {"id": "D5", "reason": "WAITING_REPLY_NO_REPEAT_OUTREACH"},
    ]
    assert result["decisions"] == []
    assert result["effects"]["external_messages"] == 0


def test_missing_provider_root_readback_blocks_current_claim():
    payload = copy.deepcopy(observed())
    payload["roots"]["role_views"]["provider_readback"] = False
    payload["roots"]["role_views"]["freshness"] = "STALE"
    result = qualify(payload)
    assert result["status"] == "BLOCKED_MISSING_CURRENT_ROOTS"
    assert result["promotion_eligible"] is False
    assert result["current_claim_allowed"] is False


def test_pointer_bound_root_hash_mismatch_blocks_current_claim():
    payload = copy.deepcopy(observed())
    payload["pointer_bindings"]["role_index"] = "f" * 64
    result = qualify(payload)
    assert result["status"] == "BLOCKED_ROOT_BINDING_MISMATCH"
    assert "pointer_bindings.role_index:HASH_MISMATCH" in result["root_binding_errors"]
    assert result["current_claim_allowed"] is False


def test_inactive_reseal_marker_blocks_current_claim():
    payload = copy.deepcopy(observed())
    payload["authority"]["pointer_reseal_status"] = "HISTORICAL_PRE_REPAIR_ONLY"
    result = qualify(payload)
    assert result["status"] == "BLOCKED_ROOT_BINDING_MISMATCH"
    assert "authority.pointer_reseal_status:NOT_ACTIVE_RESEALED" in result["root_binding_errors"]


def test_closed_d1_requires_additive_supersession_evidence():
    payload = copy.deepcopy(observed())
    del payload["decision_evidence"]["D1"]
    result = qualify(payload)
    assert result["status"] == "BLOCKED_MISSING_CURRENT_EVIDENCE"
    assert "D1:CLOSED_WITHOUT_SUPERSESSION_EVIDENCE" in result["decision_evidence_errors"]


def test_closed_d4_requires_provider_readback_and_closed_outcome():
    payload = copy.deepcopy(observed())
    payload["decision_evidence"]["D4"]["provider_readback"] = False
    payload["decision_evidence"]["D4"]["outcome"] = "OPEN"
    result = qualify(payload)
    assert result["status"] == "BLOCKED_MISSING_CURRENT_EVIDENCE"
    assert "D4:NO_PROVIDER_READBACK" in result["decision_evidence_errors"]
    assert "D4:EVIDENCE_OUTCOME_NOT_CLOSED" in result["decision_evidence_errors"]


def test_waiting_reply_never_turns_into_repeat_send():
    result = qualify(observed())
    assert all(card["decision_id"] != "D5" for card in result["decisions"])
    assert {"id": "D5", "reason": "WAITING_REPLY_NO_REPEAT_OUTREACH"} in result["suppressions"]
    assert result["effects"]["external_messages"] == 0


def test_waiting_reply_requires_explicit_no_repeat_evidence():
    payload = copy.deepcopy(observed())
    payload["decision_evidence"]["D5"]["repeat_outreach_authorized"] = True
    result = qualify(payload)
    assert result["status"] == "BLOCKED_MISSING_CURRENT_EVIDENCE"
    assert "D5:REPEAT_OUTREACH_MUST_BE_FALSE" in result["decision_evidence_errors"]


def test_reopened_d4_creates_human_only_card():
    payload = copy.deepcopy(observed())
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


def test_safety_ceiling_mismatch_fails_closed():
    payload = copy.deepcopy(observed())
    payload["effect_ceiling"]["can_trade"] = True
    result = qualify(payload)
    assert result["status"] == "FAIL_SAFETY_CEILING"
    assert result["promotion_eligible"] is False
    assert result["current_claim_allowed"] is False
    assert any("can_trade" in item for item in result["safety_errors"])


def test_external_messages_cannot_be_unconditionally_allowed():
    payload = copy.deepcopy(observed())
    payload["effect_ceiling"]["external_messages"] = "ALLOW"
    result = qualify(payload)
    assert result["status"] == "FAIL_SAFETY_CEILING"
    assert "effect_ceiling.external_messages:MUST_REMAIN_HUMAN_GATED" in result["safety_errors"]


def test_each_current_root_requires_durable_sha_and_evidence_ref():
    payload = copy.deepcopy(observed())
    payload["roots"]["role_views"]["sha256"] = None
    payload["roots"]["role_views"]["evidence_ref"] = ""
    result = qualify(payload)
    assert result["status"] == "BLOCKED_MISSING_CURRENT_ROOTS"
    assert "role_views:SHA256_MISSING_OR_INVALID" in result["root_errors"]
    assert "role_views:EVIDENCE_REF_MISSING" in result["root_errors"]


def test_zero_effects_are_constant_even_when_a_card_exists():
    payload = copy.deepcopy(observed())
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
