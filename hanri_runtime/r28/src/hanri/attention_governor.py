from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any, Mapping

DOMAINS = ("SELF", "AGENT", "SYSTEM", "OPERATOR")
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
NEGATIVE_OUTCOMES = {"VERIFIED_NO_EFFECT", "REGRESSED"}
POSITIVE_OUTCOMES = {"VERIFIED_IMPROVED"}


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _proposal_id(kind: str, subject_id: str, signal: str, evidence_refs: list[str]) -> str:
    digest = canonical_sha256({
        "kind": kind,
        "subject_id": subject_id,
        "signal": signal,
        "evidence_refs": sorted(evidence_refs),
    })[:16]
    return f"R39-{kind}-{digest}"


def _base_proposal(*, kind: str, domain: str, subject_id: str, signal: str, summary: str,
                   evidence_refs: list[str], isolate_test_required: bool) -> dict[str, Any]:
    return {
        "proposal_id": _proposal_id(kind, subject_id, signal, evidence_refs),
        "kind": kind,
        "domain": domain,
        "subject_id": subject_id,
        "signal": signal,
        "summary": summary,
        "evidence_refs": sorted(set(evidence_refs)),
        "authority": "PROPOSAL_ONLY",
        "requires_human_acceptance": True,
        "isolate_test_required": isolate_test_required,
        "effect_authorized": False,
    }


def _proposal_for_observation(obs: Mapping[str, Any]) -> dict[str, Any]:
    domain = str(obs["domain"])
    subject_id = str(obs["subject_id"])
    signal = str(obs["signal"])
    summary = str(obs["summary"])
    evidence_refs = [str(x) for x in obs.get("evidence_refs", [])]
    repeated_count = int(obs.get("repeated_count", 1))
    desired = str(obs.get("proposed_change") or summary)

    if domain == "AGENT":
        if signal in {"SKILL_GAP", "REPEATED_FAILURE", "TOOL_MISUSE", "QUALITY_DRIFT"} or repeated_count >= 2:
            proposal = _base_proposal(
                kind="SKILL_CANDIDATE", domain=domain, subject_id=subject_id, signal=signal,
                summary=summary, evidence_refs=evidence_refs, isolate_test_required=True,
            )
            proposal["skill_spec"] = {
                "skill_name": f"hanri/{subject_id.lower()}/{signal.lower()}",
                "target_agent": subject_id,
                "objective": desired,
                "trigger_signals": [signal],
                "instruction_outline": [
                    "read the cited failure evidence before acting",
                    "apply the narrow corrective procedure",
                    "emit an evidence-bound result receipt",
                    "fail closed when required evidence is unavailable",
                ],
                "validation_gate": {
                    "requires_isolated_eval": True,
                    "acceptance": "candidate must outperform the prior behavior on cited failure cases without new policy violations",
                },
                "install_authorized": False,
            }
            return proposal

        proposal = _base_proposal(
            kind="AGENT_IMPROVEMENT", domain=domain, subject_id=subject_id, signal=signal,
            summary=summary, evidence_refs=evidence_refs, isolate_test_required=True,
        )
        proposal["agent_change"] = {"desired_behavior": desired, "install_authorized": False}
        return proposal

    if domain == "SYSTEM":
        proposal = _base_proposal(
            kind="SYSTEM_IMPROVEMENT", domain=domain, subject_id=subject_id, signal=signal,
            summary=summary, evidence_refs=evidence_refs, isolate_test_required=True,
        )
        proposal["system_change"] = {
            "hypothesis": desired,
            "test_mode": "ISOLATED_OR_SHADOW_FIRST",
            "independent_readback_required": True,
            "rollback_required": True,
        }
        return proposal

    if domain == "OPERATOR":
        proposal = _base_proposal(
            kind="OPERATOR_ADVICE", domain=domain, subject_id=subject_id, signal=signal,
            summary=summary, evidence_refs=evidence_refs, isolate_test_required=False,
        )
        proposal["operator_advice"] = {
            "recommendation": desired,
            "delivery": "ADVISORY_ONLY",
            "auto_message": False,
            "auto_schedule": False,
        }
        return proposal

    if domain == "SELF":
        proposal = _base_proposal(
            kind="HANRI_SELF_IMPROVEMENT", domain=domain, subject_id=subject_id, signal=signal,
            summary=summary, evidence_refs=evidence_refs, isolate_test_required=True,
        )
        proposal["self_change"] = {
            "corrective_attention_rule": desired,
            "self_apply_authorized": False,
            "requires_external_verification": True,
        }
        return proposal

    raise ValueError(f"unsupported domain: {domain}")


