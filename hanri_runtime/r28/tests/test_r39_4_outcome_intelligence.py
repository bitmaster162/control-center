import pytest

from hanri.attention_governor import canonical_sha256
from hanri.outcome_intelligence import POLICY_VERSION, run_outcome_intelligence


def safe_boundary():
    return {"proposal_only": True, "local_state_write_only": True, "provider_calls": False, "scheduler_install": False, "human_decision_execution": False, "self_apply": False, "skill_install": False, "system_write": False, "operator_message": False, "auto_dispatch": False, "external_messages": False, "can_trade": False, "capital_permission": "DENY"}


def loop_state(proposals):
    state = {"schema_version": 1, "policy_version": "39.3.1-continuous-attention-loop-v2", "evidence_hash_algorithm": "SEMANTIC_ENVELOPE_V2", "semantic_cycle_count": 7, "proposal_memory": proposals, "effect_boundary": safe_boundary()}
    state["state_sha256"] = canonical_sha256(state)
    return state


def proposal(domain="AGENT", kind="SKILL_CANDIDATE", subject="Codex", signal="SKILL_GAP"):
    return {"domain": domain, "kind": kind, "subject_id": subject, "signal": signal, "proposal_fingerprint": "a" * 64}


def bundle(*rows):
    envs = []
    for i, row in enumerate(rows, start=1):
        envs.append({"envelope_id": f"OUT-{i}", "source_type": "RECOMMENDATION_OUTCOME", "producer": "TEST", "observed_at": f"2026-08-12T00:0{i}:00Z", "subject_id": "HANRI", "evidence_refs": row.get("evidence_refs", []), "payload": {"recommendation_id": row["recommendation_id"], "status": row["status"]}})
    return {"envelopes": envs, "bundle_sha256": "b" * 64}


def policy():
    return {"policy_version": POLICY_VERSION, "max_history_tail": 20, "reinforcement_min_verified_improved": 2, "outcome_debt_min_tracked": 2, "min_outcome_coverage_rate": 0.5}


def run(loop, b, prior=None):
    return run_outcome_intelligence(loop_state=loop, producer_bundle=b, prior_state=prior, policy=policy(), generated_at="2026-08-12T01:00:00Z")


def test_no_outcomes_never_infers_improvement_and_exposes_outcome_debt():
    loop = loop_state({"P1": proposal(), "P2": proposal(domain="SYSTEM", kind="SYSTEM_IMPROVEMENT")})
    result = run(loop, bundle())
    m = result["receipt"]["metrics"]
    assert m["verified_improved"] == 0
    assert m["evaluated_recommendations"] == 0
    assert m["unknown_or_unevaluated"] == 2
    assert m["outcome_coverage_rate"] == 0.0
    assert result["receipt"]["next_attention"]["mode"] == "OUTCOME_EVIDENCE_GAP"
    assert "OUTCOME_EVIDENCE_COLLECTION" in result["receipt"]["learning_candidate_types"]


def test_verified_improved_requires_explicit_evidence_and_counts_known_recommendation():
    loop = loop_state({"P1": proposal()})
    with pytest.raises(ValueError, match="requires explicit evidence_refs"):
        run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED"}))
    result = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["EVAL:case-1"]}))
    m = result["receipt"]["metrics"]
    assert m["verified_improved"] == 1
    assert m["effectiveness_rate"] == 1.0
    assert m["adverse_rate"] == 0.0


@pytest.mark.parametrize("status", ["VERIFIED_NO_EFFECT", "REGRESSED"])
def test_negative_outcome_creates_self_review_and_domain_review(status):
    loop = loop_state({"P1": proposal(domain="AGENT", kind="SKILL_CANDIDATE")})
    result = run(loop, bundle({"recommendation_id": "P1", "status": status, "evidence_refs": ["EVAL:negative"]}))
    types = set(result["receipt"]["learning_candidate_types"])
    assert "HANRI_RECOMMENDATION_RULE_REVIEW" in types
    assert "SKILL_CANDIDATE_REVIEW" in types
    assert result["receipt"]["next_attention"]["mode"] == "OUTCOME_FAILURE_REVIEW"
    assert result["receipt"]["next_attention"]["focus_domains"] == ["SELF", "AGENT"]


def test_orphan_outcome_is_not_counted_as_effectiveness():
    loop = loop_state({"P1": proposal()})
    result = run(loop, bundle({"recommendation_id": "UNKNOWN-P", "status": "VERIFIED_IMPROVED", "evidence_refs": ["EVAL:orphan"]}))
    m = result["receipt"]["metrics"]
    assert m["orphan_outcomes"] == 1
    assert m["evaluated_recommendations"] == 0
    assert m["effectiveness_rate"] is None


def test_conflicting_current_outcomes_fail_closed():
    loop = loop_state({"P1": proposal()})
    with pytest.raises(ValueError, match="conflicting current outcomes"):
        run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:1"]}, {"recommendation_id": "P1", "status": "REGRESSED", "evidence_refs": ["E:2"]}))


def test_repeated_identical_outcome_does_not_duplicate_status_transition():
    loop = loop_state({"P1": proposal()})
    first = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:1"]}))
    second = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:1"]}), prior=first["state"])
    assert first["receipt"]["new_status_transition_count"] == 1
    assert second["receipt"]["new_status_transition_count"] == 0
    assert second["state"]["outcome_records"]["P1"]["status_transition_count"] == 1


def test_improved_then_regressed_updates_current_metrics_and_self_review():
    loop = loop_state({"P1": proposal(domain="SYSTEM", kind="SYSTEM_IMPROVEMENT")})
    first = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:before"]}))
    second = run(loop, bundle({"recommendation_id": "P1", "status": "REGRESSED", "evidence_refs": ["E:after"]}), prior=first["state"])
    m = second["receipt"]["metrics"]
    assert m["verified_improved"] == 0
    assert m["regressed"] == 1
    assert second["receipt"]["status_transitions"][0]["from_status"] == "VERIFIED_IMPROVED"
    assert second["receipt"]["status_transitions"][0]["to_status"] == "REGRESSED"
    assert "SYSTEM_IMPROVEMENT_REVIEW" in second["receipt"]["learning_candidate_types"]


def test_reinforcement_requires_two_positive_and_no_negative_in_same_domain_kind():
    loop = loop_state({"P1": proposal(), "P2": proposal(subject="Claude")})
    one = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:1"]}))
    assert "REINFORCEMENT_REVIEW" not in one["receipt"]["learning_candidate_types"]
    two = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:1"]}, {"recommendation_id": "P2", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:2"]}), prior=one["state"])
    assert "REINFORCEMENT_REVIEW" in two["receipt"]["learning_candidate_types"]
    assert two["receipt"]["next_attention"]["mode"] == "REINFORCEMENT_REVIEW"


def test_tampered_loop_state_fails_closed():
    loop = loop_state({"P1": proposal()})
    loop["semantic_cycle_count"] = 999
    with pytest.raises(ValueError, match="loop state SHA mismatch"):
        run(loop, bundle())


def test_effect_boundary_remains_zero_effect():
    loop = loop_state({"P1": proposal()})
    result = run(loop, bundle({"recommendation_id": "P1", "status": "VERIFIED_IMPROVED", "evidence_refs": ["E:1"]}))
    boundary = result["receipt"]["effect_boundary"]
    assert result["receipt"]["execution_effects_performed"] == 0
    for key in ("provider_calls", "scheduler_install", "scheduler_modify", "self_apply", "skill_install", "system_write", "operator_message", "auto_dispatch", "external_messages", "can_trade"):
        assert boundary[key] is False
    assert boundary["capital_permission"] == "DENY"
