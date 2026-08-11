from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping

STRONG_EVIDENCE = {"RECEIPTED", "HASH_VERIFIED"}
CURRENT_STATE_SECTIONS = ("kpis", "current_actions", "systems", "agents", "decisions")
FRESHNESS_FIELD_SECTIONS = {"kpis", "systems", "agents"}
VALID_FRESHNESS = {"CURRENT", "STALE", "UNKNOWN", "NOT_APPLICABLE"}


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _parse_time(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("timestamp is required")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolve_successor(source_id: str, superseded_by: Mapping[str, str]) -> str:
    current = source_id
    seen: set[str] = set()
    while current in superseded_by:
        if current in seen:
            raise ValueError(f"supersession cycle at {current}")
        seen.add(current)
        current = str(superseded_by[current])
    return current


def _source_is_usable(source: Mapping[str, Any]) -> bool:
    return str(source.get("evidence_state", "")) in STRONG_EVIDENCE


def _set_row_freshness(section: str, row: MutableMapping[str, Any], value: str) -> None:
    """Set freshness only where the v1 snapshot contract supports that field."""
    if section in FRESHNESS_FIELD_SECTIONS or "freshness" in row:
        row["freshness"] = value


def reconcile_truth_projection(
    snapshot: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    """Build a deterministic, schema-compatible current-truth projection bundle.

    Returns {"snapshot": ..., "receipt": ...}. The snapshot remains compatible
    with the existing v1 schema: superseded sources are rendered STALE and the
    exact supersession relation is kept in the separate receipt.
    """
    result = copy.deepcopy(dict(snapshot))
    now = _parse_time(generated_at)

    sources = result.get("sources")
    if not isinstance(sources, list):
        raise ValueError("snapshot.sources must be a list")

    source_by_id: dict[str, MutableMapping[str, Any]] = {}
    legacy_freshness_normalization: dict[str, dict[str, str]] = {}
    for row in sources:
        if not isinstance(row, MutableMapping):
            raise ValueError("snapshot.sources rows must be objects")
        source_id = str(row.get("source_id", "")).strip()
        if not source_id or source_id in source_by_id:
            raise ValueError("source_id must be unique and non-empty")

        freshness = str(row.get("freshness", "UNKNOWN"))
        if freshness not in VALID_FRESHNESS:
            normalized = "STALE" if freshness == "SUPERSEDED" else "UNKNOWN"
            row["freshness"] = normalized
            prior_notes = str(row.get("notes", "")).strip()
            marker = f"LEGACY_FRESHNESS_NORMALIZED:{freshness}->{normalized}"
            row["notes"] = f"{prior_notes} | {marker}".strip(" |")
            legacy_freshness_normalization[source_id] = {"from": freshness, "to": normalized}

        source_by_id[source_id] = row

    superseded_by = {str(k): str(v) for k, v in dict(policy.get("superseded_by", {})).items()}
    ttl_by_source = {str(k): int(v) for k, v in dict(policy.get("source_ttl_seconds", {})).items()}
    freshness_basis = {str(k): str(v) for k, v in dict(policy.get("freshness_basis", {})).items()}

    applied_supersession: dict[str, str] = {}
    ttl_audit: dict[str, dict[str, Any]] = {}

    for source_id in list(source_by_id):
        if source_id not in superseded_by:
            continue
        final_successor = _resolve_successor(source_id, superseded_by)
        successor = source_by_id.get(final_successor)
        if successor is None or not _source_is_usable(successor):
            continue
        source = source_by_id[source_id]
        source["freshness"] = "STALE"
        prior_notes = str(source.get("notes", "")).strip()
        marker = f"SUPERSEDED_BY:{final_successor}"
        if marker not in prior_notes:
            source["notes"] = f"{prior_notes} | {marker}".strip(" |")
        applied_supersession[source_id] = final_successor

    for source_id, ttl_seconds in ttl_by_source.items():
        if ttl_seconds <= 0:
            raise ValueError(f"TTL must be positive for {source_id}")
        source = source_by_id.get(source_id)
        if source is None or source_id in applied_supersession:
            continue
        as_of = source.get("as_of")
        if not as_of:
            source["freshness"] = "UNKNOWN"
            ttl_audit[source_id] = {
                "status": "UNKNOWN",
                "max_age_seconds": ttl_seconds,
                "basis": freshness_basis.get(source_id, "TTL declared but source has no as_of timestamp"),
            }
            continue
        age_seconds = max(0, int((now - _parse_time(str(as_of))).total_seconds()))
        status = "STALE" if age_seconds > ttl_seconds else "CURRENT"
        if source.get("freshness") not in {"UNKNOWN", "NOT_APPLICABLE"}:
            source["freshness"] = status
        ttl_audit[source_id] = {
            "status": status,
            "age_seconds": age_seconds,
            "max_age_seconds": ttl_seconds,
            "basis": freshness_basis.get(source_id, "Source-specific TTL"),
        }

    effective_ref_map: dict[str, str] = {}
    for source_id in source_by_id:
        final_id = _resolve_successor(source_id, superseded_by)
        final_source = source_by_id.get(final_id)
        if final_source is not None and _source_is_usable(final_source):
            effective_ref_map[source_id] = final_id
        else:
            effective_ref_map[source_id] = source_id

    degraded_items: list[dict[str, Any]] = []
    rewritten_refs: list[dict[str, Any]] = []

    for section in CURRENT_STATE_SECTIONS:
        rows = result.get(section, [])
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, MutableMapping):
                continue
            refs = row.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                continue

            original_refs = [str(ref) for ref in refs]
            effective_refs: list[str] = []
            for ref in original_refs:
                effective = effective_ref_map.get(ref, ref)
                if effective not in effective_refs:
                    effective_refs.append(effective)
            row["evidence_refs"] = effective_refs
            if effective_refs != original_refs:
                rewritten_refs.append({
                    "section": section,
                    "index": index,
                    "before": original_refs,
                    "after": effective_refs,
                })

            freshnesses = [
                str(source_by_id[ref].get("freshness", "UNKNOWN"))
                for ref in effective_refs
                if ref in source_by_id
            ]
            if not freshnesses:
                resolved_freshness = "UNKNOWN"
                degraded_items.append({"section": section, "index": index, "reason": "NO_RESOLVED_EVIDENCE"})
            elif any(value == "CURRENT" for value in freshnesses):
                resolved_freshness = "CURRENT"
            elif any(value == "STALE" for value in freshnesses):
                resolved_freshness = "STALE"
                degraded_items.append({"section": section, "index": index, "reason": "STALE_EVIDENCE"})
            else:
                resolved_freshness = "UNKNOWN"
                degraded_items.append({"section": section, "index": index, "reason": "UNKNOWN_EVIDENCE"})
            _set_row_freshness(section, row, resolved_freshness)

    counts = {name: 0 for name in ("CURRENT", "STALE", "UNKNOWN", "NOT_APPLICABLE")}
    for source in source_by_id.values():
        freshness = str(source.get("freshness", "UNKNOWN"))
        counts[freshness if freshness in counts else "UNKNOWN"] += 1

    projection_health = "CURRENT" if not degraded_items else "DEGRADED"
    meta_freshness_state = "CURRENT" if projection_health == "CURRENT" else "STALE"
    meta = result.setdefault("meta", {})
    if isinstance(meta, MutableMapping):
        meta["generated_at"] = generated_at
        freshness_meta = meta.setdefault("freshness", {})
        if isinstance(freshness_meta, MutableMapping):
            freshness_meta["mode"] = "LIVE"
            freshness_meta["state"] = meta_freshness_state
            freshness_meta["as_of"] = generated_at
            freshness_meta["reason"] = (
                "R38 supersession/freshness resolver applied to current-state surfaces; "
                "historical events remain append-only and are not promoted to current truth."
            )

    receipt = {
        "schema_version": 1,
        "policy_version": str(policy.get("policy_version", "UNVERSIONED")),
        "generated_at": generated_at,
        "projection_health": projection_health,
        "snapshot_freshness_state": meta_freshness_state,
        "source_counts": counts,
        "legacy_freshness_normalization": legacy_freshness_normalization,
        "applied_supersession": applied_supersession,
        "ttl_audit": ttl_audit,
        "rewritten_current_state_refs": rewritten_refs,
        "current_state_degraded_items": degraded_items,
        "effect_boundary": {
            "read_only": True,
            "writes_performed": 0,
            "external_messages": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return {"snapshot": result, "receipt": receipt}
