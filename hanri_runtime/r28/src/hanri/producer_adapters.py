from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from hanri.attention_governor import canonical_sha256
from hanri.guarded_cli import enhanced_sanitize

POLICY_VERSION = "39.2.0-producer-adapters-v1"
ADAPTER_TYPES = {
    "RETURN_ARTIFACT",
    "SYSTEM_RECEIPT",
    "OPERATOR_EVENT_ARTIFACT",
    "HANRI_RECEIPT",
    "RECOMMENDATION_OUTCOME_ARTIFACT",
}
FAIL_STATES = {"FAIL", "FAILED", "ERROR", "REJECTED", "BLOCKED", "REGRESSED", "HALTED", "DOWN"}
SYSTEM_BAD_STATES = FAIL_STATES | {"DEGRADED", "UNHEALTHY"}
STALE_STATES = {"STALE", "UNKNOWN", "CONFLICT"}
OPERATOR_SIGNALS = {"MANUAL_REPEAT", "OPERATOR_FRICTION", "CONTEXT_OVERLOAD", "DECISION_BOTTLENECK"}
SELF_SIGNALS = {"MISSED_DEFECT", "ATTENTION_BLIND_SPOT", "ATTENTION_IMBALANCE", "RECOMMENDATION_OUTCOME_FAILURE"}
UTC = dt.timezone.utc
_PERCENT_ENV = re.compile(r"%([^%]+)%")


