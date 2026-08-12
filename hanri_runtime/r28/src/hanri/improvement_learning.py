from __future__ import annotations

import copy
from collections import Counter, defaultdict
from typing import Any, Mapping

from hanri.attention_governor import DOMAINS, canonical_sha256

POLICY_VERSION = "39.5.0-improvement-learning-v1"
OUTCOME_POLICY_VERSION = "39.4.0.1-outcome-intelligence-metric-semantics-v1"

POSITIVE = {"VERIFIED_IMPROVED"}
NEGATIVE = {"VERIFIED_NO_EFFECT", "REGRESSED"}
EVALUATED = POSITIVE | NEGATIVE

_EFFECT_FALSE_KEYS = (
    "provider_calls",
    "scheduler_install",
    "scheduler_modify",
    "human_decision_execution",
    "self_apply",
    "skill_install",
    "system_write",
    "operator_message",
    "auto_dispatch",
    "external_messages",
)


def _without_hash(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in payload.items() if k != key}


def _safe_effect_boundary() -> dict[str, Any]:
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


def _require_safe_boundary(boundary: Mapping[str, Any], *, context: str) -> None:
    if not bool(boundary.get("proposal_only", False)):
        raise ValueError(f"{context}: proposal_only must remain true")
    if not bool(boundary.get("local_state_write_only", False)):
        raise ValueError(f"{context}: local_state_write_only must remain true")
    if bool(boundary.get("can_trade", False)):
        raise ValueError(f"{context}: can_trade must remain false")
    if str(boundary.get("capital_permission", "DENY")).upper() != "DENY":
        raise ValueError(f"{context}: capital_permission must remain DENY")
    for key in _EFFECT_FALSE_KEYS:
        if bool(boundary.get(key, False)):
            raise ValueError(f"{context}: {key} must remain false")


