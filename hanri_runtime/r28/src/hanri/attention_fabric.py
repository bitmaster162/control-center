from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from hanri.attention_governor import DOMAINS, canonical_sha256, run_attention_governor

SOURCE_TYPES = {
    "HANRI_SELF_TRACE",
    "AGENT_RETURN",
    "SYSTEM_HEALTH",
    "OPERATOR_EVENT",
    "RECOMMENDATION_OUTCOME",
    "OBSERVATION",
}
SEVERITY_WEIGHT = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
KIND_WEIGHT = {
    "HANRI_SELF_IMPROVEMENT": 2,
    "SKILL_CANDIDATE": 2,
    "AGENT_IMPROVEMENT": 1,
    "SYSTEM_IMPROVEMENT": 2,
    "OPERATOR_ADVICE": 1,
}


def _as_nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _normalize_envelope(raw: Mapping[str, Any]) -> dict[str, Any]:
    env = copy.deepcopy(dict(raw))
    envelope_id = _as_nonempty(env.get("envelope_id"), "envelope_id")
    source_type = _as_nonempty(env.get("source_type"), "source_type").upper()
    observed_at = _as_nonempty(env.get("observed_at"), "observed_at")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"unsupported source_type: {source_type}")
    evidence_refs = sorted({str(x).strip() for x in env.get("evidence_refs", []) if str(x).strip()})
    payload = copy.deepcopy(dict(env.get("payload", {})))
    if source_type != "RECOMMENDATION_OUTCOME" and not evidence_refs:
        raise ValueError(f"envelope {envelope_id} requires evidence_refs")
    normalized = {
        "envelope_id": envelope_id,
        "source_type": source_type,
        "observed_at": observed_at,
        "producer": str(env.get("producer", "UNKNOWN")).strip() or "UNKNOWN",
        "subject_id": str(env.get("subject_id", "")).strip(),
        "evidence_refs": evidence_refs,
        "payload": payload,
    }
    normalized["envelope_sha256"] = canonical_sha256(normalized)
    return normalized


def _observation_from_envelope(env: Mapping[str, Any]) -> dict[str, Any] | None:
    source_type = str(env["source_type"])
    payload = dict(env.get("payload", {}))
    subject_id = str(env.get("subject_id") or payload.get("subject_id") or "UNKNOWN").strip()
    evidence_refs = sorted(set(list(env.get("evidence_refs", [])) + [f"ENVELOPE_SHA256:{env['envelope_sha256']}"]))

    if source_type == "RECOMMENDATION_OUTCOME":
        return None

    if source_type == "OBSERVATION":
        domain = str(payload.get("domain", "")).upper()
        if domain not in DOMAINS:
            raise ValueError(f"invalid observation domain: {domain}")
        signal = _as_nonempty(payload.get("signal"), "payload.signal").upper()
        severity = str(payload.get("severity", "MEDIUM")).upper()
        summary = _as_nonempty(payload.get("summary"), "payload.summary")

    elif source_type == "HANRI_SELF_TRACE":
        domain = "SELF"
        signal = str(payload.get("signal") or ("MISSED_DEFECT" if payload.get("missed_defect") else "SELF_REVIEW")).upper()
        severity = str(payload.get("severity", "MEDIUM")).upper()
        summary = _as_nonempty(payload.get("summary"), "payload.summary")
        subject_id = subject_id if subject_id != "UNKNOWN" else "HANRI"

    elif source_type == "AGENT_RETURN":
        domain = "AGENT"
        if payload.get("skill_gap"):
            signal = "SKILL_GAP"
        elif payload.get("tool_misuse"):
            signal = "TOOL_MISUSE"
        elif str(payload.get("status", "")).upper() in {"FAIL", "FAILED", "REJECTED"}:
            signal = "REPEATED_FAILURE" if int(payload.get("repeated_count", 1)) >= 2 else "QUALITY_DRIFT"
        else:
            signal = str(payload.get("signal", "QUALITY_DRIFT")).upper()
        severity = str(payload.get("severity", "MEDIUM")).upper()
        summary = _as_nonempty(payload.get("summary"), "payload.summary")

    elif source_type == "SYSTEM_HEALTH":
        domain = "SYSTEM"
        state = str(payload.get("state", payload.get("status", "UNKNOWN"))).upper()
        freshness = str(payload.get("freshness", "CURRENT")).upper()
        if freshness in {"STALE", "UNKNOWN"}:
            signal = "STATIC_SNAPSHOT_DRIFT"
        elif state in {"DEGRADED", "FAILED", "DOWN", "HALTED"}:
            signal = "HEALTH_DEGRADED"
        else:
            signal = str(payload.get("signal", "SYSTEM_FRICTION")).upper()
        severity = str(payload.get("severity", "HIGH" if state in {"FAILED", "DOWN"} else "MEDIUM")).upper()
        summary = _as_nonempty(payload.get("summary"), "payload.summary")

    elif source_type == "OPERATOR_EVENT":
        domain = "OPERATOR"
        repeated = int(payload.get("repeated_count", 1))
        signal = str(payload.get("signal") or ("MANUAL_REPEAT" if repeated >= 2 else "OPERATOR_FRICTION")).upper()
        severity = str(payload.get("severity", "MEDIUM")).upper()
        summary = _as_nonempty(payload.get("summary"), "payload.summary")

    else:
        raise ValueError(f"unsupported source_type: {source_type}")

    return {
        "observation_id": f"ENV-{env['envelope_id']}",
        "domain": domain,
        "subject_id": subject_id,
        "signal": signal,
        "severity": severity,
        "summary": summary,
        "evidence_refs": evidence_refs,
        "repeated_count": max(1, int(payload.get("repeated_count", 1))),
        "proposed_change": str(payload.get("proposed_change", "")).strip(),
    }


