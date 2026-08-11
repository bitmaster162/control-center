from __future__ import annotations

import copy
import pytest

from hanri.attention_fabric_semantic import HASH_ALGORITHM, run_attention_fabric_semantic
from hanri.continuous_attention_loop import POLICY_VERSION as LEGACY_POLICY_VERSION
from hanri.continuous_attention_loop_semantic import (
    EVIDENCE_HASH_ALGORITHM,
    POLICY_VERSION,
    advance_continuous_attention_loop_v2,
)


def governor_policy():
    return {
        "policy_version": "39.0.0-attention-over-attention-v1",
        "attention_policy": {"min_observations_per_domain": 1, "max_single_domain_share": 0.60},
    }


def fabric_policy():
    return {"policy_version": "39.1.0-attention-fabric-v1"}


def loop_policy():
    return {
        "policy_version": POLICY_VERSION,
        "loop_id": "HANRI_R39_CONTINUOUS_ATTENTION",
        "max_history_tail": 20,
        "no_delta_refresh_threshold": 3,
    }


def coverage_envelope(domain, observed_at, suffix):
    return {
        "envelope_id": f"COVERAGE-{domain}-{suffix}",
        "source_type": "AUDIT_COVERAGE",
        "observed_at": observed_at,
        "producer": "TEST",
        "subject_id": "HANRI" if domain == "SELF" else domain,
        "evidence_refs": [f"SOURCE_SHA256:{suffix * 64}"],
        "payload": {"domain": domain, "audit_state": "AUDITED_NO_MATERIAL_DEFECT_SIGNAL", "source_status": "PASS"},
    }


def bundle(observed_at):
    envelopes = [coverage_envelope(d, observed_at, ch) for d, ch in zip(("SELF", "AGENT", "SYSTEM", "OPERATOR"), "abcd")]
    return {"schema_version": 1, "envelopes": envelopes, "bundle_sha256": "0" * 64}


def fabric_from_bundle(b, generated_at):
    return run_attention_fabric_semantic(
        {"fabric_run_id": f"FABRIC-{generated_at}", "generated_at": generated_at, "envelopes": b["envelopes"]},
        governor_policy=governor_policy(),
        fabric_policy=fabric_policy(),
    )


def advance(b, f, prior, generated_at):
    return advance_continuous_attention_loop_v2(
        producer_bundle=b,
        fabric_result=f,
        prior_state=prior,
        policy=loop_policy(),
        generated_at=generated_at,
    )


def test_semantic_envelope_hash_excludes_observed_at():
    first = fabric_from_bundle(bundle("2026-08-12T06:40:00Z"), "2026-08-12T06:40:00Z")
    second = fabric_from_bundle(bundle("2026-08-12T06:41:00Z"), "2026-08-12T06:41:00Z")
    assert first["envelope_hash_algorithm"] == HASH_ALGORITHM
    assert first["ledger"]["envelope_hashes"] == second["ledger"]["envelope_hashes"]


def test_semantic_envelope_hash_changes_when_payload_changes():
    b1 = bundle("2026-08-12T06:40:00Z")
    b2 = copy.deepcopy(b1)
    b2["envelopes"][2]["payload"]["source_status"] = "DEGRADED"
    f1 = fabric_from_bundle(b1, "2026-08-12T06:40:00Z")
    f2 = fabric_from_bundle(b2, "2026-08-12T06:41:00Z")
    assert f1["ledger"]["envelope_hashes"] != f2["ledger"]["envelope_hashes"]


def test_material_proposal_identity_is_stable_across_timestamp_only_change():
    def material(ts):
        return {
            "schema_version": 1,
            "envelopes": [{
                "envelope_id": "SYSTEM-MATERIAL-1",
                "source_type": "SYSTEM_HEALTH",
                "observed_at": ts,
                "producer": "TEST",
                "subject_id": "SYSTEM-X",
                "evidence_refs": ["SOURCE_SHA256:" + "e" * 64],
                "payload": {"state": "DEGRADED", "freshness": "CURRENT", "severity": "MEDIUM", "summary": "health degraded"},
            }],
        }
    f1 = fabric_from_bundle(material("2026-08-12T06:40:00Z"), "2026-08-12T06:40:00Z")
    f2 = fabric_from_bundle(material("2026-08-12T06:41:00Z"), "2026-08-12T06:41:00Z")
    assert [p["proposal_id"] for p in f1["prioritized_proposals"]] == [p["proposal_id"] for p in f2["prioritized_proposals"]]


def test_two_realistic_wakes_with_only_timestamp_change_are_no_delta():
    b1 = bundle("2026-08-12T06:40:00Z")
    f1 = fabric_from_bundle(b1, "2026-08-12T06:40:00Z")
    first = advance(b1, f1, None, "2026-08-12T06:40:00Z")
    assert first["receipt"]["transition"] == "INITIALIZED"
    assert first["state"]["semantic_cycle_count"] == 1

    b2 = bundle("2026-08-12T06:41:00Z")
    f2 = fabric_from_bundle(b2, "2026-08-12T06:41:00Z")
    second = advance(b2, f2, first["state"], "2026-08-12T06:41:00Z")
    assert second["receipt"]["transition"] == "NO_DELTA"
    assert second["state"]["wake_count"] == 2
    assert second["state"]["semantic_cycle_count"] == 1
    assert second["state"]["no_delta_streak"] == 1
    assert first["receipt"]["evidence_set_sha256"] == second["receipt"]["evidence_set_sha256"]
    assert second["state"]["evidence_hash_algorithm"] == EVIDENCE_HASH_ALGORITHM


def test_payload_change_is_semantic_delta():
    b1 = bundle("2026-08-12T06:40:00Z")
    first = advance(b1, fabric_from_bundle(b1, "2026-08-12T06:40:00Z"), None, "2026-08-12T06:40:00Z")
    b2 = bundle("2026-08-12T06:41:00Z")
    b2["envelopes"][1]["payload"]["source_status"] = "CHANGED"
    second = advance(b2, fabric_from_bundle(b2, "2026-08-12T06:41:00Z"), first["state"], "2026-08-12T06:41:00Z")
    assert second["receipt"]["transition"] == "SEMANTIC_DELTA"
    assert second["state"]["semantic_cycle_count"] == 2


def test_legacy_r39_3_0_state_requires_explicit_migration():
    legacy = {
        "policy_version": LEGACY_POLICY_VERSION,
        "state_sha256": "0" * 64,
    }
    b = bundle("2026-08-12T06:40:00Z")
    f = fabric_from_bundle(b, "2026-08-12T06:40:00Z")
    with pytest.raises(ValueError, match="legacy_or_foreign_state_requires_migration"):
        advance(b, f, legacy, "2026-08-12T06:40:00Z")


def test_v2_preserves_zero_effect_boundary():
    b = bundle("2026-08-12T06:40:00Z")
    out = advance(b, fabric_from_bundle(b, "2026-08-12T06:40:00Z"), None, "2026-08-12T06:40:00Z")
    boundary = out["state"]["effect_boundary"]
    assert boundary["provider_calls"] is False
    assert boundary["scheduler_install"] is False
    assert boundary["self_apply"] is False
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"
    assert out["receipt"]["execution_effects_performed"] == 0
