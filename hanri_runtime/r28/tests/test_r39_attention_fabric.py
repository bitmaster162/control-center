from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from hanri.attention_fabric import load_envelopes_from_directory, run_attention_fabric

ROOT = Path(__file__).resolve().parents[1]
GOVERNOR_POLICY = json.loads((ROOT / "config" / "r39.attention-governor.json").read_text(encoding="utf-8"))
FABRIC_POLICY = json.loads((ROOT / "config" / "r39.1.attention-fabric.json").read_text(encoding="utf-8"))


def envelope(envelope_id, source_type, subject_id, payload, evidence_refs=None, observed_at="2026-08-12T05:20:00+07:00"):
    return {
        "envelope_id": envelope_id,
        "source_type": source_type,
        "subject_id": subject_id,
        "producer": "test",
        "observed_at": observed_at,
        "evidence_refs": evidence_refs or [f"EVIDENCE:{envelope_id}"],
        "payload": payload,
    }


def full_payload():
    return {
        "fabric_run_id": "R39.1-TEST-001",
        "generated_at": "2026-08-12T05:21:00+07:00",
        "envelopes": [
            envelope("self-1", "HANRI_SELF_TRACE", "HANRI", {
                "missed_defect": True,
                "severity": "HIGH",
                "summary": "HANRI missed a host-wrapper defect before operator execution.",
                "proposed_change": "audit host wrapper behavior before release",
            }),
            envelope("agent-1", "AGENT_RETURN", "CODEX-01", {
                "status": "FAILED",
                "skill_gap": True,
                "repeated_count": 3,
                "severity": "HIGH",
                "summary": "Agent repeated current-truth verification errors.",
                "proposed_change": "create evidence-first verification skill",
            }),
            envelope("system-1", "SYSTEM_HEALTH", "CONTROL_CENTER_DASHBOARD", {
                "state": "DEGRADED",
                "freshness": "STALE",
                "severity": "HIGH",
                "summary": "Dashboard projection contains stale evidence.",
                "proposed_change": "regenerate from verified current sources",
            }),
            envelope("operator-1", "OPERATOR_EVENT", "ROBERT", {
                "repeated_count": 4,
                "severity": "MEDIUM",
                "summary": "Operator repeatedly had to challenge stale system truth.",
                "proposed_change": "surface proactive attention digest",
            }),
            envelope("outcome-1", "RECOMMENDATION_OUTCOME", "HANRI", {
                "recommendation_id": "REC-OLD-1",
                "status": "VERIFIED_NO_EFFECT",
            }, evidence_refs=["OUTCOME:REC-OLD-1"]),
        ],
    }


def test_real_envelopes_cover_all_domains_and_feed_governor():
    out = run_attention_fabric(full_payload(), governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    assert out["mode"] == "REAL_ENVELOPE_INGESTION"
    assert out["ledger"]["accepted_envelopes"] == 5
    assert out["ledger"]["observation_count"] == 4
    assert out["ledger"]["outcome_count"] == 1
    assert out["attention_summary"]["coverage_complete"] is True
    assert out["attention_summary"]["domain_counts"] == {"SELF": 1, "AGENT": 1, "SYSTEM": 1, "OPERATOR": 1}


def test_agent_return_becomes_skill_candidate_and_priority_is_deterministic():
    out = run_attention_fabric(full_payload(), governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    skills = [p for p in out["prioritized_proposals"] if p["kind"] == "SKILL_CANDIDATE"]
    assert len(skills) == 1
    assert skills[0]["skill_spec"]["install_authorized"] is False
    scores = [p["priority"]["score"] for p in out["prioritized_proposals"]]
    assert scores == sorted(scores, reverse=True)
    assert [p["priority"]["rank"] for p in out["prioritized_proposals"]] == list(range(1, len(scores) + 1))


def test_same_id_same_hash_dedupes_but_conflict_fails_closed():
    payload = full_payload()
    payload["envelopes"].append(copy.deepcopy(payload["envelopes"][0]))
    out = run_attention_fabric(payload, governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    assert out["ledger"]["duplicate_envelopes"] == 1
    assert out["ledger"]["accepted_envelopes"] == 5

    conflict = full_payload()
    bad = copy.deepcopy(conflict["envelopes"][0])
    bad["payload"]["summary"] = "different bytes under same envelope id"
    conflict["envelopes"].append(bad)
    with pytest.raises(ValueError, match="conflicting envelope_id"):
        run_attention_fabric(conflict, governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)


def test_missing_domain_stays_visible_as_blind_spot_not_silently_green():
    payload = full_payload()
    payload["envelopes"] = [e for e in payload["envelopes"] if e["source_type"] != "OPERATOR_EVENT"]
    out = run_attention_fabric(payload, governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    assert out["attention_summary"]["coverage_complete"] is False
    assert "OPERATOR" in out["attention_summary"]["blind_spots"]


def test_effect_boundary_remains_zero_effect():
    out = run_attention_fabric(full_payload(), governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    assert out["effect_boundary"]["proposal_only"] is True
    assert out["effect_boundary"]["self_apply"] is False
    assert out["effect_boundary"]["skill_install"] is False
    assert out["effect_boundary"]["system_write"] is False
    assert out["effect_boundary"]["operator_message"] is False
    assert out["effect_boundary"]["auto_dispatch"] is False
    assert out["effect_boundary"]["can_trade"] is False
    assert out["effect_boundary"]["capital_permission"] == "DENY"


def test_directory_loader_accepts_single_list_and_bundle(tmp_path):
    e1 = envelope("a", "HANRI_SELF_TRACE", "HANRI", {"summary": "self", "signal": "SELF_REVIEW"})
    e2 = envelope("b", "SYSTEM_HEALTH", "SYS", {"summary": "sys", "state": "DEGRADED"})
    e3 = envelope("c", "OPERATOR_EVENT", "ROBERT", {"summary": "op", "repeated_count": 2})
    (tmp_path / "01.json").write_text(json.dumps(e1), encoding="utf-8")
    (tmp_path / "02.json").write_text(json.dumps([e2]), encoding="utf-8")
    (tmp_path / "03.json").write_text(json.dumps({"envelopes": [e3]}), encoding="utf-8")
    loaded = load_envelopes_from_directory(tmp_path)
    assert [x["envelope_id"] for x in loaded] == ["a", "b", "c"]


def test_receipt_is_order_invariant():
    a = full_payload()
    b = full_payload()
    b["envelopes"] = list(reversed(b["envelopes"]))
    oa = run_attention_fabric(a, governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    ob = run_attention_fabric(b, governor_policy=GOVERNOR_POLICY, fabric_policy=FABRIC_POLICY)
    assert oa == ob