def _outcome_from_envelope(env: Mapping[str, Any]) -> dict[str, Any] | None:
    if env["source_type"] != "RECOMMENDATION_OUTCOME":
        return None
    payload = dict(env.get("payload", {}))
    recommendation_id = _as_nonempty(payload.get("recommendation_id"), "payload.recommendation_id")
    status = _as_nonempty(payload.get("status"), "payload.status").upper()
    evidence_refs = sorted(set(list(env.get("evidence_refs", [])) + [f"ENVELOPE_SHA256:{env['envelope_sha256']}"]))
    return {
        "recommendation_id": recommendation_id,
        "status": status,
        "evidence_refs": evidence_refs,
    }


def _prioritize(governor_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    finding_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for finding in governor_result.get("findings", []):
        key = (str(finding.get("domain")), str(finding.get("subject_id")), str(finding.get("signal")))
        finding_index[key] = dict(finding)

    ranked: list[dict[str, Any]] = []
    for proposal in governor_result.get("proposals", []):
        item = copy.deepcopy(dict(proposal))
        key = (str(item.get("domain")), str(item.get("subject_id")), str(item.get("signal")))
        finding = finding_index.get(key, {})
        severity = str(finding.get("severity", "MEDIUM")).upper()
        repeated_count = max(1, int(finding.get("repeated_count", 1)))
        evidence_count = len(item.get("evidence_refs", []))
        score = (
            SEVERITY_WEIGHT.get(severity, 2) * 100
            + min(repeated_count, 9) * 10
            + KIND_WEIGHT.get(str(item.get("kind")), 0) * 5
            + min(evidence_count, 9)
        )
        item["priority"] = {
            "score": score,
            "severity": severity,
            "repeated_count": repeated_count,
            "evidence_count": evidence_count,
        }
        ranked.append(item)
    ranked.sort(key=lambda x: (-int(x["priority"]["score"]), str(x["proposal_id"])))
    for index, item in enumerate(ranked, start=1):
        item["priority"]["rank"] = index
    return ranked


def run_attention_fabric(
    payload: Mapping[str, Any],
    *,
    governor_policy: Mapping[str, Any],
    fabric_policy: Mapping[str, Any],
) -> dict[str, Any]:
    run_id = _as_nonempty(payload.get("fabric_run_id"), "fabric_run_id")
    generated_at = _as_nonempty(payload.get("generated_at"), "generated_at")
    raw_envelopes = [dict(x) for x in payload.get("envelopes", [])]

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for raw in raw_envelopes:
        env = _normalize_envelope(raw)
        existing = by_id.get(env["envelope_id"])
        if existing is not None:
            if existing["envelope_sha256"] != env["envelope_sha256"]:
                raise ValueError(f"conflicting envelope_id: {env['envelope_id']}")
            duplicate_count += 1
            continue
        by_id[env["envelope_id"]] = env

    envelopes = sorted(by_id.values(), key=lambda x: (x["observed_at"], x["envelope_id"]))
    observations: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for env in envelopes:
        observation = _observation_from_envelope(env)
        if observation is not None:
            observations.append(observation)
        outcome = _outcome_from_envelope(env)
        if outcome is not None:
            outcomes.append(outcome)

    governor_payload = {
        "run_id": f"{run_id}:GOVERNOR",
        "generated_at": generated_at,
        "observations": observations,
        "recommendation_outcomes": outcomes,
    }
    governor = run_attention_governor(governor_payload, policy=governor_policy)
    prioritized = _prioritize(governor)
    source_counts = Counter(env["source_type"] for env in envelopes)

    result = {
        "schema_version": 1,
        "policy_version": str(fabric_policy.get("policy_version", "39.1.0-attention-fabric-v1")),
        "fabric_run_id": run_id,
        "generated_at": generated_at,
        "mode": "REAL_ENVELOPE_INGESTION",
        "ledger": {
            "input_envelopes": len(raw_envelopes),
            "accepted_envelopes": len(envelopes),
            "duplicate_envelopes": duplicate_count,
            "source_counts": dict(sorted(source_counts.items())),
            "observation_count": len(observations),
            "outcome_count": len(outcomes),
            "envelope_hashes": [
                {"envelope_id": env["envelope_id"], "sha256": env["envelope_sha256"], "source_type": env["source_type"]}
                for env in envelopes
            ],
        },
        "governor": governor,
        "prioritized_proposals": prioritized,
        "attention_summary": {
            "coverage_complete": bool(governor["meta_audit"]["coverage_complete"]),
            "blind_spots": list(governor["meta_audit"]["blind_spots"]),
            "domain_counts": dict(governor["meta_audit"]["domain_counts"]),
            "proposal_count": len(prioritized),
            "top_proposal_id": prioritized[0]["proposal_id"] if prioritized else None,
            "negative_outcome_count": int(governor["meta_audit"]["negative_outcome_count"]),
        },
        "effect_boundary": copy.deepcopy(governor["effect_boundary"]),
    }
    result["fabric_receipt_sha256"] = canonical_sha256(result)
    return result


def load_envelopes_from_directory(path: str | Path) -> list[dict[str, Any]]:
    root = Path(path)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    envelopes: list[dict[str, Any]] = []
    for item in sorted(root.glob("*.json"), key=lambda p: p.name.lower()):
        data = json.loads(item.read_text(encoding="utf-8"))
        if isinstance(data, list):
            envelopes.extend(dict(x) for x in data)
        elif isinstance(data, dict) and "envelopes" in data:
            envelopes.extend(dict(x) for x in data.get("envelopes", []))
        elif isinstance(data, dict):
            envelopes.append(dict(data))
        else:
            raise ValueError(f"unsupported JSON root in {item}")
    return envelopes
