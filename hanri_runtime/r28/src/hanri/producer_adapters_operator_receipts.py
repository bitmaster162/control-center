from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping, Sequence

from hanri.attention_governor import canonical_sha256
from hanri.producer_adapters_coverage import (
    adapt_artifact as _coverage_adapt_artifact,
    collect_source_rows,
    normalize_operator_contract,
    summarize_skips,
)

POLICY_VERSION = "39.2.2-human-decision-receipts-v1"
HUMAN_DECISION_SCHEMA = "control_canter.human_decision_receipt.v1"
CURRENT_GENERATION = "R64"
CANONICAL_OPERATOR_ID = "ROBERT"


def _decision_contract(data: Mapping[str, Any]) -> dict[str, Any]:
    schema = str(data.get("schema", "")).strip()
    generation = str(data.get("generation", "")).strip().upper()
    decider = str(data.get("decider", "")).strip().upper()
    decisions = data.get("decisions")
    boundaries = data.get("boundaries")

    decision_rows = decisions if isinstance(decisions, list) else []
    boundaries_map = boundaries if isinstance(boundaries, Mapping) else {}
    valid_decisions = bool(decision_rows) and all(
        isinstance(row, Mapping)
        and str(row.get("id", "")).strip()
        and str(row.get("verdict", "")).strip()
        for row in decision_rows
    )
    boundary_ok = (
        boundaries_map.get("can_trade") is False
        and str(boundaries_map.get("capital_permission", "")).strip().upper() == "DENY"
    )

    reasons: list[str] = []
    if schema != HUMAN_DECISION_SCHEMA:
        reasons.append("SCHEMA_MISMATCH")
    if generation != CURRENT_GENERATION:
        reasons.append("GENERATION_MISMATCH")
    if decider not in {"ROBERT", "HUMAN", "OPERATOR"}:
        reasons.append("DECIDER_NOT_HUMAN_BOUND")
    if not valid_decisions:
        reasons.append("DECISIONS_INVALID_OR_EMPTY")
    if not boundary_ok:
        reasons.append("SAFETY_BOUNDARY_MISMATCH")

    return {
        "schema": schema,
        "generation": generation,
        "decider": decider,
        "decision_count": len(decision_rows),
        "safety_boundary_ok": boundary_ok,
        "valid": not reasons,
        "reasons": reasons,
    }


def normalize_human_decision_receipt(
    *,
    adapter_type: str,
    data: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    raw = normalize_operator_contract(adapter_type=adapter_type, data=data)
    if str(adapter_type).strip().upper() != "OPERATOR_EVENT_ARTIFACT":
        return raw, None
    if str(raw.get("schema", "")).strip() != HUMAN_DECISION_SCHEMA:
        return raw, None

    contract = _decision_contract(raw)
    if not contract["valid"]:
        return raw, contract

    normalized = copy.deepcopy(raw)
    normalized["operator_event"] = True
    normalized["subject_id"] = CANONICAL_OPERATOR_ID
    normalized["actor"] = CANONICAL_OPERATOR_ID
    normalized["status"] = "RECORDED"
    normalized["summary"] = (
        f"Recorded {CURRENT_GENERATION} human decision receipt with "
        f"{contract['decision_count']} bounded decisions."
    )

    refs = normalized.get("evidence_refs")
    if not isinstance(refs, list):
        refs = []
    refs = list(refs)
    refs.extend([
        f"HUMAN_DECISION_SCHEMA:{HUMAN_DECISION_SCHEMA}",
        f"GENERATION:{CURRENT_GENERATION}",
        f"DECISION_COUNT:{contract['decision_count']}",
    ])
    normalized["evidence_refs"] = refs

    # Raw utterances and individual decision scopes are source evidence only.
    # The base adapter persists neither raw input nor arbitrary producer fields.
    return normalized, contract


def adapt_artifact(
    *,
    adapter_type: str,
    source_id: str,
    data: Mapping[str, Any],
    observed_at_fallback: str,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    normalized, contract = normalize_human_decision_receipt(
        adapter_type=adapter_type,
        data=data,
    )
    result = _coverage_adapt_artifact(
        adapter_type=adapter_type,
        source_id=source_id,
        data=normalized,
        observed_at_fallback=observed_at_fallback,
        source_sha256=source_sha256,
    )
    if contract is not None:
        result = copy.deepcopy(result)
        result["human_decision_contract"] = contract
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
    validated = sum(
        1
        for row in results
        if row.get("human_decision_contract", {}).get("valid") is True
    )
    invalid = sum(
        1
        for row in results
        if "human_decision_contract" in row
        and row.get("human_decision_contract", {}).get("valid") is not True
    )

    receipt = {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "base_policy_version": "39.2.1-attention-coverage-closure-v1",
        "processed_sources": len(results),
        "emitted_envelopes": len(envelopes),
        "dispositions": dict(sorted(dispositions.items())),
        "human_decision_receipts_validated": validated,
        "human_decision_receipts_invalid": invalid,
        "source_receipts": [
            {
                "source_id": row["source_id"],
                "source_sha256": row["source_sha256"],
                "adapter_type": row["adapter_type"],
                "disposition": row["disposition"],
                **(
                    {"human_decision_contract": row["human_decision_contract"]}
                    if "human_decision_contract" in row
                    else {}
                ),
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
            "human_decision_execution": False,
            "synthetic_operator_events": False,
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


__all__ = [
    "POLICY_VERSION",
    "HUMAN_DECISION_SCHEMA",
    "CURRENT_GENERATION",
    "CANONICAL_OPERATOR_ID",
    "normalize_human_decision_receipt",
    "adapt_artifact",
    "adapt_artifacts",
    "collect_source_rows",
    "summarize_skips",
]
