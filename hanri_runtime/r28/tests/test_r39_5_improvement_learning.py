from __future__ import annotations

import copy

import pytest

from hanri.attention_governor import DOMAINS, canonical_sha256
from hanri.improvement_learning import POLICY_VERSION, run_improvement_learning


SAFE = {
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

POLICY = {
    "schema_version": 1,
    "policy_version": POLICY_VERSION,
    "min_evaluated_for_pattern": 2,
    "supported_evidence_min": 4,
    "reinforcement_min_verified_improved": 2,
    "evidence_observation_cap": 12,
    "outcome_debt_weight": 30.0,
    "pattern_history_tail": 10,
    "max_history_tail": 20,
    "receipt_top_n": 5,
    "priority_weights": {
        "regressed": 100.0,
        "verified_no_effect": 60.0,
        "verified_improved": 10.0,
        "evidence_observation": 0.25,
        "recurring_negative_cycle": 4.0,
        "transition_instability_penalty": 1.0,
    },
    "effect_boundary": SAFE,
}


def _record(domain: str, kind: str, status: str, *, obs: int = 1, transitions: int = 1) -> dict:
    return {
        "domain": domain,
        "kind": kind,
        "subject_id": f"{domain.lower()}-1",
        "signal": "test",
        "current_status": status,
        "evaluated": status in {"VERIFIED_IMPROVED", "VERIFIED_NO_EFFECT", "REGRESSED"},
        "negative": status in {"VERIFIED_NO_EFFECT", "REGRESSED"},
        "positive": status == "VERIFIED_IMPROVED",
        "evidence_fingerprints": [canonical_sha256({"domain": domain, "kind": kind, "status": status, "obs": obs})],
        "evidence_observation_count": obs,
        "status_transition_count": transitions,
    }


def _outcome_state(records: dict[str, dict], *, tracked: dict[str, int] | None = None, cycle: int = 1, salt: str = "a") -> dict:
    tracked = tracked or {d: 0 for d in DOMAINS}
    evaluated_by_domain = {d: 0 for d in DOMAINS}
    for rec in records.values():
        if rec["current_status"] in {"VERIFIED_IMPROVED", "VERIFIED_NO_EFFECT", "REGRESSED"}:
            evaluated_by_domain[rec["domain"]] += 1
    per_domain = {}
    for d in DOMAINS:
        t = int(tracked.get(d, 0))
        e = evaluated_by_domain[d]
        per_domain[d] = {
            "tracked": t,
            "evaluated": e,
            "verified_improved": sum(1 for r in records.values() if r["domain"] == d and r["current_status"] == "VERIFIED_IMPROVED"),
            "verified_no_effect": sum(1 for r in records.values() if r["domain"] == d and r["current_status"] == "VERIFIED_NO_EFFECT"),
            "regressed": sum(1 for r in records.values() if r["domain"] == d and r["current_status"] == "REGRESSED"),
            "outcome_coverage_rate": (e / t) if t else None,
            "outcome_coverage_applicable": t > 0,
            "outcome_coverage_status": "DEFINED" if t > 0 else "NOT_APPLICABLE",
        }
    metrics = {
        "tracked_recommendations": sum(int(v) for v in tracked.values()),
        "evaluated_recommendations": sum(evaluated_by_domain.values()),
        "verified_improved": sum(1 for r in records.values() if r["current_status"] == "VERIFIED_IMPROVED"),
        "verified_no_effect": sum(1 for r in records.values() if r["current_status"] == "VERIFIED_NO_EFFECT"),
        "regressed": sum(1 for r in records.values() if r["current_status"] == "REGRESSED"),
        "per_domain": per_domain,
    }
    state = {
        "schema_version": 1,
        "policy_version": "39.4.0.1-outcome-intelligence-metric-semantics-v1",
        "source_semantic_cycle": cycle,
        "outcome_records": copy.deepcopy(records),
        "metrics": metrics,
        "learning_candidates": [],
        "next_attention": {"mode": "OUTCOME_MONITORING"},
        "metric_semantics": {"zero_denominator": "NOT_APPLICABLE"},
        "intelligence_digest": canonical_sha256({"records": records, "metrics": metrics, "cycle": cycle, "salt": salt}),
        "effect_boundary": copy.deepcopy(SAFE),
        "execution_effects_performed": 0,
    }
    state["state_sha256"] = canonical_sha256(state)
    return state


def _run(outcome: dict, prior: dict | None = None, generated_at: str = "2026-08-12T02:10:00Z") -> dict:
    return run_improvement_learning(
        outcome_state=outcome,
        prior_state=prior,
        policy=POLICY,
        generated_at=generated_at,
    )


def test_zero_tracked_never_fabricates_improvement_score():
    result = _run(_outcome_state({}, tracked={d: 0 for d in DOMAINS}))
    r = result["receipt"]
    assert r["learning_summary"]["evidence_status"] == "NO_RECOMMENDATIONS_YET"
    assert r["ranked_improvement_count"] == 0
    assert r["next_attention"]["mode"] == "WAIT_FOR_RECOMMENDATION_OUTCOMES"


def test_tracked_without_evaluated_routes_to_evidence_collection():
    tracked = {d: 0 for d in DOMAINS}
    tracked["AGENT"] = 2
    result = _run(_outcome_state({}, tracked=tracked))
    rows = result["state"]["ranked_improvements"]
    assert len(rows) == 1
    assert rows[0]["priority_class"] == "EVIDENCE_COLLECTION"
    assert rows[0]["domain"] == "AGENT"
    assert result["receipt"]["next_attention"]["mode"] == "OUTCOME_EVIDENCE_COLLECTION"


def test_regression_outranks_no_effect_and_reinforcement():
    records = {
        "r1": _record("SYSTEM", "latency", "REGRESSED", obs=2),
        "r2": _record("AGENT", "tooling", "VERIFIED_NO_EFFECT", obs=2),
        "r3": _record("OPERATOR", "workflow", "VERIFIED_IMPROVED", obs=2),
        "r4": _record("OPERATOR", "workflow", "VERIFIED_IMPROVED", obs=2),
    }
    tracked = {d: 0 for d in DOMAINS}
    tracked.update({"SYSTEM": 1, "AGENT": 1, "OPERATOR": 2})
    rows = _run(_outcome_state(records, tracked=tracked))["state"]["ranked_improvements"]
    assert rows[0]["priority_class"] == "CRITICAL_CORRECTIVE_REVIEW"
    assert rows[0]["domain"] == "SYSTEM"
    assert rows[1]["priority_class"] == "HIGH_CORRECTIVE_REVIEW"


def test_negative_agent_pattern_routes_to_skill_and_hanri_rule_review():
    records = {"r1": _record("AGENT", "tool-use", "REGRESSED")}
    tracked = {d: 0 for d in DOMAINS}
    tracked["AGENT"] = 1
    row = _run(_outcome_state(records, tracked=tracked))["state"]["ranked_improvements"][0]
    assert row["review_actions"] == ["SKILL_CANDIDATE_REVIEW", "HANRI_RECOMMENDATION_RULE_REVIEW"]
    assert row["self_apply_authorized"] is False
    assert row["install_authorized"] is False


def test_reinforcement_requires_repeated_positive_and_zero_negative():
    records = {
        "r1": _record("SYSTEM", "cache", "VERIFIED_IMPROVED"),
        "r2": _record("SYSTEM", "cache", "VERIFIED_IMPROVED"),
    }
    tracked = {d: 0 for d in DOMAINS}
    tracked["SYSTEM"] = 2
    row = _run(_outcome_state(records, tracked=tracked))["state"]["ranked_improvements"][0]
    assert row["priority_class"] == "BOUNDED_REINFORCEMENT_REVIEW"
    assert row["generalization_authorized"] is False


def test_negative_blocks_reinforcement_for_same_pattern():
    records = {
        "r1": _record("SYSTEM", "cache", "VERIFIED_IMPROVED"),
        "r2": _record("SYSTEM", "cache", "VERIFIED_IMPROVED"),
        "r3": _record("SYSTEM", "cache", "VERIFIED_NO_EFFECT"),
    }
    tracked = {d: 0 for d in DOMAINS}
    tracked["SYSTEM"] = 3
    row = _run(_outcome_state(records, tracked=tracked))["state"]["ranked_improvements"][0]
    assert row["priority_class"] == "HIGH_CORRECTIVE_REVIEW"


def test_small_sample_confidence_is_insufficient():
    records = {"r1": _record("SELF", "attention", "REGRESSED")}
    tracked = {d: 0 for d in DOMAINS}
    tracked["SELF"] = 1
    row = _run(_outcome_state(records, tracked=tracked))["state"]["ranked_improvements"][0]
    assert row["confidence"] == "INSUFFICIENT"


def test_supported_for_review_still_does_not_claim_causation():
    records = {f"r{i}": _record("OPERATOR", "advice", "VERIFIED_IMPROVED") for i in range(4)}
    tracked = {d: 0 for d in DOMAINS}
    tracked["OPERATOR"] = 4
    row = _run(_outcome_state(records, tracked=tracked))["state"]["ranked_improvements"][0]
    assert row["confidence"] == "SUPPORTED_FOR_REVIEW"
    assert row["causation_claimed"] is False
    assert row["generalization_authorized"] is False


def test_same_intelligence_digest_is_no_delta_and_does_not_inflate_recurrence():
    records = {"r1": _record("SYSTEM", "latency", "REGRESSED")}
    tracked = {d: 0 for d in DOMAINS}
    tracked["SYSTEM"] = 1
    outcome = _outcome_state(records, tracked=tracked)
    first = _run(outcome)["state"]
    second = _run(outcome, prior=first, generated_at="2026-08-12T02:11:00Z")["state"]
    assert second["transition"] == "NO_DELTA"
    assert second["pattern_memory"]["SYSTEM|latency"]["observation_cycles"] == 1
    assert second["pattern_memory"]["SYSTEM|latency"]["recurring_negative_cycles"] == 1


def test_new_semantic_digest_increments_negative_recurrence():
    records = {"r1": _record("SYSTEM", "latency", "REGRESSED")}
    tracked = {d: 0 for d in DOMAINS}
    tracked["SYSTEM"] = 1
    first = _run(_outcome_state(records, tracked=tracked, cycle=1, salt="a"))["state"]
    second = _run(_outcome_state(records, tracked=tracked, cycle=2, salt="b"), prior=first)["state"]
    assert second["transition"] == "SEMANTIC_DELTA"
    assert second["pattern_memory"]["SYSTEM|latency"]["observation_cycles"] == 2
    assert second["pattern_memory"]["SYSTEM|latency"]["recurring_negative_cycles"] == 2


def test_tampered_prior_state_fails_closed():
    first = _run(_outcome_state({}, tracked={d: 0 for d in DOMAINS}))["state"]
    first["transition"] = "tampered"
    with pytest.raises(ValueError, match="state SHA mismatch"):
        _run(_outcome_state({}, tracked={d: 0 for d in DOMAINS}), prior=first)


def test_foreign_outcome_policy_fails_closed():
    outcome = _outcome_state({}, tracked={d: 0 for d in DOMAINS})
    outcome["policy_version"] = "foreign"
    outcome["state_sha256"] = canonical_sha256({k: v for k, v in outcome.items() if k != "state_sha256"})
    with pytest.raises(ValueError, match="R39.4.0.1 outcome state required"):
        _run(outcome)


def test_effect_boundary_remains_zero_effect_and_proposal_only():
    result = _run(_outcome_state({}, tracked={d: 0 for d in DOMAINS}))
    for obj in (result["state"], result["receipt"]):
        assert obj["execution_effects_performed"] == 0
        assert obj["effect_boundary"]["proposal_only"] is True
        assert obj["effect_boundary"]["provider_calls"] is False
        assert obj["effect_boundary"]["scheduler_modify"] is False
        assert obj["effect_boundary"]["self_apply"] is False
        assert obj["effect_boundary"]["skill_install"] is False
        assert obj["effect_boundary"]["system_write"] is False
        assert obj["effect_boundary"]["operator_message"] is False
        assert obj["effect_boundary"]["can_trade"] is False
        assert obj["effect_boundary"]["capital_permission"] == "DENY"
