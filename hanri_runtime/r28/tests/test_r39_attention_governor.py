from __future__ import annotations

import copy
import json
from pathlib import Path

from hanri.attention_governor import canonical_sha256, run_attention_governor

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "config" / "r39.attention-governor.json").read_text(encoding="utf-8"))
FIXTURE = json.loads((ROOT / "data" / "r39_attention_fixture.json").read_text(encoding="utf-8"))


def run(payload=None):
    return run_attention_governor(payload or FIXTURE, policy=POLICY)


def test_audits_all_four_domains_and_meta_attention():
    out = run()
    assert out["meta_audit"]["domain_counts"] == {"SELF": 1, "AGENT": 1, "SYSTEM": 1, "OPERATOR": 1}
    assert out["meta_audit"]["coverage_complete"] is True
    assert out["meta_audit"]["attention_over_attention"] is True


def test_agent_repeated_gap_becomes_skill_candidate_but_not_installed():
    out = run()
    skills = [p for p in out["proposals"] if p["kind"] == "SKILL_CANDIDATE"]
    assert len(skills) == 1
    assert skills[0]["subject_id"] == "CODEX-01"
    assert skills[0]["skill_spec"]["install_authorized"] is False
    assert skills[0]["skill_spec"]["validation_gate"]["requires_isolated_eval"] is True


def test_system_improvement_requires_test_readback_and_rollback():
    out = run()
    item = next(p for p in out["proposals"] if p["kind"] == "SYSTEM_IMPROVEMENT")
    assert item["isolate_test_required"] is True
    assert item["system_change"]["independent_readback_required"] is True
    assert item["system_change"]["rollback_required"] is True


def test_operator_advice_is_advisory_only():
    out = run()
    item = next(p for p in out["proposals"] if p["kind"] == "OPERATOR_ADVICE")
    assert item["operator_advice"]["delivery"] == "ADVISORY_ONLY"
    assert item["operator_advice"]["auto_message"] is False
    assert item["effect_authorized"] is False


def test_self_miss_and_failed_recommendation_create_self_improvements():
    out = run()
    self_items = [p for p in out["proposals"] if p["kind"] == "HANRI_SELF_IMPROVEMENT"]
    assert len(self_items) >= 2
    assert out["meta_audit"]["negative_outcome_count"] == 1


def test_missing_domain_is_detected_as_attention_blind_spot():
    payload = copy.deepcopy(FIXTURE)
    payload["observations"] = [x for x in payload["observations"] if x["domain"] != "OPERATOR"]
    out = run_attention_governor(payload, policy=POLICY)
    assert "OPERATOR" in out["meta_audit"]["blind_spots"]
    assert any(f["signal"] == "ATTENTION_BLIND_SPOT" for f in out["findings"])


def test_attention_imbalance_is_self_audited():
    payload = copy.deepcopy(FIXTURE)
    extra = []
    for n in range(6):
        row = copy.deepcopy(payload["observations"][1])
        row["observation_id"] = f"OBS-AGENT-X{n}"
        row["subject_id"] = f"AGENT-X{n}"
        extra.append(row)
    payload["observations"].extend(extra)
    out = run_attention_governor(payload, policy=POLICY)
    assert out["meta_audit"]["imbalanced_domain"] == "AGENT"
    assert any(f["signal"] == "ATTENTION_IMBALANCE" for f in out["findings"])


def test_effect_boundary_remains_proposal_only():
    out = run()
    assert out["effect_boundary"] == {
        "proposal_only": True,
        "self_apply": False,
        "skill_install": False,
        "system_write": False,
        "operator_message": False,
        "auto_dispatch": False,
        "external_messages": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }
    assert all(p["effect_authorized"] is False for p in out["proposals"])


def test_receipt_is_deterministic_across_observation_order():
    p1 = copy.deepcopy(FIXTURE)
    p2 = copy.deepcopy(FIXTURE)
    p2["observations"] = list(reversed(p2["observations"]))
    o1 = run_attention_governor(p1, policy=POLICY)
    o2 = run_attention_governor(p2, policy=POLICY)
    assert o1 == o2
    digest = o1.pop("receipt_sha256")
    assert digest == canonical_sha256(o1)
