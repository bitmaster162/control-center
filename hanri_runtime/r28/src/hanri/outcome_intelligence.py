from __future__ import annotations

import copy
from collections import Counter, defaultdict
from typing import Any, Mapping

from hanri.attention_governor import DOMAINS, canonical_sha256

POLICY_VERSION = "39.4.0-outcome-intelligence-v1"
LOOP_POLICY_VERSION = "39.3.1-continuous-attention-loop-v2"
EVIDENCE_HASH_ALGORITHM = "SEMANTIC_ENVELOPE_V2"

POSITIVE = {"VERIFIED_IMPROVED"}
NEGATIVE = {"VERIFIED_NO_EFFECT", "REGRESSED"}
NON_EVALUATIVE = {"UNKNOWN"}
ALLOWED_STATUSES = POSITIVE | NEGATIVE | NON_EVALUATIVE

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
    if bool(boundary.get("can_trade", False)):
        raise ValueError(f"{context}: can_trade must remain false")
    if str(boundary.get("capital_permission", "DENY")).upper() != "DENY":
        raise ValueError(f"{context}: capital_permission must remain DENY")
    for key in _EFFECT_FALSE_KEYS:
        if bool(boundary.get(key, False)):
            raise ValueError(f"{context}: {key} must remain false")


def _verify_loop_state(loop_state: Mapping[str, Any]) -> dict[str, Any]:
    state = copy.deepcopy(dict(loop_state))
    if str(state.get("policy_version", "")) != LOOP_POLICY_VERSION:
        raise ValueError("R39.3.1 loop state required")
    if str(state.get("evidence_hash_algorithm", "")) != EVIDENCE_HASH_ALGORITHM:
        raise ValueError("SEMANTIC_ENVELOPE_V2 loop state required")
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("loop state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="loop_state")
    return state


def _verify_prior_state(prior_state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not prior_state:
        return None
    state = copy.deepcopy(dict(prior_state))
    if str(state.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError("prior outcome-intelligence state policy_version mismatch")
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("prior outcome-intelligence state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="prior_state")
    return state


def _extract_explicit_outcomes(producer_bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_recommendation: dict[str, dict[str, Any]] = {}
    for raw in producer_bundle.get("envelopes", []):
        env = dict(raw)
        if str(env.get("source_type", "")).upper() != "RECOMMENDATION_OUTCOME":
            continue
        payload = dict(env.get("payload", {}))
        recommendation_id = str(payload.get("recommendation_id", "")).strip()
        status = str(payload.get("status", "UNKNOWN")).strip().upper()
        if not recommendation_id:
            raise ValueError("recommendation outcome requires recommendation_id")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"unsupported recommendation outcome status: {status}")

        evidence_refs = sorted({str(x).strip() for x in env.get("evidence_refs", []) if str(x).strip()})
        if status in POSITIVE | NEGATIVE and not evidence_refs:
            raise ValueError(f"verified outcome {recommendation_id} requires explicit evidence_refs")

        row = {
            "recommendation_id": recommendation_id,
            "status": status,
            "evidence_refs": evidence_refs,
            "evidence_fingerprint": canonical_sha256(evidence_refs),
        }
        existing = by_recommendation.get(recommendation_id)
        if existing is not None:
            if existing["status"] != status:
                raise ValueError(f"conflicting current outcomes for recommendation_id={recommendation_id}")
            merged_refs = sorted(set(existing["evidence_refs"]) | set(evidence_refs))
            existing["evidence_refs"] = merged_refs
            existing["evidence_fingerprint"] = canonical_sha256(merged_refs)
            continue
        by_recommendation[recommendation_id] = row

    return [by_recommendation[k] for k in sorted(by_recommendation)]


def _proposal_meta(loop_state: Mapping[str, Any], recommendation_id: str) -> dict[str, Any] | None:
    raw = dict(loop_state.get("proposal_memory", {})).get(recommendation_id)
    if not isinstance(raw, Mapping):
        return None
    item = dict(raw)
    domain = str(item.get("domain", "")).upper()
    if domain not in DOMAINS:
        raise ValueError(f"tracked recommendation {recommendation_id} has invalid domain: {domain}")
    return {
        "recommendation_id": recommendation_id,
        "domain": domain,
        "kind": str(item.get("kind", "")),
        "subject_id": str(item.get("subject_id", "")),
        "signal": str(item.get("signal", "")),
        "proposal_fingerprint": str(item.get("proposal_fingerprint", "")),
    }


def _update_records(
    *,
    prior_records: Mapping[str, Any],
    loop_state: Mapping[str, Any],
    outcomes: list[dict[str, Any]],
    semantic_cycle: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    records = copy.deepcopy(dict(prior_records))
    transitions: list[dict[str, Any]] = []
    orphan_ids: list[str] = []

    for outcome in outcomes:
        rid = outcome["recommendation_id"]
        meta = _proposal_meta(loop_state, rid)
        if meta is None:
            orphan_ids.append(rid)
            continue

        previous = dict(records.get(rid, {})) if isinstance(records.get(rid), Mapping) else {}
        previous_status = str(previous.get("current_status", "")).upper()
        evidence_fingerprints = sorted(set(previous.get("evidence_fingerprints", [])) | {outcome["evidence_fingerprint"]})
        status = outcome["status"]

        status_changed = bool(previous_status) and previous_status != status
        first_observation = not previous_status
        if first_observation or status_changed:
            transitions.append({
                "recommendation_id": rid,
                "from_status": previous_status or None,
                "to_status": status,
                "semantic_cycle": semantic_cycle,
                "evidence_fingerprint": outcome["evidence_fingerprint"],
            })

        records[rid] = {
            **meta,
            "current_status": status,
            "evaluated": status in POSITIVE | NEGATIVE,
            "negative": status in NEGATIVE,
            "positive": status in POSITIVE,
            "last_seen_semantic_cycle": semantic_cycle,
            "evidence_fingerprints": evidence_fingerprints[-10:],
            "evidence_observation_count": len(evidence_fingerprints[-10:]),
            "status_transition_count": int(previous.get("status_transition_count", 0)) + (1 if first_observation or status_changed else 0),
        }

    return dict(sorted(records.items())), transitions, sorted(set(orphan_ids))


def _metrics(loop_state: Mapping[str, Any], records: Mapping[str, Any], orphan_ids: list[str]) -> dict[str, Any]:
    tracked = dict(loop_state.get("proposal_memory", {}))
    tracked_ids = sorted(tracked)
    known_records = {rid: dict(rec) for rid, rec in records.items() if rid in tracked}

    counts = Counter(str(rec.get("current_status", "UNKNOWN")).upper() for rec in known_records.values())
    evaluated_ids = sorted(
        rid for rid, rec in known_records.items()
        if str(rec.get("current_status", "")).upper() in POSITIVE | NEGATIVE
    )
    evaluated_count = len(evaluated_ids)
    improved = counts["VERIFIED_IMPROVED"]
    no_effect = counts["VERIFIED_NO_EFFECT"]
    regressed = counts["REGRESSED"]

    unevaluated_ids = sorted(
        rid for rid in tracked_ids
        if rid not in known_records or str(known_records[rid].get("current_status", "UNKNOWN")).upper() not in POSITIVE | NEGATIVE
    )
    coverage_rate = (evaluated_count / len(tracked_ids)) if tracked_ids else 1.0
    effectiveness_rate = (improved / evaluated_count) if evaluated_count else None
    adverse_rate = (regressed / evaluated_count) if evaluated_count else None

    per_domain: dict[str, dict[str, Any]] = {}
    for domain in DOMAINS:
        domain_tracked = [
            rid for rid, row in tracked.items()
            if str(dict(row).get("domain", "")).upper() == domain
        ]
        domain_eval = [rid for rid in domain_tracked if rid in evaluated_ids]
        dcounts = Counter(
            str(known_records[rid].get("current_status", "UNKNOWN")).upper()
            for rid in domain_eval
        )
        per_domain[domain] = {
            "tracked": len(domain_tracked),
            "evaluated": len(domain_eval),
            "verified_improved": dcounts["VERIFIED_IMPROVED"],
            "verified_no_effect": dcounts["VERIFIED_NO_EFFECT"],
            "regressed": dcounts["REGRESSED"],
            "outcome_coverage_rate": (len(domain_eval) / len(domain_tracked)) if domain_tracked else 1.0,
        }

    return {
        "tracked_recommendations": len(tracked_ids),
        "evaluated_recommendations": evaluated_count,
        "verified_improved": improved,
        "verified_no_effect": no_effect,
        "regressed": regressed,
        "unknown_or_unevaluated": len(unevaluated_ids),
        "orphan_outcomes": len(orphan_ids),
        "orphan_recommendation_ids": orphan_ids,
        "unevaluated_recommendation_ids": unevaluated_ids,
        "outcome_coverage_rate": coverage_rate,
        "effectiveness_rate": effectiveness_rate,
        "adverse_rate": adverse_rate,
        "per_domain": per_domain,
    }


def _candidate_id(payload: Mapping[str, Any]) -> str:
    return "R39.4-" + canonical_sha256(payload)[:18]


def _review_kind(domain: str) -> str:
    return {
        "SELF": "ATTENTION_RULE_REVIEW",
        "AGENT": "SKILL_CANDIDATE_REVIEW",
        "SYSTEM": "SYSTEM_IMPROVEMENT_REVIEW",
        "OPERATOR": "OPERATOR_ADVICE_REVIEW",
    }.get(domain, "RECOMMENDATION_RULE_REVIEW")


def _learning_candidates(
    *,
    records: Mapping[str, Any],
    metrics: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for rid, raw in sorted(records.items()):
        rec = dict(raw)
        status = str(rec.get("current_status", "")).upper()
        if status not in NEGATIVE:
            continue
        domain = str(rec.get("domain", "")).upper()
        base = {
            "candidate_type": _review_kind(domain),
            "recommendation_id": rid,
            "source_domain": domain,
            "source_kind": str(rec.get("kind", "")),
            "subject_id": str(rec.get("subject_id", "")),
            "signal": str(rec.get("signal", "")),
            "outcome_status": status,
            "evidence_fingerprints": list(rec.get("evidence_fingerprints", [])),
            "authority": "PROPOSAL_ONLY",
            "requires_human_acceptance": True,
            "self_apply_authorized": False,
            "install_authorized": False,
        }
        base["candidate_id"] = _candidate_id(base)
        candidates.append(base)

        meta = {
            "candidate_type": "HANRI_RECOMMENDATION_RULE_REVIEW",
            "recommendation_id": rid,
            "source_domain": domain,
            "source_kind": str(rec.get("kind", "")),
            "outcome_status": status,
            "objective": "compare failed recommendation logic against explicit outcome evidence before reuse",
            "authority": "PROPOSAL_ONLY",
            "requires_human_acceptance": True,
            "self_apply_authorized": False,
        }
        meta["candidate_id"] = _candidate_id(meta)
        candidates.append(meta)

    threshold = max(2, int(policy.get("reinforcement_min_verified_improved", 2)))
    groups: dict[tuple[str, str], Counter] = defaultdict(Counter)
    group_ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rid, raw in records.items():
        rec = dict(raw)
        status = str(rec.get("current_status", "")).upper()
        if status not in POSITIVE | NEGATIVE:
            continue
        key = (str(rec.get("domain", "")).upper(), str(rec.get("kind", "")))
        groups[key][status] += 1
        group_ids[key].append(rid)

    for (domain, kind), counts in sorted(groups.items()):
        positive_count = counts["VERIFIED_IMPROVED"]
        negative_count = counts["VERIFIED_NO_EFFECT"] + counts["REGRESSED"]
        if positive_count < threshold or negative_count:
            continue
        base = {
            "candidate_type": "REINFORCEMENT_REVIEW",
            "source_domain": domain,
            "source_kind": kind,
            "verified_improved_count": positive_count,
            "negative_count": negative_count,
            "recommendation_ids": sorted(group_ids[(domain, kind)]),
            "confidence": "BOUNDED",
            "generalization_authorized": False,
            "authority": "PROPOSAL_ONLY",
            "requires_human_acceptance": True,
            "self_apply_authorized": False,
            "install_authorized": False,
        }
        base["candidate_id"] = _candidate_id(base)
        candidates.append(base)

    min_tracked = max(1, int(policy.get("outcome_debt_min_tracked", 2)))
    min_coverage = float(policy.get("min_outcome_coverage_rate", 0.50))
    if int(metrics["tracked_recommendations"]) >= min_tracked and float(metrics["outcome_coverage_rate"]) < min_coverage:
        base = {
            "candidate_type": "OUTCOME_EVIDENCE_COLLECTION",
            "unevaluated_recommendation_ids": list(metrics["unevaluated_recommendation_ids"]),
            "current_outcome_coverage_rate": float(metrics["outcome_coverage_rate"]),
            "target_outcome_coverage_rate": min_coverage,
            "authority": "PROPOSAL_ONLY",
            "requires_human_acceptance": False,
            "collection_only": True,
            "external_messages_authorized": False,
            "self_apply_authorized": False,
        }
        base["candidate_id"] = _candidate_id(base)
        candidates.append(base)

    candidates.sort(key=lambda x: (str(x["candidate_type"]), str(x["candidate_id"])))
    return candidates


def _next_attention(
    *,
    records: Mapping[str, Any],
    metrics: Mapping[str, Any],
    candidates: list[dict[str, Any]],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    negative = [dict(r) for r in records.values() if str(dict(r).get("current_status", "")).upper() in NEGATIVE]
    if negative:
        affected = sorted({
            str(r.get("domain", "")).upper()
            for r in negative
            if str(r.get("domain", "")).upper() in DOMAINS
        })
        return {
            "mode": "OUTCOME_FAILURE_REVIEW",
            "focus_domains": ["SELF"] + [d for d in affected if d != "SELF"],
            "reason": "explicit negative recommendation outcomes require recommendation-rule review before reuse",
        }

    min_tracked = max(1, int(policy.get("outcome_debt_min_tracked", 2)))
    min_coverage = float(policy.get("min_outcome_coverage_rate", 0.50))
    if int(metrics["tracked_recommendations"]) >= min_tracked and float(metrics["outcome_coverage_rate"]) < min_coverage:
        domains = [
            domain for domain, row in dict(metrics["per_domain"]).items()
            if float(dict(row).get("outcome_coverage_rate", 1.0)) < min_coverage
        ]
        return {
            "mode": "OUTCOME_EVIDENCE_GAP",
            "focus_domains": domains or ["SELF"],
            "reason": "too many tracked recommendations lack explicit outcome evidence",
        }

    if any(str(c.get("candidate_type")) == "REINFORCEMENT_REVIEW" for c in candidates):
        return {
            "mode": "REINFORCEMENT_REVIEW",
            "focus_domains": sorted({
                str(c.get("source_domain", "SELF"))
                for c in candidates
                if str(c.get("candidate_type")) == "REINFORCEMENT_REVIEW"
            }),
            "reason": "repeated verified improvements support bounded reinforcement review, not automatic generalization",
        }

    return {
        "mode": "OUTCOME_MONITORING",
        "focus_domains": ["SELF", "AGENT", "SYSTEM", "OPERATOR"],
        "reason": "continue collecting explicit outcome evidence without inferring success from disappearance or silence",
    }


def run_outcome_intelligence(
    *,
    loop_state: Mapping[str, Any],
    producer_bundle: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if str(policy.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    if not str(generated_at).strip():
        raise ValueError("generated_at is required")
    _require_safe_boundary(dict(policy.get("effect_boundary", {})), context="policy")

    loop = _verify_loop_state(loop_state)
    prior = _verify_prior_state(prior_state)
    outcomes = _extract_explicit_outcomes(producer_bundle)
    semantic_cycle = int(loop.get("semantic_cycle_count", 0))

    records, transitions, orphan_ids = _update_records(
        prior_records=dict(prior.get("outcome_records", {})) if prior else {},
        loop_state=loop,
        outcomes=outcomes,
        semantic_cycle=semantic_cycle,
    )
    metrics = _metrics(loop, records, orphan_ids)
    candidates = _learning_candidates(records=records, metrics=metrics, policy=policy)
    next_attention = _next_attention(records=records, metrics=metrics, candidates=candidates, policy=policy)

    history_tail = copy.deepcopy(list(prior.get("history_tail", []))) if prior else []
    history_tail.append({
        "semantic_cycle": semantic_cycle,
        "loop_state_sha256": str(loop.get("state_sha256", "")),
        "explicit_outcome_count": len(outcomes),
        "evaluated_recommendations": int(metrics["evaluated_recommendations"]),
        "outcome_coverage_rate": metrics["outcome_coverage_rate"],
        "negative_recommendations": int(metrics["verified_no_effect"]) + int(metrics["regressed"]),
        "learning_candidate_count": len(candidates),
        "next_attention_mode": next_attention["mode"],
    })
    max_history = max(1, int(policy.get("max_history_tail", 20)))
    history_tail = history_tail[-max_history:]

    effect_boundary = _safe_effect_boundary()
    intelligence_digest = canonical_sha256({
        "loop_state_sha256": str(loop.get("state_sha256", "")),
        "outcome_records": records,
        "metrics": metrics,
        "learning_candidates": candidates,
        "next_attention": next_attention,
    })

    state = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "source_loop_policy_version": LOOP_POLICY_VERSION,
        "source_loop_state_sha256": str(loop.get("state_sha256", "")),
        "source_semantic_cycle": semantic_cycle,
        "outcome_records": records,
        "metrics": metrics,
        "learning_candidates": candidates,
        "next_attention": next_attention,
        "intelligence_digest": intelligence_digest,
        "history_tail": history_tail,
        "effect_boundary": effect_boundary,
    }
    state["state_sha256"] = canonical_sha256(state)

    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "source_loop_state_sha256": state["source_loop_state_sha256"],
        "source_semantic_cycle": semantic_cycle,
        "explicit_outcome_count": len(outcomes),
        "new_status_transition_count": len(transitions),
        "status_transitions": transitions,
        "metrics": copy.deepcopy(metrics),
        "learning_candidate_count": len(candidates),
        "learning_candidate_types": sorted({str(x["candidate_type"]) for x in candidates}),
        "next_attention": copy.deepcopy(next_attention),
        "intelligence_digest": intelligence_digest,
        "state_sha256": state["state_sha256"],
        "effect_boundary": copy.deepcopy(effect_boundary),
        "execution_effects_performed": 0,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"state": state, "receipt": receipt}


__all__ = [
    "POLICY_VERSION",
    "LOOP_POLICY_VERSION",
    "EVIDENCE_HASH_ALGORITHM",
    "run_outcome_intelligence",
]