def _containers(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = [data]
    for key in ("payload", "result", "receipt", "meta", "verification", "summary"):
        value = data.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
    return rows


def _pick(data: Mapping[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for container in _containers(data):
        for key in keys:
            if key in container and container[key] not in (None, ""):
                value = container[key]
                if not isinstance(value, (dict, list, tuple, set)):
                    return value
    return default


def _bool(data: Mapping[str, Any], keys: Sequence[str]) -> bool:
    value = _pick(data, keys, False)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _int(data: Mapping[str, Any], keys: Sequence[str], default: int = 1) -> int:
    try:
        return int(_pick(data, keys, default))
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, findings: list[dict[str, str]], fallback: str) -> str:
    text = str(value or fallback).strip() or fallback
    clean = enhanced_sanitize(text, findings)
    return str(clean)


def _safe_refs(values: Sequence[Any], findings: list[dict[str, str]]) -> list[str]:
    result: list[str] = []
    for value in values[:32]:
        text = str(value).strip()
        if text:
            result.append(str(enhanced_sanitize(text, findings)))
    return sorted(set(result))


def _status(data: Mapping[str, Any]) -> str:
    return str(_pick(data, ("status", "state", "verdict", "conclusion", "result_status"), "UNKNOWN")).strip().upper()


def _freshness(data: Mapping[str, Any]) -> str:
    return str(_pick(data, ("freshness", "freshness_state", "evidence_freshness"), "CURRENT")).strip().upper()


def _subject(data: Mapping[str, Any], fallback: str) -> str:
    return str(_pick(data, ("subject_id", "agent_id", "system_id", "actor", "from", "producer", "component"), fallback)).strip() or fallback


def _observed_at(data: Mapping[str, Any], fallback: str) -> str:
    return str(_pick(data, ("observed_at", "created_at", "generated_at", "timestamp", "modified_at", "time"), fallback)).strip() or fallback


def _source_digest(data: Mapping[str, Any], source_sha256: str | None) -> str:
    if source_sha256:
        digest = str(source_sha256).strip().lower()
        if re.fullmatch(r"[a-f0-9]{64}", digest):
            return digest
        raise ValueError("source_sha256 must be lowercase/uppercase hex SHA-256")
    return canonical_sha256(data)


def _envelope_id(adapter_type: str, source_id: str, source_sha256: str) -> str:
    suffix = canonical_sha256({"adapter_type": adapter_type, "source_id": source_id, "source_sha256": source_sha256})[:24]
    return f"R39.2-{adapter_type}-{suffix}"


def _coverage(*, envelope_id: str, observed_at: str, domain: str, subject_id: str,
              evidence_refs: list[str], source_status: str) -> dict[str, Any]:
    return {
        "envelope_id": envelope_id,
        "source_type": "AUDIT_COVERAGE",
        "observed_at": observed_at,
        "producer": "HANRI_R39_2_PRODUCER_ADAPTERS",
        "subject_id": subject_id,
        "evidence_refs": evidence_refs,
        "payload": {
            "domain": domain,
            "audit_state": "AUDITED_NO_MATERIAL_DEFECT_SIGNAL",
            "source_status": source_status,
        },
    }


def adapt_artifact(
    *,
    adapter_type: str,
    source_id: str,
    data: Mapping[str, Any],
    observed_at_fallback: str,
    source_sha256: str | None = None,
) -> dict[str, Any]:
    adapter = str(adapter_type).strip().upper()
    if adapter not in ADAPTER_TYPES:
        raise ValueError(f"unsupported adapter_type: {adapter}")
    source_id = str(source_id).strip()
    if not source_id:
        raise ValueError("source_id is required")

    raw = copy.deepcopy(dict(data))
    digest = _source_digest(raw, source_sha256)
    findings: list[dict[str, str]] = []
    safe_source_id = _safe_text(source_id, findings, "UNKNOWN_SOURCE")
    observed_at = _safe_text(_observed_at(raw, observed_at_fallback), findings, observed_at_fallback)
    subject = _safe_text(_subject(raw, "UNKNOWN"), findings, "UNKNOWN")
    status = _status(raw)
    freshness = _freshness(raw)
    explicit_refs = raw.get("evidence_refs", [])
    if not isinstance(explicit_refs, list):
        explicit_refs = []
    evidence_refs = _safe_refs(
        [f"SOURCE_ID:{safe_source_id}", f"SOURCE_SHA256:{digest}", *explicit_refs], findings
    )
    envelope_id = _envelope_id(adapter, safe_source_id, digest)
    repeated = max(1, _int(raw, ("repeated_count", "failure_count", "occurrences"), 1))
    summary = _safe_text(
        _pick(raw, ("summary", "message", "reason", "description", "detail"), f"Audited {adapter} {safe_source_id}."),
        findings,
        f"Audited {adapter} {safe_source_id}.",
    )
    proposed_change = _safe_text(
        _pick(raw, ("proposed_change", "recommendation", "next_action", "corrective_action"), ""),
        findings,
        "",
    ) if _pick(raw, ("proposed_change", "recommendation", "next_action", "corrective_action"), "") else ""

    envelope: dict[str, Any] | None = None
    disposition = "EMITTED_COVERAGE"

    if adapter == "RETURN_ARTIFACT":
        skill_gap = _bool(raw, ("skill_gap", "missing_skill"))
        tool_misuse = _bool(raw, ("tool_misuse", "wrong_tool"))
        material = skill_gap or tool_misuse or status in FAIL_STATES
        if material:
            envelope = {
                "envelope_id": envelope_id,
                "source_type": "AGENT_RETURN",
                "observed_at": observed_at,
                "producer": "HANRI_R39_2_PRODUCER_ADAPTERS",
                "subject_id": subject,
                "evidence_refs": evidence_refs,
                "payload": {
                    "status": status,
                    "skill_gap": skill_gap,
                    "tool_misuse": tool_misuse,
                    "repeated_count": repeated,
                    "severity": str(_pick(raw, ("severity",), "HIGH" if status in FAIL_STATES else "MEDIUM")).upper(),
                    "summary": summary,
                    "proposed_change": proposed_change,
                },
            }
            disposition = "EMITTED_MATERIAL"
        else:
            envelope = _coverage(
                envelope_id=envelope_id, observed_at=observed_at, domain="AGENT", subject_id=subject,
                evidence_refs=evidence_refs, source_status=status,
            )

    elif adapter == "SYSTEM_RECEIPT":
        material = status in SYSTEM_BAD_STATES or freshness in STALE_STATES or _bool(raw, ("error", "health_error"))
        if material:
            envelope = {
                "envelope_id": envelope_id,
                "source_type": "SYSTEM_HEALTH",
                "observed_at": observed_at,
                "producer": "HANRI_R39_2_PRODUCER_ADAPTERS",
                "subject_id": subject,
                "evidence_refs": evidence_refs,
                "payload": {
                    "state": status,
                    "freshness": freshness,
                    "severity": str(_pick(raw, ("severity",), "HIGH" if status in FAIL_STATES else "MEDIUM")).upper(),
                    "summary": summary,
                    "proposed_change": proposed_change,
                },
            }
            disposition = "EMITTED_MATERIAL"
        else:
            envelope = _coverage(
                envelope_id=envelope_id, observed_at=observed_at, domain="SYSTEM", subject_id=subject,
                evidence_refs=evidence_refs, source_status=status,
            )

    elif adapter == "OPERATOR_EVENT_ARTIFACT":
        actor = str(_pick(raw, ("actor", "from", "subject_id", "operator"), "")).strip().upper()
        explicit_operator = _bool(raw, ("operator_event", "human_event")) or actor in {"ROBERT", "HUMAN", "OPERATOR"}
        if not explicit_operator:
            return {
                "source_id": safe_source_id,
                "source_sha256": digest,
                "adapter_type": adapter,
                "disposition": "SKIPPED_NOT_OPERATOR_EVENT",
                "envelope": None,
                "secret_boundary": {"finding_count": len(findings), "raw_values_persisted": False},
                "secret_findings": findings,
            }
        signal = str(_pick(raw, ("signal", "event_type"), "")).strip().upper()
        material = signal in OPERATOR_SIGNALS or repeated >= 2 or _bool(raw, ("friction", "manual_repeat", "context_overload"))
        if material:
            envelope = {
                "envelope_id": envelope_id,
                "source_type": "OPERATOR_EVENT",
                "observed_at": observed_at,
                "producer": "HANRI_R39_2_PRODUCER_ADAPTERS",
                "subject_id": subject if subject != "UNKNOWN" else "ROBERT",
                "evidence_refs": evidence_refs,
                "payload": {
                    "signal": signal or ("MANUAL_REPEAT" if repeated >= 2 else "OPERATOR_FRICTION"),
                    "repeated_count": repeated,
                    "severity": str(_pick(raw, ("severity",), "MEDIUM")).upper(),
                    "summary": summary,
                    "proposed_change": proposed_change,
                },
            }
            disposition = "EMITTED_MATERIAL"
        else:
            envelope = _coverage(
                envelope_id=envelope_id, observed_at=observed_at, domain="OPERATOR",
                subject_id=subject if subject != "UNKNOWN" else "ROBERT",
                evidence_refs=evidence_refs, source_status=status,
            )

    elif adapter == "HANRI_RECEIPT":
        signal = str(_pick(raw, ("signal", "finding", "failure_class"), "")).strip().upper()
        material = status in FAIL_STATES or status in {"REVISE"} or signal in SELF_SIGNALS or _bool(raw, ("missed_defect", "attention_blind_spot"))
        if material:
            envelope = {
                "envelope_id": envelope_id,
                "source_type": "HANRI_SELF_TRACE",
                "observed_at": observed_at,
                "producer": "HANRI_R39_2_PRODUCER_ADAPTERS",
                "subject_id": "HANRI",
                "evidence_refs": evidence_refs,
                "payload": {
                    "signal": signal or ("MISSED_DEFECT" if _bool(raw, ("missed_defect",)) else "SELF_REVIEW"),
                    "missed_defect": _bool(raw, ("missed_defect",)),
                    "severity": str(_pick(raw, ("severity",), "HIGH" if status in FAIL_STATES else "MEDIUM")).upper(),
                    "summary": summary,
                    "proposed_change": proposed_change,
                },
            }
            disposition = "EMITTED_MATERIAL"
        else:
            envelope = _coverage(
                envelope_id=envelope_id, observed_at=observed_at, domain="SELF", subject_id="HANRI",
                evidence_refs=evidence_refs, source_status=status,
            )

    elif adapter == "RECOMMENDATION_OUTCOME_ARTIFACT":
        recommendation_id = str(_pick(raw, ("recommendation_id", "proposal_id", "candidate_id"), "")).strip()
        outcome_status = str(_pick(raw, ("outcome_status", "status", "outcome"), "")).strip().upper()
        if not recommendation_id or not outcome_status:
            return {
                "source_id": safe_source_id,
                "source_sha256": digest,
                "adapter_type": adapter,
                "disposition": "SKIPPED_INCOMPLETE_OUTCOME",
                "envelope": None,
                "secret_boundary": {"finding_count": len(findings), "raw_values_persisted": False},
                "secret_findings": findings,
            }
        envelope = {
            "envelope_id": envelope_id,
            "source_type": "RECOMMENDATION_OUTCOME",
            "observed_at": observed_at,
            "producer": "HANRI_R39_2_PRODUCER_ADAPTERS",
            "subject_id": "HANRI",
            "evidence_refs": evidence_refs,
            "payload": {
                "recommendation_id": _safe_text(recommendation_id, findings, "UNKNOWN"),
                "status": _safe_text(outcome_status, findings, "UNKNOWN").upper(),
            },
        }
        disposition = "EMITTED_OUTCOME"

    assert envelope is not None
    return {
        "source_id": safe_source_id,
        "source_sha256": digest,
        "adapter_type": adapter,
        "disposition": disposition,
        "envelope": envelope,
        "secret_boundary": {"finding_count": len(findings), "raw_values_persisted": False},
        "secret_findings": findings,
    }


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
        "processed_sources": len(results),
        "emitted_envelopes": len(envelopes),
        "dispositions": dict(sorted(dispositions.items())),
        "source_receipts": [
            {
                "source_id": row["source_id"],
                "source_sha256": row["source_sha256"],
                "adapter_type": row["adapter_type"],
                "disposition": row["disposition"],
                "envelope_id": row["envelope"]["envelope_id"] if row.get("envelope") else None,
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
    return {"envelopes": sorted(envelopes, key=lambda x: x["envelope_id"]), "receipt": receipt}


def expand_percent_env(value: str, environ: Mapping[str, str] | None = None) -> str:
    env = dict(os.environ if environ is None else environ)
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        for candidate in (key, key.upper(), key.lower()):
            if candidate in env:
                return str(env[candidate])
        return match.group(0)
    expanded = _PERCENT_ENV.sub(repl, str(value))
    return os.path.expandvars(os.path.expanduser(expanded))


def _file_observed_at(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat().replace("+00:00", "Z")


def collect_source_rows(config: Mapping[str, Any], *, now: dt.datetime | None = None,
                        environ: Mapping[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now_utc = (now or dt.datetime.now(UTC)).astimezone(UTC)
    max_file_bytes = int(config.get("max_file_bytes", 4 * 1024 * 1024))
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for source in config.get("sources", []):
        if not bool(source.get("enabled", True)):
            continue
        source_name = str(source.get("source_id", "SOURCE")).strip() or "SOURCE"
        adapter_type = str(source.get("adapter_type", "")).strip().upper()
        root = Path(expand_percent_env(str(source.get("path", "")), environ))
        pattern = str(source.get("glob", "*.json"))
        recursive = bool(source.get("recursive", False))
        max_files = max(1, int(source.get("max_files", 50)))
        max_age_seconds = int(source.get("max_age_seconds", 0))

        if root.is_file():
            files = [root]
        elif root.is_dir():
            iterator = root.rglob(pattern) if recursive else root.glob(pattern)
            files = [p for p in iterator if p.is_file()]
            files.sort(key=lambda p: (-p.stat().st_mtime, str(p).lower()))
            files = files[:max_files]
        else:
            skipped.append({"source_id": source_name, "reason": "SOURCE_PATH_MISSING"})
            continue

        for path in files:
            stat = path.stat()
            age_seconds = max(0, int((now_utc - dt.datetime.fromtimestamp(stat.st_mtime, tz=UTC)).total_seconds()))
            logical_id = f"{source_name}:{path.name}"
            if max_age_seconds > 0 and age_seconds > max_age_seconds:
                skipped.append({"source_id": logical_id, "reason": "SOURCE_TOO_OLD"})
                continue
            if stat.st_size > max_file_bytes:
                skipped.append({"source_id": logical_id, "reason": "SOURCE_TOO_LARGE"})
                continue
            raw_bytes = path.read_bytes()
            digest = hashlib.sha256(raw_bytes).hexdigest()
            try:
                parsed = json.loads(raw_bytes.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                skipped.append({"source_id": logical_id, "reason": "SOURCE_NOT_JSON"})
                continue

            items: list[Mapping[str, Any]]
            if isinstance(parsed, Mapping):
                items = [parsed]
            elif isinstance(parsed, list) and all(isinstance(x, Mapping) for x in parsed):
                items = [dict(x) for x in parsed]
            else:
                skipped.append({"source_id": logical_id, "reason": "SOURCE_JSON_ROOT_UNSUPPORTED"})
                continue

            for index, item in enumerate(items):
                item_id = logical_id if len(items) == 1 else f"{logical_id}#{index}"
                item_digest = digest if len(items) == 1 else canonical_sha256({"file_sha256": digest, "index": index, "item": item})
                rows.append({
                    "adapter_type": adapter_type,
                    "source_id": item_id,
                    "data": dict(item),
                    "observed_at_fallback": _file_observed_at(path),
                    "source_sha256": item_digest,
                })
    rows.sort(key=lambda x: (x["adapter_type"], x["source_id"]))
    skipped.sort(key=lambda x: (x["source_id"], x["reason"]))
    return rows, skipped
