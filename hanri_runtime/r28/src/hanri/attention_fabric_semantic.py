from __future__ import annotations

import copy
from typing import Any, Mapping

import hanri.attention_fabric as _v1
from hanri.attention_governor import canonical_sha256

HASH_ALGORITHM = "SEMANTIC_ENVELOPE_V2"


def _as_nonempty(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def semantic_envelope_projection(raw: Mapping[str, Any]) -> dict[str, Any]:
    env = copy.deepcopy(dict(raw))
    envelope_id = _as_nonempty(env.get("envelope_id"), "envelope_id")
    source_type = _as_nonempty(env.get("source_type"), "source_type").upper()
    if source_type not in _v1.SOURCE_TYPES:
        raise ValueError(f"unsupported source_type: {source_type}")
    evidence_refs = sorted({str(x).strip() for x in env.get("evidence_refs", []) if str(x).strip()})
    payload = copy.deepcopy(dict(env.get("payload", {})))
    if source_type != "RECOMMENDATION_OUTCOME" and not evidence_refs:
        raise ValueError(f"envelope {envelope_id} requires evidence_refs")
    return {
        "envelope_id": envelope_id,
        "source_type": source_type,
        "producer": str(env.get("producer", "UNKNOWN")).strip() or "UNKNOWN",
        "subject_id": str(env.get("subject_id", "")).strip(),
        "evidence_refs": evidence_refs,
        "payload": payload,
    }


def _normalize_envelope_semantic(raw: Mapping[str, Any]) -> dict[str, Any]:
    env = copy.deepcopy(dict(raw))
    observed_at = _as_nonempty(env.get("observed_at"), "observed_at")
    projection = semantic_envelope_projection(env)
    normalized = {
        **projection,
        "observed_at": observed_at,
    }
    normalized["envelope_sha256"] = canonical_sha256(projection)
    return normalized


def run_attention_fabric_semantic(
    payload: Mapping[str, Any],
    *,
    governor_policy: Mapping[str, Any],
    fabric_policy: Mapping[str, Any],
) -> dict[str, Any]:
    original = _v1._normalize_envelope
    try:
        _v1._normalize_envelope = _normalize_envelope_semantic
        result = _v1.run_attention_fabric(
            payload,
            governor_policy=governor_policy,
            fabric_policy=fabric_policy,
        )
    finally:
        _v1._normalize_envelope = original

    result = copy.deepcopy(result)
    result["envelope_hash_algorithm"] = HASH_ALGORITHM
    result["fabric_receipt_sha256"] = canonical_sha256(
        {k: v for k, v in result.items() if k != "fabric_receipt_sha256"}
    )
    return result


load_envelopes_from_directory = _v1.load_envelopes_from_directory

__all__ = [
    "HASH_ALGORITHM",
    "semantic_envelope_projection",
    "run_attention_fabric_semantic",
    "load_envelopes_from_directory",
]
