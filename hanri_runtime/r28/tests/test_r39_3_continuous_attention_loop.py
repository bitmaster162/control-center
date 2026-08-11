from __future__ import annotations

import copy

import pytest

from hanri.attention_governor import canonical_sha256
from hanri.continuous_attention_loop import (
    POLICY_VERSION,
    advance_continuous_attention_loop,
)


def policy(**overrides):
    row = {
        "policy_version": POLICY_VERSION,
        "loop_id": "HANRI_R39_CONTINUOUS_ATTENTION",
        "max_history_tail": 20,
        "no_delta_refresh_threshold": 3,
    }
    row.update(overrides)
    return row


def safe_boundary():
    return {
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


def fabric(*, suffix="a", counts=None, blind_spots=None, proposals=None):
    counts = counts or {"SELF": 2, "AGENT": 1, "SYSTEM": 2, "OPERATOR": 1}
    blind_spots = list(blind_spots or [])
    proposals = list(proposals or [])
    rows = [
        {"envelope_id": f"E-{suffix}-1", "sha256": (suffix * 64)[:64], "source_type": "AUDIT_COVERAGE"},
        {"envelope_id": f"E-{suffix}-2", "sha256": (("f" if suffix != "f" else "e") * 64), "source_type": "SYSTEM_HEALTH"},
    ]
    result = {
        "schema_version": 1,
        "fabric_run_id": f"FABRIC-{suffix}",
        "ledger": {
            "envelope_hashes": rows,
            "accepted_envelopes": len(rows),
        },
        "attention_summary": {
            "coverage_complete": not blind_spots,
            "blind_spots": blind_spots,
            "domain_counts": counts,
            "material_domain_counts": {"SELF": 0, "AGENT": 0, "SYSTEM": 0, "OPERATOR": 0},
            "proposal_count": len(proposals),
            "negative_outcome_count": 0,
        },
        "prioritized_proposals": proposals,
        "effect_boundary": safe_boundary(),
    }
    result["fabric_receipt_sha256"] = canonical_sha256(result)
    return result


def producer_bundle(*, suffix="a", outcomes=None):
    envelopes = []
    for index, outcome in enumerate(outcomes or [], start=1):
        envelopes.append({
            "envelope_id": f"OUT-{suffix}-{index}",
            "source_type": "RECOMMENDATION_OUTCOME",
            "observed_at": "2026-08-12T06:30:00+07:00",
            "producer": "TEST",
            "subject_id": "HANRI",
            "evidence_refs": [f"OUTCOME:{suffix}:{index}"],
            "payload": dict(outcome),
        })
    bundle = {
        "schema_version": 1,
        "producer_policy_version": "39.2.2-human-decision-receipts-v1",
        "generated_at": "2026-08-12T06:30:00+07:00",
        "envelopes": envelopes,
    }
    bundle["bundle_sha256"] = canonical_sha256(bundle)
    return bundle


def run(*, f=None, b=None, prior=None, p=None, generated_at="2026-08-12T06:30:00+07:00"):
    return advance_continuous_attention_loop(
        producer_bundle=b or producer_bundle(),
        fabric_result=f or fabric(),
        prior_state=prior,
        policy=p or policy(),
        generated_at=generated_at,
    )


def test_first_cycle_initializes_semantic_memory():
    out = run()
    state = out["state"]
    receipt = out["receipt"]
    assert receipt["transition"] == "INITIALIZED"
    assert receipt["semantic_delta"] is True
    assert state["wake_count"] == 1
    assert state["semantic_cycle_count"] == 1
    assert state["no_delta_streak"] == 0
    assert state["coverage"]["complete"] is True
    assert state["next_attention"]["mode"] == "MAINTAIN_BALANCED_COVERAGE"
    assert set(state["next_attention"]["focus_domains"]) == {"AGENT", "OPERATOR"}
    assert state["state_sha256"] == canonical_sha256({k: v for k, v in state.items() if k != "state_sha256"})


def test_same_evidence_is_no_delta_and_does_not_increment_semantic_cycle():
    first = run()
    second = run(prior=first["state"], generated_at="2026-08-12T06:31:00+07:00")
    assert second["receipt"]["transition"] == "NO_DELTA"
    assert second["receipt"]["semantic_delta"] is False
    assert second["state"]["wake_count"] == 2
    assert second["state"]["semantic_cycle_count"] == 1
    assert second["state"]["no_delta_streak"] == 1
    assert second["state"]["domain_memory"]["AGENT"]["total_covered_semantic_cycles"] == 1


def test_changed_evidence_advances_semantic_cycle():
    first = run()
    second = run(f=fabric(suffix="b"), prior=first["state"], generated_at="2026-08-12T06:31:00+07:00")
    assert second["receipt"]["transition"] == "SEMANTIC_DELTA"
    assert second["state"]["semantic_cycle_count"] == 2
    assert second["state"]["no_delta_streak"] == 0
    assert second["state"]["domain_memory"]["SYSTEM"]["total_covered_semantic_cycles"] == 2


def test_proposal_lifecycle_is_not_duplicated_on_no_delta():
    proposal = {
        "proposal_id": "R39-SKILL-CANDIDATE-1",
        "kind": "SKILL_CANDIDATE",
        "domain": "AGENT",
        "subject_id": "CODEX-01",
        "signal": "SKILL_GAP",
        "authority": "PROPOSAL_ONLY",
    }
    first = run(f=fabric(proposals=[proposal]))
    record1 = first["state"]["proposal_memory"][proposal["proposal_id"]]
    assert record1["seen_semantic_cycles"] == 1
    assert record1["currently_present"] is True

    second = run(f=fabric(proposals=[proposal]), prior=first["state"], generated_at="2026-08-12T06:31:00+07:00")
    record2 = second["state"]["proposal_memory"][proposal["proposal_id"]]
    assert second["receipt"]["transition"] == "NO_DELTA"
    assert record2["seen_semantic_cycles"] == 1
    assert record2["currently_present"] is True


def test_missing_proposal_is_not_claimed_as_verified_improvement():
    proposal = {
        "proposal_id": "R39-SYSTEM-1",
        "kind": "SYSTEM_IMPROVEMENT",
        "domain": "SYSTEM",
        "subject_id": "CONTINUITY-OS",
        "signal": "QUALITY_DRIFT",
    }
    first = run(f=fabric(proposals=[proposal]))
    second = run(f=fabric(suffix="b", proposals=[]), prior=first["state"], generated_at="2026-08-12T06:31:00+07:00")
    record = second["state"]["proposal_memory"][proposal["proposal_id"]]
    assert record["currently_present"] is False
    assert record["status"] == "NOT_CURRENTLY_OBSERVED"
    assert record["status"] != "VERIFIED_IMPROVED"


def test_negative_outcome_persists_self_review_until_superseded():
    rid = "R39-SYSTEM-NEGATIVE-1"
    first = run(
        f=fabric(suffix="a"),
        b=producer_bundle(outcomes=[{"recommendation_id": rid, "status": "REGRESSED"}]),
    )
    assert first["state"]["unresolved_negative_outcomes"] == [rid]
    assert first["state"]["next_attention"]["mode"] == "SELF_REVIEW_REQUIRED"

    # Changed evidence without a newer outcome keeps the negative outcome memory.
    second = run(
        f=fabric(suffix="b"),
        b=producer_bundle(suffix="b"),
        prior=first["state"],
        generated_at="2026-08-12T06:31:00+07:00",
    )
    assert second["state"]["unresolved_negative_outcomes"] == [rid]
    assert second["state"]["next_attention"]["mode"] == "SELF_REVIEW_REQUIRED"

    third = run(
        f=fabric(suffix="c"),
        b=producer_bundle(suffix="c", outcomes=[{"recommendation_id": rid, "status": "VERIFIED_IMPROVED"}]),
        prior=second["state"],
        generated_at="2026-08-12T06:32:00+07:00",
    )
    assert third["state"]["unresolved_negative_outcomes"] == []
    assert third["state"]["outcome_memory"][rid]["status"] == "VERIFIED_IMPROVED"


def test_coverage_loss_becomes_next_attention_repair_not_execution():
    counts = {"SELF": 2, "AGENT": 0, "SYSTEM": 2, "OPERATOR": 1}
    out = run(f=fabric(counts=counts, blind_spots=["AGENT"]))
    assert out["state"]["next_attention"]["mode"] == "COVERAGE_REPAIR_REQUIRED"
    assert out["state"]["next_attention"]["focus_domains"] == ["AGENT"]
    assert out["receipt"]["effect_boundary"]["auto_dispatch"] is False
    assert out["receipt"]["execution_effects_performed"] == 0


def test_repeated_no_delta_wakes_shift_to_evidence_refresh_focus():
    state = run()["state"]
    for minute in (31, 32, 33):
        state = run(prior=state, generated_at=f"2026-08-12T06:{minute}:00+07:00")["state"]
    assert state["semantic_cycle_count"] == 1
    assert state["no_delta_streak"] == 3
    assert state["next_attention"]["mode"] == "EVIDENCE_REFRESH_FOCUS"
    assert set(state["next_attention"]["focus_domains"]) == {"AGENT", "OPERATOR"}


def test_tampered_prior_state_fails_closed():
    first = run()["state"]
    tampered = copy.deepcopy(first)
    tampered["wake_count"] = 999
    with pytest.raises(ValueError, match="prior state SHA mismatch"):
        run(prior=tampered)


def test_unsafe_fabric_fails_closed():
    bad = fabric()
    bad["effect_boundary"]["can_trade"] = True
    with pytest.raises(ValueError, match="can_trade must remain false"):
        run(f=bad)


def test_history_tail_is_bounded():
    p = policy(max_history_tail=2)
    state = run(p=p)["state"]
    state = run(f=fabric(suffix="b"), prior=state, p=p, generated_at="2026-08-12T06:31:00+07:00")["state"]
    state = run(f=fabric(suffix="c"), prior=state, p=p, generated_at="2026-08-12T06:32:00+07:00")["state"]
    assert len(state["history_tail"]) == 2
    assert [row["semantic_cycle"] for row in state["history_tail"]] == [2, 3]


def test_r39_3_effect_boundary_is_local_state_only():
    out = run()
    boundary = out["state"]["effect_boundary"]
    assert boundary["proposal_only"] is True
    assert boundary["local_state_write_only"] is True
    assert boundary["provider_calls"] is False
    assert boundary["scheduler_install"] is False
    assert boundary["human_decision_execution"] is False
    assert boundary["self_apply"] is False
    assert boundary["skill_install"] is False
    assert boundary["system_write"] is False
    assert boundary["operator_message"] is False
    assert boundary["auto_dispatch"] is False
    assert boundary["external_messages"] is False
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"
