from __future__ import annotations

import copy
from typing import Any, Mapping

from hanri.attention_governor import canonical_sha256
import hanri.outcome_intelligence as _v1

POLICY_VERSION = "39.4.0.1-outcome-intelligence-metric-semantics-v1"
BASE_POLICY_VERSION = _v1.POLICY_VERSION
LOOP_POLICY_VERSION = _v1.LOOP_POLICY_VERSION
EVIDENCE_HASH_ALGORITHM = _v1.EVIDENCE_HASH_ALGORITHM


def _without_hash(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in payload.items() if k != key}


def _verify_prior_state(prior_state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not prior_state:
        return None
    state = copy.deepcopy(dict(prior_state))
    if str(state.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(
            f"legacy_or_foreign_outcome_state_requires_migration expected={POLICY_VERSION} "
            f"actual={state.get('policy_version')}"
        )
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("prior outcome-intelligence state SHA mismatch")
    _v1._require_safe_boundary(dict(state.get("effect_boundary", {})), context="prior_state")
    return state


def _to_v1_state(state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if state is None:
        return None
    converted = copy.deepcopy(dict(state))
    converted["policy_version"] = BASE_POLICY_VERSION
    converted.pop("metric_semantics", None)
    converted["state_sha256"] = canonical_sha256(
        {k: v for k, v in converted.items() if k != "state_sha256"}
    )
    return converted


def _to_v1_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    converted = copy.deepcopy(dict(policy))
    if str(converted.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    converted["policy_version"] = BASE_POLICY_VERSION
    return converted


def _repair_coverage_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    repaired = copy.deepcopy(dict(metrics))
    tracked = int(repaired.get("tracked_recommendations", 0))
    repaired["outcome_coverage_applicable"] = tracked > 0
    repaired["outcome_coverage_status"] = "DEFINED" if tracked > 0 else "NOT_APPLICABLE"
    if tracked == 0:
        repaired["outcome_coverage_rate"] = None

    per_domain = {}
    for domain, raw in dict(repaired.get("per_domain", {})).items():
        row = copy.deepcopy(dict(raw))
        domain_tracked = int(row.get("tracked", 0))
        row["outcome_coverage_applicable"] = domain_tracked > 0
        row["outcome_coverage_status"] = "DEFINED" if domain_tracked > 0 else "NOT_APPLICABLE"
        if domain_tracked == 0:
            row["outcome_coverage_rate"] = None
        per_domain[str(domain)] = row
    repaired["per_domain"] = per_domain
    return repaired


def run_outcome_intelligence_v2(
    *,
    loop_state: Mapping[str, Any],
    producer_bundle: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    prior = _verify_prior_state(prior_state)
    base = _v1.run_outcome_intelligence(
        loop_state=loop_state,
        producer_bundle=producer_bundle,
        prior_state=_to_v1_state(prior),
        policy=_to_v1_policy(policy),
        generated_at=generated_at,
    )

    state = copy.deepcopy(base["state"])
    receipt = copy.deepcopy(base["receipt"])
    metrics = _repair_coverage_metrics(state.get("metrics", {}))

    history_tail = copy.deepcopy(list(state.get("history_tail", [])))
    if history_tail:
        history_tail[-1]["outcome_coverage_rate"] = metrics["outcome_coverage_rate"]
        history_tail[-1]["outcome_coverage_applicable"] = metrics["outcome_coverage_applicable"]
        history_tail[-1]["outcome_coverage_status"] = metrics["outcome_coverage_status"]

    metric_semantics = {
        "zero_denominator": "NOT_APPLICABLE",
        "zero_denominator_numeric_rate": None,
        "zero_tracked_recommendations_never_claims_full_coverage": True,
        "zero_tracked_domain_never_claims_full_coverage": True,
    }

    intelligence_digest = canonical_sha256({
        "loop_state_sha256": str(state.get("source_loop_state_sha256", "")),
        "outcome_records": state.get("outcome_records", {}),
        "metrics": metrics,
        "learning_candidates": state.get("learning_candidates", []),
        "next_attention": state.get("next_attention", {}),
        "metric_semantics": metric_semantics,
    })

    state["policy_version"] = POLICY_VERSION
    state["metrics"] = metrics
    state["history_tail"] = history_tail
    state["metric_semantics"] = metric_semantics
    state["intelligence_digest"] = intelligence_digest
    state["state_sha256"] = canonical_sha256(
        {k: v for k, v in state.items() if k != "state_sha256"}
    )

    receipt["policy_version"] = POLICY_VERSION
    receipt["metrics"] = copy.deepcopy(metrics)
    receipt["metric_semantics"] = copy.deepcopy(metric_semantics)
    receipt["intelligence_digest"] = intelligence_digest
    receipt["state_sha256"] = state["state_sha256"]
    receipt["receipt_sha256"] = canonical_sha256(
        {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    )
    return {"state": state, "receipt": receipt}


__all__ = [
    "POLICY_VERSION",
    "BASE_POLICY_VERSION",
    "LOOP_POLICY_VERSION",
    "EVIDENCE_HASH_ALGORITHM",
    "run_outcome_intelligence_v2",
]
