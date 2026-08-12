from __future__ import annotations

import copy

import pytest

from hanri.attention_governor import canonical_sha256
from hanri.improvement_recommendations import POLICY_VERSION, run_bounded_improvement_recommendations


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
    "max_recommendations": 12,
    "receipt_top_n": 5,
    "max_history_tail": 20,
    "decision_options": ["ACCEPT", "REJECT", "REVISE", "HOLD"],
    "emit_priority_classes": [
        "CRITICAL_CORRECTIVE_REVIEW",
        "HIGH_CORRECTIVE_REVIEW",
        "EVIDENCE_COLLECTION",
        "BOUNDED_REINFORCEMENT_REVIEW",
    ],
    "allowed_review_actions": [
        "ATTENTION_RULE_REVIEW",
        "SKILL_CANDIDATE_REVIEW",
        "SYSTEM_IMPROVEMENT_REVIEW",
        "OPERATOR_ADVICE_REVIEW",
        "HANRI_RECOMMENDATION_RULE_REVIEW",
        "REINFORCEMENT_REVIEW",
        "OUTCOME_EVIDENCE_COLLECTION",
    ],
    "human_review_required": True,
    "shadow_test_required_before_adoption": True,
    "execution_authority_forbidden": True,
    "effect_boundary": SAFE,
}


def _row(
    *,
    rank: int,
    domain: str,
    kind: str,
    priority: str,
    actions: list[str],
    improved: int = 0,
    no_effect: int = 0,
    regressed: int = 0,
    unevaluated: int = 0,
) -> dict:
    return {
        "pattern_id": f"p-{rank}-{domain}-{kind}",
        "rank": rank,
        "domain": domain,
        "kind": kind,
        "priority_class": priority,
        "priority_score": 100.0 - rank,
        "confidence": "BOUNDED",
        "review_actions": actions,
        "recommendation_ids": [f"src-{rank}"],
        "evidence_fingerprints": [f"fp-{rank}"],
        "verified_improved": improved,
        "verified_no_effect": no_effect,
        "regressed": regressed,
        "unevaluated": unevaluated,
        "authority": "PROPOSAL_ONLY",
        "causation_claimed": False,
        "generalization_authorized": False,
        "self_apply_authorized": False,
        "install_authorized": False,
    }


def _learning(rows: list[dict], *, digest_salt: str = "a", cycle: int = 1) -> dict:
    state = {
        "schema_version": 1,
        "policy_version": "39.5.0-improvement-learning-v1",
        "generated_at": "2026-08-12T09:03:16Z",
        "source_outcome_policy_version": "39.4.0.1-outcome-intelligence-metric-semantics-v1",
        "source_outcome_state_sha256": canonical_sha256({"outcome": digest_salt}),
        "source_intelligence_digest": canonical_sha256({"source": digest_salt}),
        "source_semantic_cycle": cycle,
        "transition": "SEMANTIC_DELTA",
        "learning_summary": {
            "tracked_recommendations": len(rows),
            "evaluated_recommendations": sum(
                1 for r in rows
                if int(r.get("verified_improved", 0)) + int(r.get("verified_no_effect", 0)) + int(r.get("regressed", 0)) > 0
            ),
        },
        "ranked_improvements": copy.deepcopy(rows),
        "pattern_memory": {},
        "next_attention": {"mode": "WAIT_FOR_RECOMMENDATION_OUTCOMES"},
        "history_tail": [],
        "learning_digest": canonical_sha256({"rows": rows, "salt": digest_salt}),
        "effect_boundary": copy.deepcopy(SAFE),
        "execution_effects_performed": 0,
    }
    state["state_sha256"] = canonical_sha256(state)
    return state


def _run(learning: dict, prior: dict | None = None, policy: dict | None = None) -> dict:
    return run_bounded_improvement_recommendations(
        learning_state=learning,
        prior_state=prior,
        policy=copy.deepcopy(policy or POLICY),
        generated_at="2026-08-12T09:10:00Z",
    )


def test_zero_ranked_items_do_not_fabricate_advice():
    result = _run(_learning([]))
    receipt = result["receipt"]
    assert receipt["recommendation_count"] == 0
    assert receipt["recommendation_summary"]["recommendation_status"] == "NO_RECOMMENDATIONS_YET"
    assert receipt["top_recommendations"] == []
    assert receipt["next_attention"]["mode"] == "WAIT_FOR_RECOMMENDATION_OUTCOMES"


def test_negative_agent_pattern_emits_skill_and_hanri_rule_packets():
    rows = [_row(
        rank=1,
        domain="AGENT",
        kind="tool-use",
        priority="CRITICAL_CORRECTIVE_REVIEW",
        actions=["SKILL_CANDIDATE_REVIEW", "HANRI_RECOMMENDATION_RULE_REVIEW"],
        regressed=1,
    )]
    result = _run(_learning(rows))
    packets = result["state"]["recommendations"]
    assert [x["review_action"] for x in packets] == [
        "SKILL_CANDIDATE_REVIEW",
        "HANRI_RECOMMENDATION_RULE_REVIEW",
    ]
    assert all(x["required_human_decision"] is True for x in packets)
    assert all(x["execution_authority"] == "NONE" for x in packets)
    assert all(x["self_apply_authorized"] is False for x in packets)


