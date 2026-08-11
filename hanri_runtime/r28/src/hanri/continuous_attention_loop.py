from __future__ import annotations

import copy
from typing import Any, Mapping

from hanri.attention_governor import DOMAINS, canonical_sha256

POLICY_VERSION = "39.3.0-continuous-attention-loop-v1"
NEGATIVE_OUTCOMES = {"VERIFIED_NO_EFFECT", "REGRESSED"}
POSITIVE_OUTCOMES = {"VERIFIED_IMPROVED"}


def _without_hash(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in payload.items() if k != key}


def _require_safe_boundary(boundary: Mapping[str, Any], *, context: str) -> None:
    if bool(boundary.get("can_trade", False)):
        raise ValueError(f"{context}: can_trade must remain false")
    if str(boundary.get("capital_permission", "DENY")).upper() != "DENY":
        raise ValueError(f"{context}: capital_permission must remain DENY")
    for key in ("self_apply", "skill_install", "system_write", "operator_message", "auto_dispatch", "external_messages"):
        if bool(boundary.get(key, False)):
            raise ValueError(f"{context}: {key} must remain false")


def _verify_prior_state(prior_state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not prior_state:
        return None
    state = copy.deepcopy(dict(prior_state))
    if str(state.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError("prior state policy_version mismatch")
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("prior state SHA mismatch")
    _require_safe_boundary(dict(state.get("effect_boundary", {})), context="prior_state")
    return state


def _validate_fabric(fabric: Mapping[str, Any]) -> None:
    if not str(fabric.get("fabric_run_id", "")).strip():
        raise ValueError("fabric_run_id is required")
    ledger = dict(fabric.get("ledger", {}))
    if not isinstance(ledger.get("envelope_hashes", []), list):
        raise ValueError("fabric ledger envelope_hashes must be a list")
    _require_safe_boundary(dict(fabric.get("effect_boundary", {})), context="fabric")


def _evidence_set_sha256(fabric: Mapping[str, Any]) -> str:
    rows = []
    for row in fabric.get("ledger", {}).get("envelope_hashes", []):
        item = dict(row)
        envelope_id = str(item.get("envelope_id", "")).strip()
        sha256 = str(item.get("sha256", "")).strip().lower()
        source_type = str(item.get("source_type", "")).strip().upper()
        if not envelope_id or len(sha256) != 64:
            raise ValueError("invalid envelope hash row")
        rows.append({"envelope_id": envelope_id, "sha256": sha256, "source_type": source_type})
    rows.sort(key=lambda x: (x["envelope_id"], x["sha256"], x["source_type"]))
    return canonical_sha256(rows)


def _extract_outcomes(producer_bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for raw in producer_bundle.get("envelopes", []):
        env = dict(raw)
        if str(env.get("source_type", "")).upper() != "RECOMMENDATION_OUTCOME":
            continue
        payload = dict(env.get("payload", {}))
        recommendation_id = str(payload.get("recommendation_id", "")).strip()
        status = str(payload.get("status", "UNKNOWN")).strip().upper()
        if not recommendation_id:
            raise ValueError("recommendation outcome requires recommendation_id")
        evidence_refs = sorted({str(x) for x in env.get("evidence_refs", []) if str(x).strip()})
        outcomes.append({
            "recommendation_id": recommendation_id,
            "status": status,
            "evidence_fingerprint": canonical_sha256(evidence_refs),
        })
    outcomes.sort(key=lambda x: (x["recommendation_id"], x["status"], x["evidence_fingerprint"]))
    return outcomes


def _bounded_proposal_record(proposal: Mapping[str, Any], semantic_cycle: int) -> dict[str, Any]:
    return {
        "proposal_id": str(proposal.get("proposal_id", "")),
        "kind": str(proposal.get("kind", "")),
        "domain": str(proposal.get("domain", "")),
        "subject_id": str(proposal.get("subject_id", "")),
        "signal": str(proposal.get("signal", "")),
        "proposal_fingerprint": canonical_sha256(proposal),
        "first_seen_semantic_cycle": semantic_cycle,
        "last_seen_semantic_cycle": semantic_cycle,
        "seen_semantic_cycles": 1,
        "currently_present": True,
        "status": "PROPOSAL_ONLY",
    }


def _update_proposal_memory(
    prior_memory: Mapping[str, Any],
    proposals: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    *,
    semantic_cycle: int,
    semantic_delta: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    memory = copy.deepcopy(dict(prior_memory))
    outcome_memory: dict[str, Any] = {}

    if semantic_delta:
        for record in memory.values():
            if isinstance(record, dict):
                record["currently_present"] = False

        for proposal in proposals:
            proposal_id = str(proposal.get("proposal_id", "")).strip()
            if not proposal_id:
                raise ValueError("proposal_id is required")
            fingerprint = canonical_sha256(proposal)
            if proposal_id not in memory:
                memory[proposal_id] = _bounded_proposal_record(proposal, semantic_cycle)
            else:
                record = dict(memory[proposal_id])
                record["kind"] = str(proposal.get("kind", record.get("kind", "")))
                record["domain"] = str(proposal.get("domain", record.get("domain", "")))
                record["subject_id"] = str(proposal.get("subject_id", record.get("subject_id", "")))
                record["signal"] = str(proposal.get("signal", record.get("signal", "")))
                record["proposal_fingerprint"] = fingerprint
                record["last_seen_semantic_cycle"] = semantic_cycle
                record["seen_semantic_cycles"] = int(record.get("seen_semantic_cycles", 0)) + 1
                record["currently_present"] = True
                if str(record.get("status", "")) == "NOT_CURRENTLY_OBSERVED":
                    record["status"] = "PROPOSAL_ONLY"
                memory[proposal_id] = record

        for proposal_id, record_raw in list(memory.items()):
            record = dict(record_raw)
            if not bool(record.get("currently_present", False)) and str(record.get("status", "")) == "PROPOSAL_ONLY":
                record["status"] = "NOT_CURRENTLY_OBSERVED"
                memory[proposal_id] = record

    for outcome in outcomes:
        recommendation_id = str(outcome["recommendation_id"])
        status = str(outcome["status"])
        outcome_memory[recommendation_id] = {
            "status": status,
            "evidence_fingerprint": str(outcome["evidence_fingerprint"]),
            "last_seen_semantic_cycle": semantic_cycle,
        }
        if recommendation_id in memory:
            record = dict(memory[recommendation_id])
            if status in NEGATIVE_OUTCOMES:
                record["status"] = "NEEDS_SELF_REVIEW"
            elif status in POSITIVE_OUTCOMES:
                record["status"] = "VERIFIED_IMPROVED"
            else:
                record["status"] = status
            memory[recommendation_id] = record

    return dict(sorted(memory.items())), dict(sorted(outcome_memory.items()))


def _merge_outcome_memory(prior: Mapping[str, Any], current: Mapping[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(dict(prior))
    for key, value in current.items():
        merged[str(key)] = copy.deepcopy(value)
    return dict(sorted(merged.items()))


def _update_domain_memory(
    prior: Mapping[str, Any],
    counts: Mapping[str, Any],
    *,
    semantic_cycle: int,
    semantic_delta: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for domain in DOMAINS:
        previous = dict(prior.get(domain, {})) if isinstance(prior.get(domain, {}), Mapping) else {}
        covered = int(counts.get(domain, 0)) > 0
        if semantic_delta:
            if covered:
                consecutive = int(previous.get("consecutive_covered_semantic_cycles", 0)) + 1
                total = int(previous.get("total_covered_semantic_cycles", 0)) + 1
                last = semantic_cycle
            else:
                consecutive = 0
                total = int(previous.get("total_covered_semantic_cycles", 0))
                last = previous.get("last_covered_semantic_cycle")
        else:
            consecutive = int(previous.get("consecutive_covered_semantic_cycles", 0))
            total = int(previous.get("total_covered_semantic_cycles", 0))
            last = previous.get("last_covered_semantic_cycle")
        out[domain] = {
            "currently_covered": covered,
            "current_attention_records": int(counts.get(domain, 0)),
            "consecutive_covered_semantic_cycles": consecutive,
            "total_covered_semantic_cycles": total,
            "last_covered_semantic_cycle": last,
        }
    return out


def _next_attention(
    *,
    coverage_complete: bool,
    blind_spots: list[str],
    domain_counts: Mapping[str, Any],
    proposals: list[dict[str, Any]],
    unresolved_negative_outcomes: list[str],
    no_delta_streak: int,
    refresh_threshold: int,
) -> dict[str, Any]:
    if unresolved_negative_outcomes:
        return {
            "mode": "SELF_REVIEW_REQUIRED",
            "focus_domains": ["SELF"],
            "reason": "negative recommendation outcome remains unresolved",
        }
    if not coverage_complete:
        return {
            "mode": "COVERAGE_REPAIR_REQUIRED",
            "focus_domains": sorted(set(blind_spots)),
            "reason": "one or more attention domains lack evidence-backed coverage",
        }
    if proposals:
        focus = []
        for proposal in proposals:
            domain = str(proposal.get("domain", "")).upper()
            if domain in DOMAINS and domain not in focus:
                focus.append(domain)
        return {
            "mode": "IMPROVEMENT_REVIEW",
            "focus_domains": focus or ["SELF"],
            "reason": "current material findings generated bounded improvement proposals",
        }

    positive_counts = {domain: max(0, int(domain_counts.get(domain, 0))) for domain in DOMAINS}
    minimum = min(positive_counts.values()) if positive_counts else 0
    under_observed = [domain for domain in DOMAINS if positive_counts[domain] == minimum]
    if no_delta_streak >= refresh_threshold:
        return {
            "mode": "EVIDENCE_REFRESH_FOCUS",
            "focus_domains": under_observed,
            "reason": "repeated no-delta wakes; refresh under-observed evidence before assuming stability",
        }
    return {
        "mode": "MAINTAIN_BALANCED_COVERAGE",
        "focus_domains": under_observed,
        "reason": "coverage is complete with no material findings; bias the next audit toward the least-observed domains",
    }


def advance_continuous_attention_loop(
    *,
    producer_bundle: Mapping[str, Any],
    fabric_result: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if str(policy.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    if not str(generated_at).strip():
        raise ValueError("generated_at is required")
    prior = _verify_prior_state(prior_state)
    _validate_fabric(fabric_result)

    evidence_set_sha256 = _evidence_set_sha256(fabric_result)
    previous_evidence_sha = str(prior.get("last_evidence_set_sha256", "")) if prior else ""
    same_evidence = bool(prior) and previous_evidence_sha == evidence_set_sha256

    wake_index = int(prior.get("wake_count", 0)) + 1 if prior else 1
    previous_semantic_cycle = int(prior.get("semantic_cycle_count", 0)) if prior else 0
    semantic_delta = not same_evidence
    semantic_cycle = previous_semantic_cycle + 1 if semantic_delta else previous_semantic_cycle
    transition = "INITIALIZED" if prior is None else ("NO_DELTA" if same_evidence else "SEMANTIC_DELTA")
    no_delta_streak = int(prior.get("no_delta_streak", 0)) + 1 if same_evidence else 0

    summary = dict(fabric_result.get("attention_summary", {}))
    coverage_complete = bool(summary.get("coverage_complete", False))
    blind_spots = sorted({str(x) for x in summary.get("blind_spots", []) if str(x).strip()})
    domain_counts = {domain: int(dict(summary.get("domain_counts", {})).get(domain, 0)) for domain in DOMAINS}
    proposals = [copy.deepcopy(dict(x)) for x in fabric_result.get("prioritized_proposals", [])]
    proposals.sort(key=lambda x: str(x.get("proposal_id", "")))
    outcomes = _extract_outcomes(producer_bundle)

    proposal_memory, current_outcome_memory = _update_proposal_memory(
        dict(prior.get("proposal_memory", {})) if prior else {},
        proposals,
        outcomes,
        semantic_cycle=semantic_cycle,
        semantic_delta=semantic_delta,
    )
    outcome_memory = _merge_outcome_memory(dict(prior.get("outcome_memory", {})) if prior else {}, current_outcome_memory)
    unresolved_negative = sorted(
        rid for rid, item in outcome_memory.items()
        if str(dict(item).get("status", "")).upper() in NEGATIVE_OUTCOMES
    )

    domain_memory = _update_domain_memory(
        dict(prior.get("domain_memory", {})) if prior else {},
        domain_counts,
        semantic_cycle=semantic_cycle,
        semantic_delta=semantic_delta,
    )
    refresh_threshold = max(1, int(policy.get("no_delta_refresh_threshold", 3)))
    next_attention = _next_attention(
        coverage_complete=coverage_complete,
        blind_spots=blind_spots,
        domain_counts=domain_counts,
        proposals=proposals,
        unresolved_negative_outcomes=unresolved_negative,
        no_delta_streak=no_delta_streak,
        refresh_threshold=refresh_threshold,
    )

    history_tail = copy.deepcopy(list(prior.get("history_tail", []))) if prior else []
    history_tail.append({
        "wake_index": wake_index,
        "semantic_cycle": semantic_cycle,
        "transition": transition,
        "evidence_set_sha256": evidence_set_sha256,
        "coverage_complete": coverage_complete,
        "blind_spots": blind_spots,
        "proposal_count": len(proposals),
        "outcome_count": len(outcomes),
        "next_attention_mode": next_attention["mode"],
    })
    max_history = max(1, int(policy.get("max_history_tail", 20)))
    history_tail = history_tail[-max_history:]

    semantic_digest = canonical_sha256({
        "evidence_set_sha256": evidence_set_sha256,
        "semantic_cycle": semantic_cycle,
        "coverage_complete": coverage_complete,
        "blind_spots": blind_spots,
        "domain_counts": domain_counts,
        "proposal_memory": proposal_memory,
        "outcome_memory": outcome_memory,
        "next_attention": next_attention,
    })

    effect_boundary = {
        "proposal_only": True,
        "local_state_write_only": True,
        "provider_calls": False,
        "scheduler_install": False,
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

    state = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "loop_id": str(policy.get("loop_id", "HANRI_R39_CONTINUOUS_ATTENTION")),
        "generated_at": generated_at,
        "wake_count": wake_index,
        "semantic_cycle_count": semantic_cycle,
        "no_delta_streak": no_delta_streak,
        "last_transition": transition,
        "last_evidence_set_sha256": evidence_set_sha256,
        "last_fabric_receipt_sha256": str(fabric_result.get("fabric_receipt_sha256", "")),
        "last_producer_bundle_sha256": str(producer_bundle.get("bundle_sha256", "")),
        "coverage": {
            "complete": coverage_complete,
            "blind_spots": blind_spots,
            "domain_counts": domain_counts,
        },
        "domain_memory": domain_memory,
        "proposal_memory": proposal_memory,
        "outcome_memory": outcome_memory,
        "unresolved_negative_outcomes": unresolved_negative,
        "next_attention": next_attention,
        "semantic_digest": semantic_digest,
        "history_tail": history_tail,
        "effect_boundary": effect_boundary,
    }
    state["state_sha256"] = canonical_sha256(state)

    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "loop_id": state["loop_id"],
        "generated_at": generated_at,
        "wake_index": wake_index,
        "semantic_cycle_count": semantic_cycle,
        "transition": transition,
        "semantic_delta": semantic_delta,
        "evidence_set_sha256": evidence_set_sha256,
        "semantic_digest": semantic_digest,
        "coverage_complete": coverage_complete,
        "blind_spots": blind_spots,
        "domain_counts": domain_counts,
        "active_proposal_count": len(proposals),
        "tracked_proposal_count": len(proposal_memory),
        "current_outcome_count": len(outcomes),
        "unresolved_negative_outcomes": unresolved_negative,
        "next_attention": copy.deepcopy(next_attention),
        "no_delta_streak": no_delta_streak,
        "state_sha256": state["state_sha256"],
        "effect_boundary": copy.deepcopy(effect_boundary),
        "execution_effects_performed": 0,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"state": state, "receipt": receipt}


__all__ = [
    "POLICY_VERSION",
    "advance_continuous_attention_loop",
]
