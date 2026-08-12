from hanri.attention_governor import canonical_sha256
from hanri.outcome_intelligence_semantic import POLICY_VERSION, run_outcome_intelligence_v2


def safe_boundary():
    return {
        "proposal_only": True,
        "local_state_write_only": True,
        "provider_calls": False,
        "scheduler_install": False,
        "scheduler_modify": False,
        "human_decision_execution": False,
        "self_apply": False,
        "skill_install": False,
        "system_write": False,
        "operator_message": False,
        "auto_dispatch": False,
        "external_messages": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }


def loop_state(proposals):
    state = {
        "schema_version": 1,
        "policy_version": "39.3.1-continuous-attention-loop-v2",
        "evidence_hash_algorithm": "SEMANTIC_ENVELOPE_V2",
        "semantic_cycle_count": 9,
        "proposal_memory": proposals,
        "effect_boundary": safe_boundary(),
    }
    state["state_sha256"] = canonical_sha256(state)
    return state


def proposal(domain="AGENT", kind="SKILL_CANDIDATE"):
    return {
        "domain": domain,
        "kind": kind,
        "subject_id": "Codex",
        "signal": "SKILL_GAP",
        "proposal_fingerprint": "a" * 64,
    }


def policy():
    return {
        "policy_version": POLICY_VERSION,
        "max_history_tail": 20,
        "reinforcement_min_verified_improved": 2,
        "outcome_debt_min_tracked": 2,
        "min_outcome_coverage_rate": 0.5,
        "effect_boundary": safe_boundary(),
    }


def run(loop, prior=None):
    return run_outcome_intelligence_v2(
        loop_state=loop,
        producer_bundle={"envelopes": [], "bundle_sha256": "b" * 64},
        prior_state=prior,
        policy=policy(),
        generated_at="2026-08-12T01:20:00Z",
    )


def test_zero_tracked_recommendations_is_not_applicable_not_full_coverage():
    result = run(loop_state({}))
    metrics = result["receipt"]["metrics"]
    assert metrics["tracked_recommendations"] == 0
    assert metrics["evaluated_recommendations"] == 0
    assert metrics["outcome_coverage_rate"] is None
    assert metrics["outcome_coverage_applicable"] is False
    assert metrics["outcome_coverage_status"] == "NOT_APPLICABLE"
    assert result["receipt"]["next_attention"]["mode"] == "OUTCOME_MONITORING"


def test_zero_tracked_domain_is_not_applicable():
    result = run(loop_state({"P1": proposal(domain="AGENT")}))
    metrics = result["receipt"]["metrics"]
    assert metrics["outcome_coverage_rate"] == 0.0
    assert metrics["outcome_coverage_applicable"] is True
    assert metrics["per_domain"]["AGENT"]["outcome_coverage_rate"] == 0.0
    assert metrics["per_domain"]["AGENT"]["outcome_coverage_applicable"] is True
    for domain in ("SELF", "SYSTEM", "OPERATOR"):
        assert metrics["per_domain"][domain]["outcome_coverage_rate"] is None
        assert metrics["per_domain"][domain]["outcome_coverage_applicable"] is False


def test_history_does_not_reintroduce_vacuous_full_coverage():
    first = run(loop_state({}))
    row = first["state"]["history_tail"][-1]
    assert row["outcome_coverage_rate"] is None
    assert row["outcome_coverage_applicable"] is False
    assert row["outcome_coverage_status"] == "NOT_APPLICABLE"


def test_v2_state_round_trip_preserves_metric_semantics():
    loop = loop_state({})
    first = run(loop)
    second = run(loop, prior=first["state"])
    assert second["state"]["policy_version"] == POLICY_VERSION
    assert second["receipt"]["metrics"]["outcome_coverage_rate"] is None
    assert second["receipt"]["metric_semantics"]["zero_denominator"] == "NOT_APPLICABLE"


def test_zero_effect_boundary_remains_closed():
    result = run(loop_state({}))
    boundary = result["receipt"]["effect_boundary"]
    assert result["receipt"]["execution_effects_performed"] == 0
    for key in (
        "provider_calls",
        "scheduler_install",
        "scheduler_modify",
        "self_apply",
        "skill_install",
        "system_write",
        "operator_message",
        "auto_dispatch",
        "external_messages",
        "can_trade",
    ):
        assert boundary[key] is False
    assert boundary["capital_permission"] == "DENY"