def run_attention_governor(
    payload: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    observations = [copy.deepcopy(dict(x)) for x in payload.get("observations", [])]
    outcomes = [copy.deepcopy(dict(x)) for x in payload.get("recommendation_outcomes", [])]
    generated_at = str(payload.get("generated_at", "")).strip()
    run_id = str(payload.get("run_id", "")).strip()
    if not generated_at or not run_id:
        raise ValueError("run_id and generated_at are required")

    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for obs in observations:
        obs_id = str(obs.get("observation_id", "")).strip()
        domain = str(obs.get("domain", "")).strip().upper()
        severity = str(obs.get("severity", "")).strip().upper()
        if not obs_id or obs_id in seen_ids:
            raise ValueError("observation_id must be unique and non-empty")
        if domain not in DOMAINS:
            raise ValueError(f"invalid domain: {domain}")
        if severity not in SEVERITIES:
            raise ValueError(f"invalid severity: {severity}")
        evidence_refs = sorted({str(x) for x in obs.get("evidence_refs", []) if str(x).strip()})
        if not evidence_refs:
            raise ValueError(f"observation {obs_id} requires evidence_refs")
        seen_ids.add(obs_id)
        normalized.append({
            "observation_id": obs_id,
            "domain": domain,
            "subject_id": str(obs.get("subject_id", "")).strip(),
            "signal": str(obs.get("signal", "")).strip().upper(),
            "severity": severity,
            "summary": str(obs.get("summary", "")).strip(),
            "evidence_refs": evidence_refs,
            "repeated_count": max(1, int(obs.get("repeated_count", 1))),
            "proposed_change": str(obs.get("proposed_change", "")).strip(),
        })
    normalized.sort(key=lambda x: x["observation_id"])

    findings: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    for obs in normalized:
        findings.append({
            "finding_id": f"F-{obs['observation_id']}",
            "domain": obs["domain"],
            "subject_id": obs["subject_id"],
            "signal": obs["signal"],
            "severity": obs["severity"],
            "summary": obs["summary"],
            "evidence_refs": obs["evidence_refs"],
            "repeated_count": obs["repeated_count"],
        })
        proposals.append(_proposal_for_observation(obs))

    counts = Counter(obs["domain"] for obs in normalized)
    min_per_domain = int(policy.get("attention_policy", {}).get("min_observations_per_domain", 1))
    max_share = float(policy.get("attention_policy", {}).get("max_single_domain_share", 0.60))
    blind_spots: list[str] = []

    for domain in DOMAINS:
        if counts.get(domain, 0) < min_per_domain:
            blind_spots.append(domain)
            evidence = ["R39_META_AUDIT:COVERAGE_LEDGER"]
            summary = f"HANRI has insufficient first-order attention coverage for {domain}."
            findings.append({
                "finding_id": f"F-META-BLIND-{domain}",
                "domain": "SELF",
                "subject_id": "HANRI",
                "signal": "ATTENTION_BLIND_SPOT",
                "severity": "HIGH",
                "summary": summary,
                "evidence_refs": evidence,
                "repeated_count": 1,
            })
            proposals.append(_proposal_for_observation({
                "domain": "SELF",
                "subject_id": "HANRI",
                "signal": "ATTENTION_BLIND_SPOT",
                "summary": summary,
                "evidence_refs": evidence,
                "repeated_count": 1,
                "proposed_change": f"require evidence-backed observation coverage for {domain} before declaring the attention cycle complete",
            }))

    total = len(normalized)
    imbalanced_domain: str | None = None
    if total:
        dominant_domain, dominant_count = max(((d, counts.get(d, 0)) for d in DOMAINS), key=lambda x: (x[1], x[0]))
        if dominant_count / total > max_share:
            imbalanced_domain = dominant_domain
            evidence = ["R39_META_AUDIT:DOMAIN_DISTRIBUTION"]
            summary = f"HANRI attention is over-concentrated on {dominant_domain}: {dominant_count}/{total} observations."
            findings.append({
                "finding_id": "F-META-IMBALANCE",
                "domain": "SELF",
                "subject_id": "HANRI",
                "signal": "ATTENTION_IMBALANCE",
                "severity": "MEDIUM",
                "summary": summary,
                "evidence_refs": evidence,
                "repeated_count": 1,
            })
            proposals.append(_proposal_for_observation({
                "domain": "SELF",
                "subject_id": "HANRI",
                "signal": "ATTENTION_IMBALANCE",
                "summary": summary,
                "evidence_refs": evidence,
                "repeated_count": 1,
                "proposed_change": "rebalance the next audit cycle toward under-observed domains without suppressing critical findings",
            }))

    outcome_counts = Counter()
    for item in sorted(outcomes, key=lambda x: str(x.get("recommendation_id", ""))):
        status = str(item.get("status", "UNKNOWN")).upper()
        outcome_counts[status] += 1
        if status in NEGATIVE_OUTCOMES:
            rid = str(item.get("recommendation_id", "UNKNOWN"))
            evidence = [str(x) for x in item.get("evidence_refs", [])] or [f"R39_OUTCOME:{rid}"]
            summary = f"Prior HANRI recommendation {rid} outcome is {status}; recommendation logic requires self-review."
            findings.append({
                "finding_id": f"F-OUTCOME-{rid}",
                "domain": "SELF",
                "subject_id": "HANRI",
                "signal": "RECOMMENDATION_OUTCOME_FAILURE",
                "severity": "HIGH" if status == "REGRESSED" else "MEDIUM",
                "summary": summary,
                "evidence_refs": sorted(set(evidence)),
                "repeated_count": 1,
            })
            proposals.append(_proposal_for_observation({
                "domain": "SELF",
                "subject_id": "HANRI",
                "signal": "RECOMMENDATION_OUTCOME_FAILURE",
                "summary": summary,
                "evidence_refs": evidence,
                "repeated_count": 1,
                "proposed_change": "compare the failed recommendation against outcome evidence and tighten the recommendation rule before reuse",
            }))

    findings.sort(key=lambda x: x["finding_id"])
    proposals.sort(key=lambda x: x["proposal_id"])

    result = {
        "schema_version": 1,
        "policy_version": str(policy.get("policy_version", "39.0.0-attention-over-attention-v1")),
        "run_id": run_id,
        "generated_at": generated_at,
        "mission": "AUDIT_SELF_AGENTS_SYSTEMS_OPERATOR_AND_PROPOSE_EVIDENCE_BOUND_IMPROVEMENTS",
        "observations": normalized,
        "findings": findings,
        "proposals": proposals,
        "meta_audit": {
            "attention_over_attention": True,
            "domain_counts": {domain: counts.get(domain, 0) for domain in DOMAINS},
            "blind_spots": blind_spots,
            "imbalanced_domain": imbalanced_domain,
            "coverage_complete": not blind_spots,
            "recommendation_outcomes": dict(sorted(outcome_counts.items())),
            "negative_outcome_count": sum(outcome_counts[s] for s in NEGATIVE_OUTCOMES),
            "verified_improved_count": sum(outcome_counts[s] for s in POSITIVE_OUTCOMES),
        },
        "capabilities": {
            "self_audit": True,
            "agent_audit": True,
            "agent_skill_factory": True,
            "system_audit": True,
            "system_improvement_proposals": True,
            "operator_audit": True,
            "operator_advice": True,
            "recommendation_outcome_audit": True,
        },
        "effect_boundary": {
            "proposal_only": True,
            "self_apply": False,
            "skill_install": False,
            "system_write": False,
            "operator_message": False,
            "auto_dispatch": False,
            "external_messages": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result
