"""Pure Control Center operator projection compiler v2.

One source cut in, one non-authority projection out.
No provider fetching, file writes, UI mutation, canonical mutation, dispatch,
apply, deploy, external send, trading, wallet, or capital effects.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FRESHNESS = {"FRESH", "STALE", "UNKNOWN", "UNAVAILABLE", "IDENTITY_CONFLICT"}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value.lower()) is not None


def _parse_time(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("INVALID_TIME")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("INVALID_TIME") from exc
    if parsed.tzinfo is None:
        raise ValueError("TIME_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(dt.timezone.utc)


def _exact_authority(anchor: Mapping[str, Any]) -> bool:
    return bool(
        anchor.get("available") is True
        and isinstance(anchor.get("generation"), str)
        and anchor.get("generation")
        and all(_valid_sha(anchor.get(key)) for key in (
            "pointer_sha256",
            "accepted_manifest_sha256",
            "current_state_sha256",
            "role_index_sha256",
            "role_views_sha256",
        ))
        and anchor.get("provider_readback") == "all_exact"
    )


def _exact_return_cursor(cursor: Mapping[str, Any]) -> bool:
    return bool(
        cursor.get("available") is True
        and isinstance(cursor.get("generation"), str)
        and cursor.get("generation")
        and _valid_sha(cursor.get("cursor_sha256"))
        and cursor.get("semantic_authority") is False
    )


def validate_source_envelope(source: Mapping[str, Any]) -> None:
    required = {
        "schema", "source_id", "source_class", "authority_scope",
        "locator", "identity", "observed_at", "fetched_at",
        "freshness", "payload_sha256", "required_for",
    }
    missing = required - set(source)
    if missing:
        raise ValueError("SOURCE_ENVELOPE_MISSING:" + ",".join(sorted(missing)))
    if source["schema"] != "control_plane.projection_source_envelope.v2":
        raise ValueError("SOURCE_ENVELOPE_SCHEMA")
    if source["source_class"] not in {
        "CANONICAL_AUTHORITY", "TRANSPORT_OBSERVATION", "PROVIDER_OBSERVATION"
    }:
        raise ValueError("SOURCE_CLASS")
    if not _valid_sha(source["payload_sha256"]):
        raise ValueError("SOURCE_PAYLOAD_SHA")
    _parse_time(source["observed_at"])
    _parse_time(source["fetched_at"])
    freshness = source["freshness"]
    if not isinstance(freshness, Mapping) or freshness.get("verdict") not in _FRESHNESS:
        raise ValueError("SOURCE_FRESHNESS")
    if not isinstance(source["required_for"], list):
        raise ValueError("SOURCE_REQUIRED_FOR")


def source_manifest(
    authority_anchor: Mapping[str, Any],
    return_plane_cursor: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not _exact_authority(authority_anchor):
        raise ValueError("CANONICAL_AUTHORITY_NOT_EXACT")
    if not _exact_return_cursor(return_plane_cursor):
        raise ValueError("RETURN_CURSOR_NOT_EXACT")

    for source in sources:
        validate_source_envelope(source)

    entries = [
        {
            "source_id": "continuityos:canonical-authority",
            "source_class": "CANONICAL_AUTHORITY",
            "payload_sha256": authority_anchor["pointer_sha256"],
        },
        {
            "source_id": "return-plane:cursor",
            "source_class": "TRANSPORT_OBSERVATION",
            "payload_sha256": return_plane_cursor["cursor_sha256"],
        },
    ]
    entries.extend(
        {
            "source_id": source["source_id"],
            "source_class": source["source_class"],
            "payload_sha256": source["payload_sha256"],
        }
        for source in sources
    )
    entries.sort(key=lambda item: (item["source_id"], item["source_class"], item["payload_sha256"]))
    return {
        "schema": "control_plane.projection_source_manifest.v2",
        "entries": entries,
    }


def compute_source_cut(
    authority_anchor: Mapping[str, Any],
    return_plane_cursor: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    manifest = source_manifest(authority_anchor, return_plane_cursor, sources)
    manifest_sha = _sha(manifest)
    cut_payload = {
        "pointer_sha256": authority_anchor["pointer_sha256"],
        "accepted_manifest_sha256": authority_anchor["accepted_manifest_sha256"],
        "current_state_sha256": authority_anchor["current_state_sha256"],
        "role_index_sha256": authority_anchor["role_index_sha256"],
        "role_views_sha256": authority_anchor["role_views_sha256"],
        "return_plane_cursor_sha256": return_plane_cursor["cursor_sha256"],
        "provider_payload_sha256s": sorted(source["payload_sha256"] for source in sources),
    }
    return {
        "source_cut_id": "cut-" + _sha(cut_payload),
        "source_manifest_sha256": manifest_sha,
        "source_count": len(manifest["entries"]),
        "all_views_same_cut": True,
        "manifest": manifest,
    }


def _freshness_summary(sources: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter = Counter(source["freshness"]["verdict"].lower() for source in sources)
    return {
        "fresh": counter["fresh"],
        "stale": counter["stale"],
        "unknown": counter["unknown"],
        "unavailable": counter["unavailable"],
        "identity_conflict": counter["identity_conflict"],
    }


def _required_source_not_fresh(
    sources: Sequence[Mapping[str, Any]],
    subject_id: str,
) -> bool:
    tokens = {subject_id, f"subject:{subject_id}", "HUMAN_GATE"}
    for source in sources:
        if source["freshness"]["verdict"] == "FRESH":
            continue
        if tokens.intersection(set(str(x) for x in source.get("required_for", []))):
            return True
    return False


def _projection_id(body: Mapping[str, Any]) -> str:
    return "ccp-" + _sha(body)


def _unavailable_projection(
    generated_at: str,
    authority_anchor: Mapping[str, Any],
    return_plane_cursor: Mapping[str, Any],
    reason: str,
) -> dict[str, Any]:
    safe_anchor = (
        dict(authority_anchor)
        if authority_anchor.get("available") is False
        else {"available": False, "reason": reason}
    )
    safe_cursor = {
        "available": bool(return_plane_cursor.get("available") is True),
        "generation": return_plane_cursor.get("generation"),
        "cursor_sha256": return_plane_cursor.get("cursor_sha256") if _valid_sha(return_plane_cursor.get("cursor_sha256")) else None,
        "semantic_authority": False,
        "reason": return_plane_cursor.get("reason"),
    }
    body = {
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "terminal": "PROJECTION_UNAVAILABLE",
        "generated_at": generated_at,
        "source_cut": None,
        "authority_anchor": safe_anchor,
        "return_plane_cursor": safe_cursor,
        "freshness_summary": {
            "fresh": 0, "stale": 0, "unknown": 0,
            "unavailable": 1, "identity_conflict": 0,
        },
        "views": {},
        "diagnostics": {
            "reason_codes": [reason],
            "mixed_result_cuts": [],
            "human_gate_suppressed": [],
        },
        "safety": {
            "can_trade": False,
            "capital_permission": "DENY",
            "deploy_permission": "DENY",
            "auto_dispatch": False,
            "auto_apply": False,
            "auto_execute": False,
            "self_application": False,
        },
        "invariants": [
            "DASHBOARD != TRUTH_OWNER",
            "PROJECTION != AUTHORITY",
            "ONE_RENDERED_PAGE == ONE_SOURCE_CUT",
            "can_trade=false",
            "capital_permission=DENY",
        ],
    }
    return {
        "schema": "control_center.operator_projection.v2",
        "projection_id": _projection_id(body),
        **body,
    }


def compile_projection(
    *,
    authority_anchor: Mapping[str, Any],
    return_plane_cursor: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    reconciliations: Sequence[Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """Compile one immutable, non-authority operator projection."""
    _parse_time(generated_at)

    if not _exact_authority(authority_anchor):
        return _unavailable_projection(
            generated_at, authority_anchor, return_plane_cursor,
            "CANONICAL_AUTHORITY_NOT_EXACT",
        )
    if not _exact_return_cursor(return_plane_cursor):
        return _unavailable_projection(
            generated_at, authority_anchor, return_plane_cursor,
            "RETURN_CURSOR_NOT_EXACT",
        )

    try:
        cut = compute_source_cut(authority_anchor, return_plane_cursor, sources)
    except ValueError as exc:
        return _unavailable_projection(
            generated_at, authority_anchor, return_plane_cursor,
            str(exc),
        )

    cut_id = cut["source_cut_id"]
    mixed_cuts = sorted({
        str(result.get("source_cut_id"))
        for result in reconciliations
        if result.get("source_cut_id") != cut_id
    })

    summary = _freshness_summary(sources)
    reasons: list[str] = []
    terminal = "PROJECTION_READY"

    if summary["identity_conflict"]:
        terminal = "PROJECTION_HOLD"
        reasons.append("SOURCE_IDENTITY_CONFLICT")
    elif mixed_cuts:
        terminal = "PROJECTION_HOLD"
        reasons.append("MIXED_RECONCILIATION_SOURCE_CUT")
    elif summary["stale"] or summary["unknown"] or summary["unavailable"]:
        terminal = "PROJECTION_DEGRADED"
        reasons.append("NONFRESH_OBSERVATION_PRESENT")

    # Fail closed: stateful views are compiled only from results that bind this cut.
    valid_results = [
        result for result in reconciliations
        if result.get("source_cut_id") == cut_id
    ]
    valid_results.sort(key=lambda result: (
        str(result.get("subject_id")),
        str(result.get("result_id")),
    ))

    human_now = []
    human_gate_suppressed = []
    blocked = []
    owner_only = []
    conflicts = []
    readback_required = []
    results_view = []

    for result in valid_results:
        subject = str(result.get("subject_id"))
        route = result.get("route")
        truth = result.get("truth_status")

        if route == "HUMAN_GATE":
            if _required_source_not_fresh(sources, subject):
                human_gate_suppressed.append(subject)
                blocked.append(subject)
                reasons.append("HUMAN_GATE_SUPPRESSED_NONFRESH_REQUIRED_SOURCE")
            else:
                human_now.append(subject)
        elif route == "BLOCKED":
            blocked.append(subject)
        elif route == "OWNER_ONLY":
            owner_only.append(subject)

        if truth == "CONFLICT":
            conflicts.append(subject)
        if result.get("readback_required") is True:
            readback_required.append(subject)

        results_view.append({
            "source_cut_id": cut_id,
            "result_id": result.get("result_id"),
            "subject_id": subject,
            "truth_status": truth,
            "semantic_status": result.get("semantic_status"),
            "route": "BLOCKED" if subject in human_gate_suppressed else route,
            "reason_codes": list(result.get("reason_codes") or []),
            "readback_required": bool(result.get("readback_required")),
            "readback_status": result.get("readback_status", "NOT_DUE"),
        })

    human_all = sorted(set(human_now))
    human_top = human_all[:3]
    human_overflow = human_all[3:]

    views = {
        "overview": {
            "source_cut_id": cut_id,
            "subjects": len(valid_results),
            "human_now": len(human_all),
            "human_now_top3": len(human_top),
            "human_now_overflow": len(human_overflow),
            "blocked": len(set(blocked)),
            "owner_only": len(owner_only),
            "conflicts": len(conflicts),
            "readback_required": len(set(readback_required)),
        },
        "human_now": {
            "source_cut_id": cut_id,
            "items": human_all,
            "top_items": human_top,
            "overflow_count": len(human_overflow),
            "overflow_items": human_overflow,
        },
        "blocked": {
            "source_cut_id": cut_id,
            "items": sorted(set(blocked)),
        },
        "owner_only": {
            "source_cut_id": cut_id,
            "items": sorted(set(owner_only)),
        },
        "conflicts": {
            "source_cut_id": cut_id,
            "items": sorted(set(conflicts)),
        },
        "readback_required": {
            "source_cut_id": cut_id,
            "items": sorted(set(readback_required)),
        },
        "results": {
            "source_cut_id": cut_id,
            "items": results_view,
        },
    }

    # A stale required dependency can degrade the projection but cannot smuggle
    # a HUMAN_GATE through the cockpit.
    if human_gate_suppressed and terminal == "PROJECTION_READY":
        terminal = "PROJECTION_DEGRADED"

    body = {
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "terminal": terminal,
        "generated_at": generated_at,
        "source_cut": {
            key: cut[key]
            for key in (
                "source_cut_id", "source_manifest_sha256",
                "source_count", "all_views_same_cut",
            )
        },
        "authority_anchor": dict(authority_anchor),
        "return_plane_cursor": dict(return_plane_cursor),
        "freshness_summary": summary,
        "views": views,
        "diagnostics": {
            "reason_codes": sorted(set(reasons)) or ["PROJECTION_COHERENT"],
            "mixed_result_cuts": mixed_cuts,
            "human_gate_suppressed": sorted(set(human_gate_suppressed)),
        },
        "safety": {
            "can_trade": False,
            "capital_permission": "DENY",
            "deploy_permission": "DENY",
            "auto_dispatch": False,
            "auto_apply": False,
            "auto_execute": False,
            "self_application": False,
        },
        "invariants": [
            "DASHBOARD != TRUTH_OWNER",
            "PROJECTION != AUTHORITY",
            "RETURN_PLANE != SEMANTIC_AUTHORITY",
            "STALE_OBSERVATION != CURRENT_FACT",
            "LAST_KNOWN != CURRENT",
            "PRIORITY != AUTHORITY",
            "QUEUE != EXECUTION_AUTHORIZATION",
            "ONE_RENDERED_PAGE == ONE_SOURCE_CUT",
            "NO_HARDCODED_CANONICAL_GENERATION",
            "NO_CLIENT_SIDE_STATE_JOIN",
            "HUMAN_NOW_DATA_PRESERVES_ALL_RIPE_ITEMS",
            "COCKPIT_HUMAN_NOW_TOP3_PLUS_OVERFLOW",
            "POST_APPLY_READBACK_REMAINS_EXPLICIT",
            "can_trade=false",
            "capital_permission=DENY",
        ],
    }
    return {
        "schema": "control_center.operator_projection.v2",
        "projection_id": _projection_id(body),
        **body,
    }
