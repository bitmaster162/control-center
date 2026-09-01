"""Deterministic read-only Control Tower / Portfolio Lens.

Consumes RUAP Snapshot IR as evidence and produces a cross-project currentness
projection. It never mutates providers, never grants effect authority, and
never infers deployment/runtime/effect state from source observations alone.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence


RUAP_SCHEMA = "ruap.snapshot/v1"
LENS_SCHEMA = "control_tower.portfolio_lens/v1"
AUTHORITY_CEILING = "OBSERVE_ONLY"

_SEVERITY = {
    "CURRENT": 0,
    "PARTIAL": 1,
    "HOLD": 2,
    "BLOCKED": 3,
}

_CURRENT_MARKERS = (
    "CURRENT",
    "SEALED",
    "PASS",
    "MERGED",
    "RELEASED",
    "COMPONENT_SOURCE",
    "BASELINE_SOURCE",
    "CURRENT_IMPLEMENTATION_SOURCE",
)

_PARTIAL_MARKERS = (
    "PARTIAL",
    "REVIEW",
    "READY_NOT_MERGED",
    "UNRESOLVED",
    "UNCLAIMED",
    "CANDIDATE",
    "HANDOFF",
    "SOURCE_PRESENT_RELATION_UNRESOLVED",
)

_HOLD_MARKERS = ("HOLD",)
_BLOCKED_MARKERS = ("BLOCKED", "ERROR", "FAIL", "DENY")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _parse_snapshot(snapshot: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(snapshot, Mapping):
        data = dict(snapshot)
    else:
        if isinstance(snapshot, bytes):
            text = snapshot.decode("utf-8", errors="strict")
        elif isinstance(snapshot, str):
            text = snapshot
        else:
            raise ValueError("SNAPSHOT_TYPE")
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("SNAPSHOT_ROOT")
    if data.get("schema") != RUAP_SCHEMA:
        raise ValueError("SNAPSHOT_SCHEMA")
    if data.get("authority_ceiling") != AUTHORITY_CEILING:
        raise ValueError("AUTHORITY_CEILING")
    if not isinstance(data.get("sources"), list):
        raise ValueError("SOURCES")
    if not isinstance(data.get("observations"), list):
        raise ValueError("OBSERVATIONS")
    source_ids = {
        row.get("id")
        for row in data["sources"]
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }
    if len(source_ids) != len(data["sources"]):
        raise ValueError("SOURCE_IDENTITY")
    for obs in data["observations"]:
        if not isinstance(obs, Mapping):
            raise ValueError("OBSERVATION_OBJECT")
        if obs.get("source_id") not in source_ids:
            raise ValueError("OBSERVATION_SOURCE")
        if not isinstance(obs.get("subject"), str) or not obs["subject"]:
            raise ValueError("OBSERVATION_SUBJECT")
        if not isinstance(obs.get("claim"), str) or not obs["claim"]:
            raise ValueError("OBSERVATION_CLAIM")
        if not isinstance(obs.get("class"), str) or not obs["class"]:
            raise ValueError("OBSERVATION_CLASS")
    return data


def _entity_key(subject: str) -> str:
    return subject.split(".", 1)[0].strip().lower()


def _status_text(observation: Mapping[str, Any]) -> str:
    status = observation.get("status")
    return str(status).strip().upper() if status is not None else ""


def classify_observation(observation: Mapping[str, Any]) -> str:
    """Classify only evidence/source currentness, never runtime/effect state."""
    text = _status_text(observation)

    if any(marker in text for marker in _BLOCKED_MARKERS):
        return "BLOCKED"
    if any(marker in text for marker in _HOLD_MARKERS):
        return "HOLD"
    if any(marker in text for marker in _PARTIAL_MARKERS):
        return "PARTIAL"

    observation_class = str(observation.get("class", "")).upper()
    if observation_class == "PROVIDER_READBACK":
        if not text or any(marker in text for marker in _CURRENT_MARKERS):
            return "CURRENT"
        return "PARTIAL"

    if observation_class in {"RECEIPT", "ACCEPTED_META"}:
        return "CURRENT" if any(marker in text for marker in _CURRENT_MARKERS) else "PARTIAL"

    return "PARTIAL"


def _worst(statuses: Sequence[str]) -> str:
    if not statuses:
        return "PARTIAL"
    return max(statuses, key=lambda value: _SEVERITY[value])


def build_portfolio_lens(
    snapshot: bytes | str | Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    data = _parse_snapshot(snapshot)
    sources = {
        row["id"]: row
        for row in data["sources"]
    }

    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in data["observations"]:
        obs = dict(raw)
        entity = _entity_key(obs["subject"])
        grouped.setdefault(entity, []).append(obs)

    entities: list[dict[str, Any]] = []
    counts = {"CURRENT": 0, "PARTIAL": 0, "HOLD": 0, "BLOCKED": 0}

    for entity in sorted(grouped):
        observations = sorted(
            grouped[entity],
            key=lambda obs: (
                obs["subject"],
                obs["source_id"],
                str(obs.get("status", "")),
            ),
        )
        classified = [classify_observation(obs) for obs in observations]
        source_currentness = _worst(classified)
        counts[source_currentness] += 1

        evidence = []
        for obs, status in zip(observations, classified):
            source = sources[obs["source_id"]]
            evidence.append(
                {
                    "subject": obs["subject"],
                    "source_id": obs["source_id"],
                    "provider": source["provider"],
                    "locator": source["locator"],
                    "observation_class": obs["class"],
                    "declared_status": obs.get("status"),
                    "source_currentness": status,
                    "freshness_required_before_effect": bool(
                        obs.get("freshness_required_before_effect", False)
                    ),
                }
            )

        next_read = {
            "action": "FRESH_READ_BEFORE_EFFECT",
            "source_ids": sorted({obs["source_id"] for obs in observations}),
            "reason": (
                "Control Tower is read-only. Source evidence never proves "
                "deployment, runtime, effect or semantic authority."
            ),
        }
        if source_currentness in {"BLOCKED", "HOLD", "PARTIAL"}:
            next_read["action"] = "RESOLVE_EVIDENCE_OR_CURRENTNESS"

        entities.append(
            {
                "entity": entity,
                "portfolio_status": source_currentness,
                "planes": {
                    "source": source_currentness,
                    "deployment": "UNKNOWN",
                    "runtime": "UNKNOWN",
                    "effect": "DENY",
                    "semantic_authority": "CONTROL_CENTER_ONLY",
                },
                "evidence": evidence,
                "next_read": next_read,
            }
        )

    payload = {
        "schema": LENS_SCHEMA,
        "generated_at": generated_at,
        "mode": "READ_ONLY",
        "authority_ceiling": AUTHORITY_CEILING,
        "semantic_authority": False,
        "effect_authority": False,
        "input": {
            "schema": RUAP_SCHEMA,
            "snapshot_generated_at": data.get("generated_at"),
            "snapshot_sha256": sha256_json(data),
        },
        "summary": {
            "entity_count": len(entities),
            "counts": counts,
        },
        "entities": entities,
        "invariants": {
            "source_ne_deployment": True,
            "source_ne_runtime": True,
            "source_ne_effect": True,
            "context_ne_permission": True,
            "control_center_remains_semantic_authority": True,
            "can_trade": False,
            "capital_permission": "DENY",
            "deploy_permission": "DENY",
        },
    }
    payload["projection_sha256"] = sha256_json(payload)
    return payload
