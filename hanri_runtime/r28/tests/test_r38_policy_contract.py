from __future__ import annotations

import json
from pathlib import Path


def test_r38_policy_uses_strong_operational_closure_for_r35_runtime_supersession():
    policy_path = Path(__file__).resolve().parents[1] / "config" / "r38.truth-projection-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    superseded = policy["superseded_by"]
    assert policy["policy_version"] == "38.0.2-live-truth-projection-v1"
    assert superseded["r35-runtime-current"] == "r36-operational-closure"
    assert superseded["r35-latest-run"] == "r36-operational-closure"
    assert superseded["r35-human-digest-current"] == "r36-operational-closure"
    assert superseded["r35-accepted-git"] == "r36-accepted-git"


def test_r38_policy_preserves_no_effect_ceiling():
    policy_path = Path(__file__).resolve().parents[1] / "config" / "r38.truth-projection-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert policy["effect_boundary"] == {
        "read_only": True,
        "writes_performed": 0,
        "external_messages": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }
