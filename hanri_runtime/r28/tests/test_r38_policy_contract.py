from __future__ import annotations

import json
from pathlib import Path


def _policy():
    policy_path = Path(__file__).resolve().parents[1] / "config" / "r38.truth-projection-policy.json"
    return json.loads(policy_path.read_text(encoding="utf-8"))


def test_r38_policy_uses_strong_operational_closure_for_runtime_supersession():
    policy = _policy()
    superseded = policy["superseded_by"]
    assert policy["policy_version"] == "38.0.3-live-truth-projection-v1"
    assert superseded["hanri-state"] == "r36-operational-closure"
    assert superseded["r35-runtime-current"] == "r36-operational-closure"
    assert superseded["r35-latest-run"] == "r36-operational-closure"
    assert superseded["r35-human-digest-current"] == "r36-operational-closure"
    assert superseded["r35-accepted-git"] == "r36-accepted-git"


def test_r38_policy_collapses_current_governance_refs_to_phase3():
    superseded = _policy()["superseded_by"]
    assert superseded["r37-phase1-accepted-git"] == "r37-phase3-accepted-git"
    assert superseded["r37-phase1-host-shadow"] == "r37-phase3-effect-receipt"
    assert superseded["r37-phase1-closure"] == "r37-phase3-effect-receipt"
    assert superseded["r37-phase2-accepted-git"] == "r37-phase3-accepted-git"
    assert superseded["r37-phase2-effect-receipt"] == "r37-phase3-effect-receipt"


def test_r38_policy_ttl_covers_mutable_operational_sources():
    ttl = _policy()["source_ttl_seconds"]
    assert ttl["fable-handoff-r64"] == 86400
    assert ttl["r64-package"] == 86400
    assert ttl["return-registry"] == 86400
    assert ttl["decision-governor-01"] == 86400
    assert ttl["operator-d5-current"] == 86400


def test_r38_policy_preserves_no_effect_ceiling():
    policy = _policy()
    assert policy["effect_boundary"] == {
        "read_only": True,
        "writes_performed": 0,
        "external_messages": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }
