from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping, Sequence

from hanri.attention_governor import canonical_sha256
from hanri.producer_adapters import adapt_artifact as _base_adapt_artifact
from hanri.producer_adapters import collect_source_rows

POLICY_VERSION = "39.2.1-attention-coverage-closure-v1"
CANONICAL_OPERATOR_EVENT_TYPE = "OPERATOR_FEEDBACK"
CANONICAL_OPERATOR_ID = "ROBERT"


def normalize_operator_contract(
    *,
    adapter_type: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    """Bridge the accepted HANRI event schema into the R39.2 operator adapter contract.

    R26+ event.schema.json already defines OPERATOR_FEEDBACK as the canonical
    human-feedback event type. R39.2 originally required actor=ROBERT/HUMAN/OPERATOR
    or an explicit boolean flag, which could discard a valid OPERATOR_FEEDBACK event
    emitted by HANRI/system code. R39.2.1 treats the schema event type itself as the
    human-binding proof. It does not manufacture friction or a material finding.
    """
    raw = copy.deepcopy(dict(data))
    if str(adapter_type).strip().upper() != "OPERATOR_EVENT_ARTIFACT":
        return raw

    event_type = str(raw.get("event_type", "")).strip().upper()
    if event_type != CANONICAL_OPERATOR_EVENT_TYPE:
        return raw

    raw["operator_event"] = True
    raw["subject_id"] = CANONICAL_OPERATOR_ID
    raw.setdefault("evidence_refs", [])
    refs = raw.get("evidence_refs")
    if not isinstance(refs, list):
        refs = []
    refs = list(refs)
    refs.append("EVENT_SCHEMA:OPERATOR_FEEDBACK")
    raw["evidence_refs"] = refs
    return raw


def adapt_artifact(
    *,
    adapter_type: str,
    source_id: str,
    data: Mapping[str, Any],
    observed_at_fallback: str,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_operator_contract(adapter_type=adapter_type, data=data)
    result = _base_adapt_artifact(
        adapter_type=adapter_type,
        source_id=source_id,
        data=normalized,
        observed_at_fallback=observed_at_fallback,
        source_sha256=source_sha256,
    )
    if (
        str(adapter_type).strip().upper() == "OPERATOR_EVENT_ARTIFACT"
        and str(normalized.get("event_type", "")).strip().upper() == CANONICAL_OPERATOR_EVENT_TYPE
    ):
        result = copy.deepcopy(result)
        result["operator_contract"] = {
            "canonical_event_type": CANONICAL_OPERATOR_EVENT_TYPE,
            "canonical_operator_id": CANONICAL_OPERATOR_ID,
            "schema_bound": True,
        }
    return result


def adapt_artifacts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    envelopes: list[dict[str, Any]] = []
    secret_findings: list[dict[str, str]] = []

    for row in rows:
        result = adapt_artifact(
            adapter_type=str(row["adapter_type"]),
            source_id=str(row["source_id"]),
            data=dict(row["data"]),
            observed_at_fallback=str(row["observed_at_fallback"]),
            source_sha256=str(row.get("source_sha256") or "") or None,
        )
        results.append(result)
        if result.get("envelope") is not None:
            envelopes.append(dict(result["envelope"]))
        secret_findings.extend(result.get("secret_findings", []))

    dispositions = Counter(str(row["disposition"]) for row in results)
    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "base_policy_version": "39.2.0-producer-adapters-v1",
        "processed_sources": len(results),
        "emitted_envelopes": len(envelopes),
        "dispositions": dict(sorted(dispositions.items())),
        "source_receipts": [
            {
                "source_id": row["source_id"],
                "source_sha256": row["source_sha256"],
                "adapter_type": row["adapter_type"],
                "disposition": row["disposition"],
                **({"operator_contract": row["operator_contract"]} if "operator_contract" in row else {}),
            }
            for row in results
        ],
        "secret_boundary": {
            "finding_count": len(secret_findings),
            "raw_values_persisted": False,
        },
        "effect_boundary": {
            "producer_reads_only": True,
            "attention_inbox_write_only": True,
            "provider_calls": False,
            "stable_roots_modified": False,
            "r36_runtime_modified": False,
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
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"envelopes": envelopes, "receipt": receipt}


def summarize_skips(skipped: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reason_counts = Counter(str(row.get("reason", "UNKNOWN")) for row in skipped)
    source_counts: Counter[str] = Counter()
    for row in skipped:
        source_id = str(row.get("source_id", "UNKNOWN"))
        source_root = source_id.split(":", 1)[0]
        source_counts[source_root] += 1

    return {
        "scan_skip_count": len(skipped),
        "scan_skip_reason_counts": dict(sorted(reason_counts.items())),
        "scan_skip_source_counts": dict(sorted(source_counts.items())),
        "scan_skips": [dict(row) for row in skipped],
    }


__all__ = [
    "POLICY_VERSION",
    "CANONICAL_OPERATOR_EVENT_TYPE",
    "CANONICAL_OPERATOR_ID",
    "normalize_operator_contract",
    "adapt_artifact",
    "adapt_artifacts",
    "collect_source_rows",
    "summarize_skips",
]
