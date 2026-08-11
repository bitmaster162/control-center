from __future__ import annotations

import copy

import pytest

from hanri.live_truth_projection import canonical_sha256, reconcile_truth_projection


def _snapshot():
    return {
        "meta": {
            "generated_at": "2026-08-12T03:00:00+07:00",
            "freshness": {"mode": "SNAPSHOT", "state": "CURRENT", "as_of": "2026-08-12T03:00:00+07:00"},
            "can_trade": False,
            "capital_permission": "DENY",
        },
        "sources": [
            {
                "source_id": "r35-runtime",
                "evidence_state": "HASH_VERIFIED",
                "freshness": "CURRENT",
                "as_of": "2026-08-11T18:28:45Z",
                "notes": "old runtime",
            },
            {
                "source_id": "r36-runtime",
                "evidence_state": "HASH_VERIFIED",
                "freshness": "CURRENT",
                "as_of": "2026-08-11T19:42:12Z",
                "notes": "accepted runtime",
            },
            {
                "source_id": "old-agent-handoff",
                "evidence_state": "SOURCE_BACKED",
                "freshness": "CURRENT",
                "as_of": "2026-08-09T00:00:00Z",
                "notes": "operational status handoff",
            },
        ],
        "kpis": [{"label": "runtime", "evidence_refs": ["r35-runtime"], "freshness": "CURRENT"}],
        "current_actions": [],
        "systems": [],
        "agents": [{"slot": "old", "evidence_refs": ["old-agent-handoff"], "freshness": "CURRENT"}],
        "decisions": [],
        "events": [{"event_id": "historical-r35", "evidence_refs": ["r35-runtime"], "freshness": "CURRENT"}],
    }


def _policy():
    return {
        "policy_version": "38.0.0-live-truth-projection-v1",
        "superseded_by": {"r35-runtime": "r36-runtime"},
        "source_ttl_seconds": {"old-agent-handoff": 86400},
        "freshness_basis": {
            "r35-runtime": "R36 accepted/live supersedes R35 current-runtime claim",
            "old-agent-handoff": "Operational agent status requires confirmation within 24h",
        },
    }


def test_superseded_current_ref_rewrites_to_accepted_successor():
    bundle = reconcile_truth_projection(
        _snapshot(), policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    snap = bundle["snapshot"]
    assert snap["sources"][0]["freshness"] == "STALE"
    assert "SUPERSEDED_BY:r36-runtime" in snap["sources"][0]["notes"]
    assert snap["kpis"][0]["evidence_refs"] == ["r36-runtime"]
    assert snap["kpis"][0]["freshness"] == "CURRENT"
    assert bundle["receipt"]["applied_supersession"] == {"r35-runtime": "r36-runtime"}


def test_historical_event_is_not_rewritten():
    bundle = reconcile_truth_projection(
        _snapshot(), policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    assert bundle["snapshot"]["events"][0]["evidence_refs"] == ["r35-runtime"]


def test_source_specific_ttl_degrades_current_state_claim():
    bundle = reconcile_truth_projection(
        _snapshot(), policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    snap = bundle["snapshot"]
    handoff = next(x for x in snap["sources"] if x["source_id"] == "old-agent-handoff")
    assert handoff["freshness"] == "STALE"
    assert snap["agents"][0]["freshness"] == "STALE"
    assert bundle["receipt"]["projection_health"] == "DEGRADED"


def test_no_effect_boundary_is_hardcoded():
    bundle = reconcile_truth_projection(
        _snapshot(), policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    assert bundle["receipt"]["effect_boundary"] == {
        "read_only": True,
        "writes_performed": 0,
        "external_messages": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }


def test_supersession_requires_strong_successor_evidence():
    snap = _snapshot()
    snap["sources"][1]["evidence_state"] = "SOURCE_BACKED"
    bundle = reconcile_truth_projection(
        snap, policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    assert bundle["snapshot"]["sources"][0]["freshness"] == "CURRENT"
    assert bundle["snapshot"]["kpis"][0]["evidence_refs"] == ["r35-runtime"]


def test_supersession_cycle_fails_closed():
    policy = _policy()
    policy["superseded_by"]["r36-runtime"] = "r35-runtime"
    with pytest.raises(ValueError, match="supersession cycle"):
        reconcile_truth_projection(
            _snapshot(), policy=policy, generated_at="2026-08-12T04:15:00+07:00"
        )


def test_deterministic_for_same_inputs_and_generated_at():
    a = reconcile_truth_projection(
        _snapshot(), policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    b = reconcile_truth_projection(
        _snapshot(), policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    assert a == b
    assert canonical_sha256(a) == canonical_sha256(b)


def test_input_is_not_mutated():
    snap = _snapshot()
    original = copy.deepcopy(snap)
    reconcile_truth_projection(
        snap, policy=_policy(), generated_at="2026-08-12T04:15:00+07:00"
    )
    assert snap == original