def _verify_outcome_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(dict(raw))
    if str(state.get("policy_version", "")) != OUTCOME_POLICY_VERSION:
        raise ValueError(
            f"R39.4.0.1 outcome state required expected={OUTCOME_POLICY_VERSION} "
            f"actual={state.get('policy_version')}"
        )
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("outcome state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="outcome_state")
    return state


def _verify_prior_state(raw: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    state = copy.deepcopy(dict(raw))
    if str(state.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError("legacy_or_foreign_improvement_learning_state_requires_migration")
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("prior improvement-learning state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="prior_state")
    return state


def _policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    p = copy.deepcopy(dict(raw))
    if str(p.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    if int(p.get("min_evaluated_for_pattern", 2)) < 1:
        raise ValueError("min_evaluated_for_pattern must be >= 1")
    if int(p.get("supported_evidence_min", 4)) < int(p.get("min_evaluated_for_pattern", 2)):
        raise ValueError("supported_evidence_min must be >= min_evaluated_for_pattern")
    if int(p.get("max_history_tail", 20)) < 1:
        raise ValueError("max_history_tail must be >= 1")
    _require_safe_boundary(dict(p.get("effect_boundary", {})), context="policy")
    return p


def _candidate_type(domain: str) -> str:
    return {
        "SELF": "ATTENTION_RULE_REVIEW",
        "AGENT": "SKILL_CANDIDATE_REVIEW",
        "SYSTEM": "SYSTEM_IMPROVEMENT_REVIEW",
        "OPERATOR": "OPERATOR_ADVICE_REVIEW",
    }.get(domain, "RECOMMENDATION_RULE_REVIEW")


def _confidence(evaluated: int, policy: Mapping[str, Any]) -> str:
    min_evaluated = int(policy.get("min_evaluated_for_pattern", 2))
    supported = int(policy.get("supported_evidence_min", 4))
    if evaluated < min_evaluated:
        return "INSUFFICIENT"
    if evaluated < supported:
        return "BOUNDED"
    return "SUPPORTED_FOR_REVIEW"


def _priority_class(*, regressed: int, no_effect: int, improved: int, evaluated: int, policy: Mapping[str, Any]) -> str:
    if regressed > 0:
        return "CRITICAL_CORRECTIVE_REVIEW"
    if no_effect > 0:
        return "HIGH_CORRECTIVE_REVIEW"
    reinforcement_min = max(2, int(policy.get("reinforcement_min_verified_improved", 2)))
    if improved >= reinforcement_min and evaluated == improved:
        return "BOUNDED_REINFORCEMENT_REVIEW"
    return "MONITOR_MORE_EVIDENCE"


def _score(*, regressed: int, no_effect: int, improved: int, evaluated: int, evidence_observations: int,
           transition_instability: int, recurring_negative_cycles: int, policy: Mapping[str, Any]) -> float | None:
    if evaluated <= 0:
        return None
    weights = dict(policy.get("priority_weights", {}))
    regression_w = float(weights.get("regressed", 100.0))
    no_effect_w = float(weights.get("verified_no_effect", 60.0))
    reinforcement_w = float(weights.get("verified_improved", 10.0))
    evidence_w = float(weights.get("evidence_observation", 0.25))
    recurrence_w = float(weights.get("recurring_negative_cycle", 4.0))
    instability_penalty = float(weights.get("transition_instability_penalty", 1.0))
    base = (
        regression_w * regressed
        + no_effect_w * no_effect
        + reinforcement_w * improved
        + evidence_w * min(evidence_observations, int(policy.get("evidence_observation_cap", 12)))
        + recurrence_w * recurring_negative_cycles
        - instability_penalty * transition_instability
    )
    return round(base, 6)


def _group_records(outcome_state: Mapping[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rid, raw in sorted(dict(outcome_state.get("outcome_records", {})).items()):
        rec = dict(raw)
        domain = str(rec.get("domain", "")).upper()
        if domain not in DOMAINS:
            raise ValueError(f"outcome record {rid} has invalid domain={domain}")
        kind = str(rec.get("kind", "")).strip() or "UNSPECIFIED"
        status = str(rec.get("current_status", "UNKNOWN")).upper()
        if status not in EVALUATED | {"UNKNOWN"}:
            raise ValueError(f"outcome record {rid} has unsupported status={status}")
        grouped[(domain, kind)].append({"recommendation_id": rid, **rec, "current_status": status})
    return grouped


def _build_pattern_rows(
    *,
    outcome_state: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    semantic_delta: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped = _group_records(outcome_state)
    prior_memory = dict((prior_state or {}).get("pattern_memory", {}))
    pattern_memory: dict[str, Any] = copy.deepcopy(prior_memory)
    rows: list[dict[str, Any]] = []

    for (domain, kind), records in sorted(grouped.items()):
        statuses = Counter(str(r.get("current_status", "UNKNOWN")).upper() for r in records)
        regressed = statuses["REGRESSED"]
        no_effect = statuses["VERIFIED_NO_EFFECT"]
        improved = statuses["VERIFIED_IMPROVED"]
        evaluated = regressed + no_effect + improved
        evidence_observations = sum(int(r.get("evidence_observation_count", 0)) for r in records)
        transition_instability = sum(max(0, int(r.get("status_transition_count", 0)) - 1) for r in records)
        key = f"{domain}|{kind}"
        prior = dict(prior_memory.get(key, {})) if isinstance(prior_memory.get(key), Mapping) else {}
        recurring_negative_cycles = int(prior.get("recurring_negative_cycles", 0))
        if semantic_delta and (regressed + no_effect) > 0:
            recurring_negative_cycles += 1
        elif semantic_delta:
            recurring_negative_cycles = 0

        priority = _priority_class(
            regressed=regressed,
            no_effect=no_effect,
            improved=improved,
            evaluated=evaluated,
            policy=policy,
        )
        score = _score(
            regressed=regressed,
            no_effect=no_effect,
            improved=improved,
            evaluated=evaluated,
            evidence_observations=evidence_observations,
            transition_instability=transition_instability,
            recurring_negative_cycles=recurring_negative_cycles,
            policy=policy,
        )
        confidence = _confidence(evaluated, policy)
        recommendation_ids = sorted(str(r["recommendation_id"]) for r in records)
        evidence_fingerprints = sorted({
            str(fp)
            for r in records
            for fp in r.get("evidence_fingerprints", [])
            if str(fp)
        })

        if regressed or no_effect:
            actions = [_candidate_type(domain), "HANRI_RECOMMENDATION_RULE_REVIEW"]
        elif priority == "BOUNDED_REINFORCEMENT_REVIEW":
            actions = ["REINFORCEMENT_REVIEW"]
        else:
            actions = ["OUTCOME_MONITORING"]

        row = {
            "pattern_id": "R39.5-" + canonical_sha256({"domain": domain, "kind": kind})[:18],
            "domain": domain,
            "kind": kind,
            "evaluated": evaluated,
            "verified_improved": improved,
            "verified_no_effect": no_effect,
            "regressed": regressed,
            "unknown": statuses["UNKNOWN"],
            "recommendation_ids": recommendation_ids,
            "evidence_fingerprints": evidence_fingerprints,
            "evidence_observation_count": evidence_observations,
            "status_transition_instability": transition_instability,
            "recurring_negative_cycles": recurring_negative_cycles,
            "priority_class": priority,
            "priority_score": score,
            "confidence": confidence,
            "review_actions": actions,
            "authority": "PROPOSAL_ONLY",
            "causation_claimed": False,
            "generalization_authorized": False,
            "self_apply_authorized": False,
            "install_authorized": False,
        }
        rows.append(row)

        if semantic_delta:
            history = list(prior.get("history_tail", []))
            history.append({
                "source_intelligence_digest": str(outcome_state.get("intelligence_digest", "")),
                "evaluated": evaluated,
                "verified_improved": improved,
                "verified_no_effect": no_effect,
                "regressed": regressed,
                "priority_class": priority,
                "priority_score": score,
            })
            history = history[-max(1, int(policy.get("pattern_history_tail", 10))):]
        else:
            history = list(prior.get("history_tail", []))

        pattern_memory[key] = {
            "domain": domain,
            "kind": kind,
            "observation_cycles": int(prior.get("observation_cycles", 0)) + (1 if semantic_delta else 0),
            "recurring_negative_cycles": recurring_negative_cycles,
            "last_priority_class": priority,
            "last_priority_score": score,
            "history_tail": history,
        }

    return rows, dict(sorted(pattern_memory.items()))


def _debt_rows(outcome_state: Mapping[str, Any], policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    metrics = dict(outcome_state.get("metrics", {}))
    for domain in DOMAINS:
        raw = dict(dict(metrics.get("per_domain", {})).get(domain, {}))
        tracked = int(raw.get("tracked", 0))
        evaluated = int(raw.get("evaluated", 0))
        debt = max(0, tracked - evaluated)
        if debt <= 0:
            continue
        ratio = debt / tracked if tracked else 0.0
        score = round(float(policy.get("outcome_debt_weight", 30.0)) * ratio, 6)
        rows.append({
            "pattern_id": "R39.5-DEBT-" + canonical_sha256({"domain": domain, "tracked": tracked, "evaluated": evaluated})[:14],
            "domain": domain,
            "kind": "OUTCOME_EVIDENCE_DEBT",
            "evaluated": evaluated,
            "tracked": tracked,
            "unevaluated": debt,
            "priority_class": "EVIDENCE_COLLECTION",
            "priority_score": score,
            "confidence": "DIRECT_COUNT",
            "review_actions": ["OUTCOME_EVIDENCE_COLLECTION"],
            "authority": "PROPOSAL_ONLY",
            "causation_claimed": False,
            "generalization_authorized": False,
            "self_apply_authorized": False,
            "install_authorized": False,
        })
    return rows


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    class_order = {
        "CRITICAL_CORRECTIVE_REVIEW": 0,
        "HIGH_CORRECTIVE_REVIEW": 1,
        "EVIDENCE_COLLECTION": 2,
        "BOUNDED_REINFORCEMENT_REVIEW": 3,
        "MONITOR_MORE_EVIDENCE": 4,
    }
    ordered = sorted(
        rows,
        key=lambda r: (
            class_order.get(str(r.get("priority_class")), 99),
            -(float(r["priority_score"]) if r.get("priority_score") is not None else -1.0),
            str(r.get("domain", "")),
            str(r.get("kind", "")),
        ),
    )
    out = []
    for idx, row in enumerate(ordered, start=1):
        item = copy.deepcopy(row)
        item["rank"] = idx
        out.append(item)
    return out


def _next_attention(outcome_state: Mapping[str, Any], ranked: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = dict(outcome_state.get("metrics", {}))
    tracked = int(metrics.get("tracked_recommendations", 0))
    evaluated = int(metrics.get("evaluated_recommendations", 0))
    if tracked == 0:
        return {
            "mode": "WAIT_FOR_RECOMMENDATION_OUTCOMES",
            "focus_domains": list(DOMAINS),
            "reason": "no tracked recommendations exist; do not fabricate improvement scores",
        }
    if evaluated == 0:
        return {
            "mode": "OUTCOME_EVIDENCE_COLLECTION",
            "focus_domains": [d for d in DOMAINS if int(dict(dict(metrics.get("per_domain", {})).get(d, {})).get("tracked", 0)) > 0],
            "reason": "tracked recommendations exist but no explicit evaluated outcomes exist",
        }
    corrective = [r for r in ranked if str(r.get("priority_class", "")) in {"CRITICAL_CORRECTIVE_REVIEW", "HIGH_CORRECTIVE_REVIEW"}]
    if corrective:
        return {
            "mode": "PRIORITIZE_CORRECTIVE_REVIEW",
            "focus_domains": list(dict.fromkeys(str(r.get("domain")) for r in corrective)),
            "reason": "explicit negative outcomes outrank reinforcement and monitoring",
        }
    reinforcement = [r for r in ranked if str(r.get("priority_class", "")) == "BOUNDED_REINFORCEMENT_REVIEW"]
    if reinforcement:
        return {
            "mode": "BOUNDED_REINFORCEMENT_REVIEW",
            "focus_domains": list(dict.fromkeys(str(r.get("domain")) for r in reinforcement)),
            "reason": "repeated verified improvements support review only; automatic generalization remains forbidden",
        }
    return {
        "mode": "CONTINUE_OUTCOME_MONITORING",
        "focus_domains": list(DOMAINS),
        "reason": "evidence is insufficient for corrective or reinforcement prioritization",
    }


def run_improvement_learning(
    *,
    outcome_state: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    outcome = _verify_outcome_state(outcome_state)
    prior = _verify_prior_state(prior_state)
    p = _policy(policy)

    source_digest = str(outcome.get("intelligence_digest", ""))
    if not source_digest:
        raise ValueError("outcome intelligence_digest missing")
    prior_digest = str((prior or {}).get("source_intelligence_digest", ""))
    semantic_delta = source_digest != prior_digest
    transition = "SEMANTIC_DELTA" if semantic_delta else "NO_DELTA"

    rows, pattern_memory = _build_pattern_rows(
        outcome_state=outcome,
        prior_state=prior,
        policy=p,
        semantic_delta=semantic_delta,
    )
    rows.extend(_debt_rows(outcome, p))
    ranked = _rank(rows)
    next_attention = _next_attention(outcome, ranked)

    metrics = dict(outcome.get("metrics", {}))
    tracked = int(metrics.get("tracked_recommendations", 0))
    evaluated = int(metrics.get("evaluated_recommendations", 0))
    corrective_count = sum(1 for r in ranked if str(r.get("priority_class")) in {"CRITICAL_CORRECTIVE_REVIEW", "HIGH_CORRECTIVE_REVIEW"})
    reinforcement_count = sum(1 for r in ranked if str(r.get("priority_class")) == "BOUNDED_REINFORCEMENT_REVIEW")
    debt_count = sum(1 for r in ranked if str(r.get("priority_class")) == "EVIDENCE_COLLECTION")

    if tracked == 0:
        evidence_status = "NO_RECOMMENDATIONS_YET"
    elif evaluated == 0:
        evidence_status = "NO_EVALUATED_OUTCOMES"
    else:
        evidence_status = "EVALUATED_OUTCOMES_PRESENT"

    learning_summary = {
        "tracked_recommendations": tracked,
        "evaluated_recommendations": evaluated,
        "ranked_improvement_items": len(ranked),
        "corrective_review_items": corrective_count,
        "reinforcement_review_items": reinforcement_count,
        "evidence_debt_items": debt_count,
        "evidence_status": evidence_status,
        "causation_claimed": False,
        "automatic_generalization": False,
    }

    effect_boundary = _safe_effect_boundary()
    learning_digest = canonical_sha256({
        "source_intelligence_digest": source_digest,
        "transition": transition,
        "ranked_improvements": ranked,
        "pattern_memory": pattern_memory,
        "next_attention": next_attention,
        "learning_summary": learning_summary,
    })

    history = list((prior or {}).get("history_tail", []))
    if semantic_delta:
        history.append({
            "generated_at": generated_at,
            "source_intelligence_digest": source_digest,
            "transition": transition,
            "evidence_status": evidence_status,
            "ranked_improvement_items": len(ranked),
            "corrective_review_items": corrective_count,
            "reinforcement_review_items": reinforcement_count,
            "evidence_debt_items": debt_count,
            "next_attention_mode": next_attention["mode"],
        })
    history = history[-max(1, int(p.get("max_history_tail", 20))):]

    state = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "source_outcome_policy_version": OUTCOME_POLICY_VERSION,
        "source_outcome_state_sha256": str(outcome.get("state_sha256", "")),
        "source_intelligence_digest": source_digest,
        "source_semantic_cycle": int(outcome.get("source_semantic_cycle", 0)),
        "transition": transition,
        "learning_summary": learning_summary,
        "ranked_improvements": ranked,
        "pattern_memory": pattern_memory,
        "next_attention": next_attention,
        "history_tail": history,
        "learning_digest": learning_digest,
        "effect_boundary": effect_boundary,
        "execution_effects_performed": 0,
    }
    state["state_sha256"] = canonical_sha256(state)

    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "status": "PASS",
        "source_outcome_state_sha256": state["source_outcome_state_sha256"],
        "source_intelligence_digest": source_digest,
        "source_semantic_cycle": state["source_semantic_cycle"],
        "transition": transition,
        "learning_summary": copy.deepcopy(learning_summary),
        "ranked_improvement_count": len(ranked),
        "top_ranked_improvements": copy.deepcopy(ranked[: max(1, int(p.get("receipt_top_n", 5)))]),
        "next_attention": copy.deepcopy(next_attention),
        "learning_digest": learning_digest,
        "state_sha256": state["state_sha256"],
        "effect_boundary": copy.deepcopy(effect_boundary),
        "execution_effects_performed": 0,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"state": state, "receipt": receipt}


__all__ = ["POLICY_VERSION", "OUTCOME_POLICY_VERSION", "run_improvement_learning"]
