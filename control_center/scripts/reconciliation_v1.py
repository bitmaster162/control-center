"""Pure deterministic Control Plane reconciliation reducer v1.

This module is additive and side-effect free. It does not write current state,
grant authority, apply changes, execute effects, deploy, send externally, or trade.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any, Iterable, Mapping

SEMANTIC_RANK = {
    "HUMAN_DECISION": 60,
    "CONTROLLER_ADJUDICATION": 50,
    "PROJECT_OWNER_DECISION": 45,
}
FACTUAL_CLASSES = {"PROVIDER_READBACK", "AUDIT"}
TRANSPORT_CLASSES = {"VERIFIED_RETURN", "TRANSPORT_OBSERVATION"}
BLOCKING_FACT = {"OPEN", "REVISE", "REJECT"}

TRUTH_STATUSES = {
    "CURRENT", "CURRENT_WITH_CONDITIONS", "STALE",
    "SUPERSEDED", "CONFLICT", "UNKNOWN",
}
SEMANTIC_STATUSES = {
    "UNREVIEWED", "ACCEPTED", "HOLD",
    "REVISE", "REJECTED", "SUPERSEDED",
}
ROUTES = {"NO_ACTION", "CONTROL_CENTER", "HUMAN_GATE", "OWNER_ONLY", "BLOCKED"}
READBACK_STATUSES = {"NOT_DUE", "REQUIRED", "VERIFIED", "FAILED", "UNKNOWN"}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _result_id(body: Mapping[str, Any]) -> str:
    return "rec-" + hashlib.sha256(_canonical_json(body)).hexdigest()


def _parse_observed_at(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("INVALID_OBSERVED_AT")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("INVALID_OBSERVED_AT") from exc
    if parsed.tzinfo is None:
        raise ValueError("OBSERVED_AT_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(dt.timezone.utc)


def _validate_envelope(records: list[Mapping[str, Any]]) -> tuple[str, str]:
    if not records:
        raise ValueError("NO_RECORDS")
    cuts = {record.get("source_cut_id") for record in records}
    subjects = {record.get("subject_id") for record in records}
    if None in cuts or len(cuts) != 1:
        raise ValueError("MIXED_SOURCE_CUT")
    if None in subjects or len(subjects) != 1:
        raise ValueError("MULTIPLE_SUBJECTS")
    for record in records:
        _parse_observed_at(record.get("observed_at"))
        if record.get("effect_authorized") is not False:
            raise ValueError("INPUT_EFFECT_AUTHORITY_NOT_ALLOWED")
        if record.get("execution_authorized") is not False:
            raise ValueError("INPUT_EXECUTION_AUTHORITY_NOT_ALLOWED")
        readback_status = record.get("readback_status")
        if readback_status is not None and readback_status not in READBACK_STATUSES:
            raise ValueError("INVALID_INPUT_READBACK_STATUS")
        if (
            record.get("apply_status") == "APPLIED"
            and record.get("source_class") != "CANONICAL_ACTIVE_STATE"
            and readback_status is None
        ):
            raise ValueError("APPLIED_RECORD_READBACK_STATUS_REQUIRED")
    return next(iter(cuts)), next(iter(subjects))


def _make_result(
    source_cut_id: str,
    subject_id: str,
    truth_status: str,
    semantic_status: str,
    route: str,
    reason_codes: Iterable[str],
    selected_refs: Iterable[str] = (),
    contradiction_refs: Iterable[str] = (),
    *,
    readback_required: bool = False,
    readback_status: str = "NOT_DUE",
) -> dict[str, Any]:
    if truth_status not in TRUTH_STATUSES:
        raise ValueError("INVALID_TRUTH_STATUS")
    if semantic_status not in SEMANTIC_STATUSES:
        raise ValueError("INVALID_SEMANTIC_STATUS")
    if route not in ROUTES:
        raise ValueError("INVALID_ROUTE")
    if readback_status not in READBACK_STATUSES:
        raise ValueError("INVALID_READBACK_STATUS")

    body = {
        "source_cut_id": source_cut_id,
        "subject_id": subject_id,
        "truth_status": truth_status,
        "semantic_status": semantic_status,
        "route": route,
        "reason_codes": sorted(set(reason_codes)) or ["RESOLVED"],
        "selected_refs": list(selected_refs),
        "contradiction_refs": list(contradiction_refs),
        "human_ripe": route == "HUMAN_GATE",
        "authority_granted": False,
        "auto_execute": False,
        "readback_required": bool(readback_required),
        "readback_status": readback_status,
        "effects": {
            "state_apply": False,
            "external_effect": False,
            "deployment": False,
            "trading": False,
            "wallet": False,
        },
        "can_trade": False,
        "capital_permission": "DENY",
    }
    return {
        "schema": "control_plane.reconciliation_result.v1",
        "result_id": _result_id(body),
        **body,
    }



def _resolve_readback(records: list[Mapping[str, Any]]) -> tuple[bool, str]:
    """Resolve explicit post-apply readback obligation without inferring execution.

    Canonical active-state APPLIED is not itself a pending readback obligation.
    Apply-capable records must carry an explicit readback_status (validated above).
    Any unresolved status wins fail-closed over VERIFIED.
    """
    statuses = [
        str(record.get("readback_status"))
        for record in records
        if record.get("readback_status") is not None
    ]
    if not statuses:
        return False, "NOT_DUE"
    if "FAILED" in statuses:
        return True, "FAILED"
    if "REQUIRED" in statuses:
        return True, "REQUIRED"
    if "UNKNOWN" in statuses:
        return True, "UNKNOWN"
    if "VERIFIED" in statuses:
        return False, "VERIFIED"
    return False, "NOT_DUE"

def _resolve_semantic(records: list[Mapping[str, Any]], cut: str, subject: str, readback_required: bool, readback_status: str):
    eligible = [
        record for record in records
        if record.get("source_class") in SEMANTIC_RANK
        and record.get("semantic_status") in {
            "ACCEPTED", "HOLD", "REVISE", "REJECTED", "SUPERSEDED"
        }
    ]
    if not eligible:
        return "UNREVIEWED", [], None

    top_rank = max(SEMANTIC_RANK[record["source_class"]] for record in eligible)
    top = [record for record in eligible if SEMANTIC_RANK[record["source_class"]] == top_rank]
    latest_time = max(_parse_observed_at(record["observed_at"]) for record in top)
    latest = [record for record in top if _parse_observed_at(record["observed_at"]) == latest_time]

    states = {record["semantic_status"] for record in latest}
    if len(states) > 1:
        return None, [], _make_result(
            cut,
            subject,
            "CONFLICT",
            "HOLD",
            "CONTROL_CENTER",
            ["EQUAL_AUTHORITY_EQUAL_TIME_SEMANTIC_CONTRADICTION"],
            (),
            sorted(record["artifact_id"] for record in latest),
            readback_required=readback_required,
            readback_status=readback_status,
        )

    chosen = min(latest, key=lambda record: (record["artifact_sha256"], record["artifact_id"]))
    return chosen["semantic_status"], [chosen["artifact_id"]], None


def resolve(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Resolve one subject within one source cut. Pure/no effects."""
    cut, subject = _validate_envelope(records)
    readback_required, readback_status = _resolve_readback(records)

    identity_conflicts = [
        record for record in records if record.get("freshness") == "IDENTITY_CONFLICT"
    ]
    if identity_conflicts:
        return _make_result(
            cut, subject, "CONFLICT", "HOLD", "BLOCKED",
            ["IDENTITY_CONFLICT"],
            (),
            sorted(record["artifact_id"] for record in identity_conflicts),
            readback_required=readback_required,
            readback_status=readback_status,
        )

    canonical = [
        record for record in records
        if record.get("source_class") == "CANONICAL_ACTIVE_STATE"
    ]
    if canonical:
        canonical_identities = {
            (
                record.get("artifact_id"),
                record.get("artifact_sha256"),
                json.dumps(record.get("claim_value"), sort_keys=True, ensure_ascii=False),
            )
            for record in canonical
        }
        if len(canonical_identities) > 1:
            return _make_result(
                cut, subject, "CONFLICT", "HOLD", "BLOCKED",
                ["MULTIPLE_CANONICAL_ACTIVE_STATES"],
                (),
                sorted(record["artifact_id"] for record in canonical),
                readback_required=readback_required,
                readback_status=readback_status,
            )
        active = min(canonical, key=lambda record: record["artifact_sha256"])
    else:
        active = None

    if active and active.get("claim_status") == "UNKNOWN" and active.get("claim_value") == "SUPERSEDED":
        return _make_result(
            cut, subject, "SUPERSEDED", "SUPERSEDED",
            "CONTROL_CENTER" if readback_required else "NO_ACTION",
            ["CANONICAL_SUPERSESSION", *( ["POST_APPLY_READBACK_REQUIRED"] if readback_required else [] )],
            [active["artifact_id"]],
            (),
            readback_required=readback_required,
            readback_status=readback_status,
        )

    # A fresh factual contradiction can block reliance on canonical truth but
    # cannot promote itself into semantic/current-truth authority.
    contradiction_refs: list[str] = []
    if active is not None:
        for record in records:
            if (
                record.get("source_class") in FACTUAL_CLASSES
                and record.get("current_observation") is True
                and record.get("freshness") == "FRESH"
                and record.get("claim_status") in BLOCKING_FACT
                and record.get("claim_value") != active.get("claim_value")
            ):
                contradiction_refs.append(record["artifact_id"])
        if contradiction_refs:
            return _make_result(
                cut, subject, "CONFLICT", "HOLD", "CONTROL_CENTER",
                ["FRESH_CURRENT_CONTRADICTION"],
                [active["artifact_id"]],
                sorted(contradiction_refs),
                readback_required=readback_required,
                readback_status=readback_status,
            )

    semantic, semantic_refs, semantic_conflict = _resolve_semantic(
        records, cut, subject, readback_required, readback_status
    )
    if semantic_conflict is not None:
        return semantic_conflict

    truth = "UNKNOWN"
    selected_refs: list[str] = []
    reasons: list[str] = []
    if active is not None:
        truth = "CURRENT_WITH_CONDITIONS" if active.get("evidence_debt") else "CURRENT"
        selected_refs.append(active["artifact_id"])
    selected_refs.extend(semantic_refs)

    # Explicit accepted successor intent does not activate itself.
    if active is not None and any(
        record.get("supersedes_id") == active.get("artifact_id")
        and record.get("semantic_status") == "ACCEPTED"
        for record in records
    ):
        reasons.append("ACCEPTED_SUCCESSOR_NOT_YET_CANONICALLY_APPLIED")

    # Routing before priority. Exact owner boundary always survives.
    if any(record.get("do_not_touch") is True for record in records):
        route = "OWNER_ONLY"
        reasons.append("OWNER_DO_NOT_TOUCH")
    elif readback_required:
        route = "CONTROL_CENTER"
        reasons.append("POST_APPLY_READBACK_REQUIRED")
    else:
        action_records = [
            record for record in records if record.get("requested_action")
        ]
        stale_action = any(
            record.get("freshness") in {"STALE", "UNKNOWN", "UNAVAILABLE", "IDENTITY_CONFLICT"}
            or record.get("action_evidence_fresh") is not True
            for record in action_records
        )
        if stale_action:
            route = "BLOCKED"
            reasons.append("STALE_OR_MISSING_REQUIRED_EVIDENCE")
        elif semantic == "ACCEPTED" and any(
            record.get("human_gate_required") is True
            and record.get("requested_action")
            and record.get("action_evidence_fresh") is True
            for record in records
        ):
            route = "HUMAN_GATE"
            reasons.append("EXACT_HUMAN_GATE_RIPE")
        elif semantic in {"UNREVIEWED", "HOLD", "REVISE"} or any(
            record.get("source_class") in TRANSPORT_CLASSES for record in records
        ):
            route = "CONTROL_CENTER"
            reasons.append("SEMANTIC_REVIEW_REQUIRED")
        elif semantic in {"REJECTED", "SUPERSEDED"}:
            route = "NO_ACTION"
            reasons.append("SEMANTIC_TERMINAL_NO_ACTION")
        else:
            route = "CONTROL_CENTER"
            reasons.append("DEFAULT_REVIEW_FAIL_CLOSED")

    return _make_result(
        cut, subject, truth, semantic, route,
        reasons, selected_refs, contradiction_refs,
        readback_required=readback_required,
        readback_status=readback_status,
    )
