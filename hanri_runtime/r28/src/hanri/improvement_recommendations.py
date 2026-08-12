from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping

from hanri.attention_governor import DOMAINS, canonical_sha256

POLICY_VERSION = "39.6.0-bounded-improvement-recommendations-v1"
SOURCE_POLICY_VERSION = "39.5.0-improvement-learning-v1"

KNOWN_PRIORITY_CLASSES = {
    "CRITICAL_CORRECTIVE_REVIEW",
    "HIGH_CORRECTIVE_REVIEW",
    "EVIDENCE_COLLECTION",
    "BOUNDED_REINFORCEMENT_REVIEW",
    "MONITOR_MORE_EVIDENCE",
}

KNOWN_REVIEW_ACTIONS = {
    "ATTENTION_RULE_REVIEW",
    "SKILL_CANDIDATE_REVIEW",
    "SYSTEM_IMPROVEMENT_REVIEW",
    "OPERATOR_ADVICE_REVIEW",
    "HANRI_RECOMMENDATION_RULE_REVIEW",
    "REINFORCEMENT_REVIEW",
    "OUTCOME_EVIDENCE_COLLECTION",
}

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


def _verify_learning_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(dict(raw))
    if str(state.get("policy_version", "")) != SOURCE_POLICY_VERSION:
        raise ValueError(
            f"R39.5 learning state required expected={SOURCE_POLICY_VERSION} "
            f"actual={state.get('policy_version')}"
        )
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("R39.5 learning state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="learning_state")
    if int(state.get("execution_effects_performed", 0)) != 0:
        raise ValueError("R39.5 learning state execution effects must remain zero")
    if not str(state.get("learning_digest", "")).strip():
        raise ValueError("R39.5 learning_digest missing")
    if not isinstance(state.get("ranked_improvements", []), list):
        raise ValueError("R39.5 ranked_improvements must be a list")
    return state


def _verify_prior_state(raw: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    state = copy.deepcopy(dict(raw))
    if str(state.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError("legacy_or_foreign_bounded_recommendation_state_requires_migration")
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("prior bounded recommendation state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="prior_state")
    if int(state.get("execution_effects_performed", 0)) != 0:
        raise ValueError("prior bounded recommendation state effects must remain zero")
    return state


def _policy(raw: Mapping[str, Any]) -> dict[str, Any]:
    p = copy.deepcopy(dict(raw))
    if str(p.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    if int(p.get("max_recommendations", 12)) < 1:
        raise ValueError("max_recommendations must be >= 1")
    if int(p.get("receipt_top_n", 5)) < 1:
        raise ValueError("receipt_top_n must be >= 1")
    if int(p.get("max_history_tail", 20)) < 1:
        raise ValueError("max_history_tail must be >= 1")

    decisions = [str(x).upper() for x in p.get("decision_options", [])]
    if decisions != ["ACCEPT", "REJECT", "REVISE", "HOLD"]:
        raise ValueError("decision_options must be exactly ACCEPT/REJECT/REVISE/HOLD")

    emit = {str(x).upper() for x in p.get("emit_priority_classes", [])}
    if not emit or not emit.issubset(KNOWN_PRIORITY_CLASSES - {"MONITOR_MORE_EVIDENCE"}):
        raise ValueError("emit_priority_classes invalid or unsafe")

    actions = {str(x).upper() for x in p.get("allowed_review_actions", [])}
    if not actions or not actions.issubset(KNOWN_REVIEW_ACTIONS):
        raise ValueError("allowed_review_actions invalid")

    if not bool(p.get("human_review_required", False)):
        raise ValueError("human_review_required must remain true")
    if not bool(p.get("shadow_test_required_before_adoption", False)):
        raise ValueError("shadow_test_required_before_adoption must remain true")
    if not bool(p.get("execution_authority_forbidden", False)):
        raise ValueError("execution_authority_forbidden must remain true")

    _require_safe_boundary(dict(p.get("effect_boundary", {})), context="policy")
    p["_emit_priority_classes"] = emit
    p["_allowed_review_actions"] = actions
    p["_decision_options"] = decisions
    return p


def _validate_ranked_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(dict(raw))
    domain = str(row.get("domain", "")).upper()
    if domain not in DOMAINS:
        raise ValueError(f"ranked improvement has invalid domain={domain}")

    priority = str(row.get("priority_class", "")).upper()
    if priority not in KNOWN_PRIORITY_CLASSES:
        raise ValueError(f"ranked improvement has invalid priority_class={priority}")

    rank = int(row.get("rank", 0))
    if rank < 1:
        raise ValueError("ranked improvement rank must be >= 1")

    actions = [str(x).upper() for x in row.get("review_actions", [])]
    if not actions:
        raise ValueError("ranked improvement review_actions cannot be empty")
    unknown = sorted(set(actions) - KNOWN_REVIEW_ACTIONS)
    if unknown:
        raise ValueError(f"ranked improvement has unknown review_actions={unknown}")

    if str(row.get("authority", "PROPOSAL_ONLY")).upper() != "PROPOSAL_ONLY":
        raise ValueError("ranked improvement authority must remain PROPOSAL_ONLY")
    for key in ("causation_claimed", "generalization_authorized", "self_apply_authorized", "install_authorized"):
        if bool(row.get(key, False)):
            raise ValueError(f"ranked improvement {key} must remain false")

    regressed = max(0, int(row.get("regressed", 0)))
    no_effect = max(0, int(row.get("verified_no_effect", 0)))
    improved = max(0, int(row.get("verified_improved", 0)))
    unevaluated = max(0, int(row.get("unevaluated", 0)))

    if priority == "CRITICAL_CORRECTIVE_REVIEW" and regressed < 1:
        raise ValueError("critical corrective review requires at least one REGRESSED outcome")
    if priority == "HIGH_CORRECTIVE_REVIEW" and no_effect < 1:
        raise ValueError("high corrective review requires at least one VERIFIED_NO_EFFECT outcome")
    if priority == "BOUNDED_REINFORCEMENT_REVIEW":
        if improved < 2 or regressed > 0 or no_effect > 0:
            raise ValueError("reinforcement review requires repeated improvements and zero negative outcomes")
        if "REINFORCEMENT_REVIEW" not in actions:
            raise ValueError("reinforcement priority requires REINFORCEMENT_REVIEW action")
    if priority == "EVIDENCE_COLLECTION":
        if unevaluated < 1:
            raise ValueError("evidence collection requires at least one unevaluated tracked outcome")
        if "OUTCOME_EVIDENCE_COLLECTION" not in actions:
            raise ValueError("evidence collection priority requires OUTCOME_EVIDENCE_COLLECTION action")

    row["domain"] = domain
    row["priority_class"] = priority
    row["review_actions"] = actions
    row["rank"] = rank
    return row


def _packet_text(action: str, *, domain: str, kind: str, priority: str) -> tuple[str, str, str]:
    label = kind.replace("_", " ").strip() or "unspecified pattern"
    if action == "ATTENTION_RULE_REVIEW":
        return (
            f"Review HANRI attention rule for {label}",
            f"Review whether HANRI attention routing for {domain}/{kind} should be revised based on verified outcome evidence.",
            "Shadow-test the proposed attention-rule change against the same evidence set and compare coverage, false positives, and missed signals before any adoption.",
        )
    if action == "SKILL_CANDIDATE_REVIEW":
        return (
            f"Review agent skill candidate for {label}",
            f"Review a bounded skill or tool-use improvement for {domain}/{kind}; do not install or activate it.",
            "Prototype only in an isolated agent fixture and require explicit before/after task evidence with no production tool or permission changes.",
        )
    if action == "SYSTEM_IMPROVEMENT_REVIEW":
        return (
            f"Review system improvement for {label}",
            f"Review a bounded system change addressing {domain}/{kind}; no live system mutation is authorized.",
            "Evaluate the candidate in a disposable copy or shadow state with deterministic baseline/candidate metrics and rollback criteria.",
        )
    if action == "OPERATOR_ADVICE_REVIEW":
        return (
            f"Review operator workflow advice for {label}",
            f"Review operator-facing advice for {domain}/{kind} derived from explicit outcomes; advice remains optional and human-decided.",
            "Compare the proposed workflow guidance against recent operator decisions and require explicit ACCEPT/REJECT/REVISE/HOLD feedback.",
        )
    if action == "HANRI_RECOMMENDATION_RULE_REVIEW":
        return (
            f"Review HANRI recommendation rule for {label}",
            f"Review whether HANRI recommendation logic for {domain}/{kind} should change; no self-modification is authorized.",
            "Replay the candidate rule over preserved historical evidence and verify that negative outcomes are reduced without broadening authority.",
        )
    if action == "REINFORCEMENT_REVIEW":
        return (
            f"Review bounded reinforcement for {label}",
            f"Review whether repeated verified improvements for {domain}/{kind} justify preserving or narrowly reinforcing the observed pattern.",
            "Require human review of the repeated positive evidence and test only the narrow observed pattern; automatic generalization remains forbidden.",
        )
    if action == "OUTCOME_EVIDENCE_COLLECTION":
        return (
            f"Collect missing outcome evidence for {label}",
            f"Collect explicit outcome evidence for tracked {domain}/{kind} recommendations before proposing any change.",
            "Bind new evidence to recommendation IDs and outcome statuses; silence, disappearance, or missing data must not be treated as success.",
        )
    raise ValueError(f"unsupported review action={action}")


def _build_packets(*, learning: Mapping[str, Any], policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    emit = set(policy["_emit_priority_classes"])
    allowed = set(policy["_allowed_review_actions"])
    decisions = list(policy["_decision_options"])
    cap = int(policy.get("max_recommendations", 12))

    ordered = sorted(
        (_validate_ranked_row(x) for x in learning.get("ranked_improvements", [])),
        key=lambda r: (int(r["rank"]), str(r.get("domain", "")), str(r.get("kind", ""))),
    )

    packets: list[dict[str, Any]] = []
    for row in ordered:
        if row["priority_class"] not in emit:
            continue

        for action in row["review_actions"]:
            if action not in allowed:
                continue
            title, proposed_change, verification_plan = _packet_text(
                action,
                domain=row["domain"],
                kind=str(row.get("kind", "UNSPECIFIED")),
                priority=row["priority_class"],
            )
            rid = "R39.6-" + canonical_sha256({
                "domain": row["domain"],
                "kind": str(row.get("kind", "UNSPECIFIED")),
                "review_action": action,
            })[:18]

            packets.append({
                "recommendation_id": rid,
                "domain": row["domain"],
                "kind": str(row.get("kind", "UNSPECIFIED")),
                "review_action": action,
                "title": title,
                "proposed_change": proposed_change,
                "verification_plan": verification_plan,
                "source_pattern_id": str(row.get("pattern_id", "")),
                "source_rank": int(row["rank"]),
                "source_priority_class": row["priority_class"],
                "source_priority_score": row.get("priority_score"),
                "source_confidence": str(row.get("confidence", "INSUFFICIENT")),
                "evidence_class": (
                    "MISSING_OUTCOME_EVIDENCE"
                    if row["priority_class"] == "EVIDENCE_COLLECTION"
                    else "EXPLICIT_OUTCOME_PATTERN"
                ),
                "source_recommendation_ids": sorted(str(x) for x in row.get("recommendation_ids", [])),
                "source_evidence_fingerprints": sorted(str(x) for x in row.get("evidence_fingerprints", [])),
                "required_human_decision": True,
                "decision_options": copy.deepcopy(decisions),
                "review_status": "PENDING_HUMAN_REVIEW",
                "authority": "PROPOSAL_ONLY",
                "execution_authority": "NONE",
                "shadow_test_required": True,
                "causation_claimed": False,
                "generalization_authorized": False,
                "self_apply_authorized": False,
                "install_authorized": False,
                "system_write_authorized": False,
                "operator_message_authorized": False,
            })
            if len(packets) >= cap:
                return packets
    return packets


def _summary(packets: list[dict[str, Any]], learning: Mapping[str, Any]) -> dict[str, Any]:
    by_domain = Counter(str(x["domain"]) for x in packets)
    by_action = Counter(str(x["review_action"]) for x in packets)
    corrective = sum(
        1 for x in packets
        if str(x["source_priority_class"]) in {"CRITICAL_CORRECTIVE_REVIEW", "HIGH_CORRECTIVE_REVIEW"}
    )
    evidence = sum(1 for x in packets if str(x["source_priority_class"]) == "EVIDENCE_COLLECTION")
    reinforcement = sum(
        1 for x in packets if str(x["source_priority_class"]) == "BOUNDED_REINFORCEMENT_REVIEW"
    )

    if not packets:
        status = "NO_RECOMMENDATIONS_YET"
    elif corrective:
        status = "CORRECTIVE_REVIEW_PACKETS_READY"
    elif evidence:
        status = "EVIDENCE_COLLECTION_PACKETS_READY"
    elif reinforcement:
        status = "REINFORCEMENT_REVIEW_PACKETS_READY"
    else:
        status = "REVIEW_PACKETS_READY"

    return {
        "recommendation_count": len(packets),
        "recommendation_status": status,
        "corrective_review_packets": corrective,
        "evidence_collection_packets": evidence,
        "reinforcement_review_packets": reinforcement,
        "by_domain": {d: int(by_domain.get(d, 0)) for d in DOMAINS},
        "by_review_action": dict(sorted(by_action.items())),
        "source_ranked_improvement_count": len(list(learning.get("ranked_improvements", []))),
    }


def _next_attention(packets: list[dict[str, Any]], learning: Mapping[str, Any]) -> dict[str, Any]:
    if any(str(x["source_priority_class"]) in {"CRITICAL_CORRECTIVE_REVIEW", "HIGH_CORRECTIVE_REVIEW"} for x in packets):
        return {
            "mode": "HUMAN_CORRECTIVE_REVIEW",
            "reason": "explicit negative outcomes produced bounded review packets; human decision remains required",
        }
    if any(str(x["source_priority_class"]) == "EVIDENCE_COLLECTION" for x in packets):
        return {
            "mode": "COLLECT_OUTCOME_EVIDENCE",
            "reason": "tracked recommendations lack explicit outcome evidence; collect evidence before change advice",
        }
    if any(str(x["source_priority_class"]) == "BOUNDED_REINFORCEMENT_REVIEW" for x in packets):
        return {
            "mode": "HUMAN_REINFORCEMENT_REVIEW",
            "reason": "repeated verified improvements support bounded human review only",
        }
    source_next = dict(learning.get("next_attention", {}))
    return {
        "mode": str(source_next.get("mode", "WAIT_FOR_RECOMMENDATION_OUTCOMES")),
        "reason": "no bounded change recommendation packet is justified by current verified learning evidence",
    }


def run_bounded_improvement_recommendations(
    *,
    learning_state: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if not str(generated_at).strip():
        raise ValueError("generated_at is required")

    learning = _verify_learning_state(learning_state)
    prior = _verify_prior_state(prior_state)
    p = _policy(policy)

    source_digest = str(learning["learning_digest"])
    prior_digest = str((prior or {}).get("source_learning_digest", ""))
    semantic_delta = source_digest != prior_digest
    transition = "SEMANTIC_DELTA" if semantic_delta else "NO_DELTA"

    packets = _build_packets(learning=learning, policy=p)
    summary = _summary(packets, learning)
    next_attention = _next_attention(packets, learning)

    recommendation_digest = canonical_sha256({
        "source_learning_digest": source_digest,
        "recommendations": packets,
        "recommendation_summary": summary,
        "next_attention": next_attention,
    })

    history = copy.deepcopy(list((prior or {}).get("history_tail", [])))
    if semantic_delta:
        history.append({
            "generated_at": generated_at,
            "source_learning_digest": source_digest,
            "source_semantic_cycle": int(learning.get("source_semantic_cycle", 0)),
            "recommendation_status": summary["recommendation_status"],
            "recommendation_count": summary["recommendation_count"],
            "corrective_review_packets": summary["corrective_review_packets"],
            "evidence_collection_packets": summary["evidence_collection_packets"],
            "reinforcement_review_packets": summary["reinforcement_review_packets"],
            "next_attention_mode": next_attention["mode"],
        })
    history = history[-max(1, int(p.get("max_history_tail", 20))):]

    effect_boundary = _safe_effect_boundary()
    state = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "source_learning_policy_version": SOURCE_POLICY_VERSION,
        "source_learning_state_sha256": str(learning.get("state_sha256", "")),
        "source_learning_digest": source_digest,
        "source_semantic_cycle": int(learning.get("source_semantic_cycle", 0)),
        "transition": transition,
        "recommendation_summary": summary,
        "recommendations": packets,
        "next_attention": next_attention,
        "history_tail": history,
        "recommendation_digest": recommendation_digest,
        "effect_boundary": effect_boundary,
        "execution_effects_performed": 0,
    }
    state["state_sha256"] = canonical_sha256(state)

    top_n = max(1, int(p.get("receipt_top_n", 5)))
    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "status": "PASS",
        "source_learning_state_sha256": state["source_learning_state_sha256"],
        "source_learning_digest": source_digest,
        "source_semantic_cycle": state["source_semantic_cycle"],
        "transition": transition,
        "recommendation_summary": copy.deepcopy(summary),
        "recommendation_count": len(packets),
        "top_recommendations": copy.deepcopy(packets[:top_n]),
        "next_attention": copy.deepcopy(next_attention),
        "recommendation_digest": recommendation_digest,
        "state_sha256": state["state_sha256"],
        "effect_boundary": copy.deepcopy(effect_boundary),
        "execution_effects_performed": 0,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"state": state, "receipt": receipt}


__all__ = [
    "POLICY_VERSION",
    "SOURCE_POLICY_VERSION",
    "run_bounded_improvement_recommendations",
]