def test_evidence_debt_emits_collection_packet_without_change_claim():
    rows = [_row(
        rank=1,
        domain="SYSTEM",
        kind="OUTCOME_EVIDENCE_DEBT",
        priority="EVIDENCE_COLLECTION",
        actions=["OUTCOME_EVIDENCE_COLLECTION"],
        unevaluated=3,
    )]
    packet = _run(_learning(rows))["state"]["recommendations"][0]
    assert packet["review_action"] == "OUTCOME_EVIDENCE_COLLECTION"
    assert packet["evidence_class"] == "MISSING_OUTCOME_EVIDENCE"
    assert "Collect explicit outcome evidence" in packet["proposed_change"]
    assert packet["system_write_authorized"] is False


def test_reinforcement_is_review_only_and_never_generalizes():
    rows = [_row(
        rank=1,
        domain="OPERATOR",
        kind="workflow",
        priority="BOUNDED_REINFORCEMENT_REVIEW",
        actions=["REINFORCEMENT_REVIEW"],
        improved=2,
    )]
    packet = _run(_learning(rows))["state"]["recommendations"][0]
    assert packet["review_action"] == "REINFORCEMENT_REVIEW"
    assert packet["generalization_authorized"] is False
    assert packet["execution_authority"] == "NONE"
    assert packet["decision_options"] == ["ACCEPT", "REJECT", "REVISE", "HOLD"]


def test_monitor_more_evidence_with_non_review_action_fails_closed():
    rows = [_row(
        rank=1,
        domain="SELF",
        kind="attention",
        priority="MONITOR_MORE_EVIDENCE",
        actions=["OUTCOME_MONITORING"],
    )]
    with pytest.raises(ValueError, match="unknown review_actions"):
        _run(_learning(rows))


def test_reinforcement_semantic_guard_fails_closed():
    rows = [_row(
        rank=1,
        domain="SYSTEM",
        kind="cache",
        priority="BOUNDED_REINFORCEMENT_REVIEW",
        actions=["REINFORCEMENT_REVIEW"],
        improved=2,
        no_effect=1,
    )]
    with pytest.raises(ValueError, match="zero negative outcomes"):
        _run(_learning(rows))


def test_tampered_learning_state_fails_closed():
    learning = _learning([])
    learning["transition"] = "tampered"
    with pytest.raises(ValueError, match="learning state SHA mismatch"):
        _run(learning)


def test_same_learning_digest_is_no_delta_and_does_not_inflate_history():
    learning = _learning([])
    first = _run(learning)["state"]
    second = run_bounded_improvement_recommendations(
        learning_state=learning,
        prior_state=first,
        policy=POLICY,
        generated_at="2026-08-12T09:11:00Z",
    )["state"]
    assert second["transition"] == "NO_DELTA"
    assert len(second["history_tail"]) == len(first["history_tail"]) == 1


def test_new_learning_digest_is_semantic_delta():
    first = _run(_learning([], digest_salt="a", cycle=1))["state"]
    second = run_bounded_improvement_recommendations(
        learning_state=_learning([], digest_salt="b", cycle=2),
        prior_state=first,
        policy=POLICY,
        generated_at="2026-08-12T09:12:00Z",
    )["state"]
    assert second["transition"] == "SEMANTIC_DELTA"
    assert len(second["history_tail"]) == 2


def test_max_recommendation_cap_is_deterministic_by_rank_then_action_order():
    rows = [
        _row(
            rank=2,
            domain="SYSTEM",
            kind="latency",
            priority="HIGH_CORRECTIVE_REVIEW",
            actions=["SYSTEM_IMPROVEMENT_REVIEW", "HANRI_RECOMMENDATION_RULE_REVIEW"],
            no_effect=1,
        ),
        _row(
            rank=1,
            domain="AGENT",
            kind="tool-use",
            priority="CRITICAL_CORRECTIVE_REVIEW",
            actions=["SKILL_CANDIDATE_REVIEW", "HANRI_RECOMMENDATION_RULE_REVIEW"],
            regressed=1,
        ),
    ]
    p = copy.deepcopy(POLICY)
    p["max_recommendations"] = 3
    packets = _run(_learning(rows), policy=p)["state"]["recommendations"]
    assert [(x["source_rank"], x["review_action"]) for x in packets] == [
        (1, "SKILL_CANDIDATE_REVIEW"),
        (1, "HANRI_RECOMMENDATION_RULE_REVIEW"),
        (2, "SYSTEM_IMPROVEMENT_REVIEW"),
    ]


def test_effect_boundary_remains_proposal_only_and_zero_effect():
    result = _run(_learning([]))
    for obj in (result["state"], result["receipt"]):
        assert obj["execution_effects_performed"] == 0
        assert obj["effect_boundary"]["proposal_only"] is True
        assert obj["effect_boundary"]["local_state_write_only"] is True
        assert obj["effect_boundary"]["provider_calls"] is False
        assert obj["effect_boundary"]["scheduler_modify"] is False
        assert obj["effect_boundary"]["self_apply"] is False
        assert obj["effect_boundary"]["skill_install"] is False
        assert obj["effect_boundary"]["system_write"] is False
        assert obj["effect_boundary"]["operator_message"] is False
        assert obj["effect_boundary"]["can_trade"] is False
        assert obj["effect_boundary"]["capital_permission"] == "DENY"
