from __future__ import annotations

from hanri.live_truth_projection import reconcile_truth_projection


def _base_snapshot():
    return {
        "meta": {
            "generated_at": "2026-08-12T03:00:00+07:00",
            "freshness": {"mode": "SNAPSHOT", "state": "CURRENT", "as_of": "2026-08-12T03:00:00+07:00"},
        },
        "sources": [
            {
                "source_id": "legacy-old",
                "evidence_state": "RECEIPTED",
                "freshness": "SUPERSEDED",
                "as_of": "2026-08-10T00:00:00Z",
                "notes": "legacy marker",
            },
            {
                "source_id": "stale-source",
                "evidence_state": "RECEIPTED",
                "freshness": "CURRENT",
                "as_of": "2026-08-10T00:00:00Z",
                "notes": "operational evidence",
            },
        ],
        "kpis": [{"label": "x", "evidence_refs": ["stale-source"], "freshness": "CURRENT"}],
        "current_actions": [{"id": "A1", "evidence_refs": ["stale-source"]}],
        "systems": [],
        "agents": [],
        "decisions": [{"id": "D1", "evidence_refs": ["stale-source"]}],
        "events": [],
    }


def _policy():
    return {
        "policy_version": "38.0.2-live-truth-projection-v1",
        "superseded_by": {},
        "source_ttl_seconds": {"stale-source": 3600},
        "freshness_basis": {"stale-source": "test TTL"},
    }


def test_degraded_receipt_maps_to_schema_valid_stale_meta_state():
    bundle = reconcile_truth_projection(
        _base_snapshot(), policy=_policy(), generated_at="2026-08-12T04:30:00+07:00"
    )
    assert bundle["receipt"]["projection_health"] == "DEGRADED"
    assert bundle["receipt"]["snapshot_freshness_state"] == "STALE"
    assert bundle["snapshot"]["meta"]["freshness"]["state"] == "STALE"


def test_current_actions_and_decisions_do_not_gain_schema_forbidden_freshness_field():
    bundle = reconcile_truth_projection(
        _base_snapshot(), policy=_policy(), generated_at="2026-08-12T04:30:00+07:00"
    )
    assert "freshness" not in bundle["snapshot"]["current_actions"][0]
    assert "freshness" not in bundle["snapshot"]["decisions"][0]
    assert bundle["snapshot"]["kpis"][0]["freshness"] == "STALE"


def test_legacy_superseded_freshness_is_normalized_to_schema_valid_stale():
    bundle = reconcile_truth_projection(
        _base_snapshot(), policy=_policy(), generated_at="2026-08-12T04:30:00+07:00"
    )
    legacy = bundle["snapshot"]["sources"][0]
    assert legacy["freshness"] == "STALE"
    assert "LEGACY_FRESHNESS_NORMALIZED:SUPERSEDED->STALE" in legacy["notes"]
    assert bundle["receipt"]["legacy_freshness_normalization"]["legacy-old"] == {
        "from": "SUPERSEDED",
        "to": "STALE",
    }
