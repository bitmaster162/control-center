from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/continuityos_freshness_qual.py"
OBSERVED = ROOT / "data/continuityos.r38.4.observed.json"
QUALIFICATION = ROOT / "data/continuityos.r38.4.qualification.json"
LEDGER = ROOT / "data/freshness.r38.2.example.json"

spec = importlib.util.spec_from_file_location("continuityos_freshness_qual", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
qualify = module.qualify


def observed() -> dict:
    return json.loads(OBSERVED.read_text(encoding="utf-8"))


def test_observed_bundle_matches_committed_qualification():
    expected = json.loads(QUALIFICATION.read_text(encoding="utf-8"))
    assert qualify(observed()) == expected
    assert expected["status"] == "PASS"
    assert expected["freshness"] == "CURRENT"
    assert expected["operational_status"] == "OPERATIONAL"
    assert expected["bounded_property"] == "DURABLE_STATE_RECOVERED_ACROSS_FRESH_PROCESS"


def test_current_master_must_bind_exact_ci_tree():
    payload = copy.deepcopy(observed())
    payload["target"]["tree"] = "f" * 40
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "tree_binding:SOURCE_TREE_MISMATCH" in result["errors"]
    assert "tree_binding:SYNTHETIC_MERGE_TREE_MISMATCH" in result["errors"]
    assert result["current_claim_allowed"] is False


def test_provider_readback_is_required():
    payload = copy.deepcopy(observed())
    payload["target"]["provider_readback"] = False
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "target.provider_readback:REQUIRED" in result["errors"]


def test_both_platform_jobs_must_be_success():
    payload = copy.deepcopy(observed())
    payload["review_evidence"]["windows"]["conclusion"] = "failure"
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "review_evidence.windows.job:NOT_SUCCESS" in result["errors"]


def test_recovery_nodeid_must_be_bound_and_collected():
    payload = copy.deepcopy(observed())
    payload["recovery_contract"]["nodeid_collected"] = False
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "recovery_contract.nodeid:NOT_BOUND" in result["errors"]


def test_behavioral_identity_claim_is_forbidden():
    payload = copy.deepcopy(observed())
    payload["claim_ceiling"]["behavioral_identity_claim"] = True
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "claim_ceiling.behavioral_identity_claim:MUST_BE_FALSE" in result["errors"]


def test_production_runtime_claim_is_forbidden():
    payload = copy.deepcopy(observed())
    payload["claim_ceiling"]["production_runtime_deployment_claim"] = True
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "claim_ceiling.production_runtime_deployment_claim:MUST_BE_FALSE" in result["errors"]


def test_network_or_trading_effect_widening_fails_closed():
    payload = copy.deepcopy(observed())
    payload["recovery_contract"]["network_effect"] = True
    payload["effects"]["can_trade"] = True
    result = qualify(payload)
    assert result["status"] == "BLOCKED"
    assert "recovery_contract.network_effect:MUST_BE_FALSE" in result["errors"]
    assert any(item.startswith("effects.can_trade:") for item in result["errors"])


def test_freshness_ledger_promotes_only_two_surfaces_current():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    current = {item["id"] for item in ledger["surfaces"] if item["freshness"] == "CURRENT"}
    assert current == {"continuity-os", "decision-governor"}
    continuity = next(item for item in ledger["surfaces"] if item["id"] == "continuity-os")
    assert continuity["operational_status"] == "OPERATIONAL"
    assert continuity["current_proof"] is True
    assert continuity["promotion_allowed"] is True
    assert "data/continuityos.r38.4.qualification.json" in continuity["proof_refs"]


def test_effect_ceiling_remains_fail_closed():
    result = qualify(observed())
    assert result["effects"] == {
        "drive_writes": 0,
        "repository_writes_at_runtime": 0,
        "scheduler_changes": 0,
        "external_messages": 0,
        "external_model_calls": 0,
        "trading": False,
        "capital_permission": "DENY",
        "can_trade": False,
        "self_application": False,
    }
