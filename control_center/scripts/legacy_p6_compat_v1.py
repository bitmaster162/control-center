"""Explicit legacy Control Center -> P6 compatibility adapter.

Legacy prose is normalized here, not inside the generic P6 reducer.
No project-name substring can grant owner authority.
"""
from __future__ import annotations
import hashlib, json
from typing import Any, Mapping

AUTO_CUT = "AUTO_SOURCE_CUT"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def adapt_legacy_work_order(row: Mapping[str, Any], *, observed_at: str) -> dict[str, Any]:
    work_order = row.get("work_order")
    if not isinstance(work_order, str) or not work_order.strip():
        raise ValueError("LEGACY_WORK_ORDER_ID_REQUIRED")
    if not isinstance(row.get("do_not_touch"), bool):
        raise ValueError("LEGACY_EXPLICIT_OWNER_BOUNDARY_REQUIRED")

    reported_state = str(row.get("reported_state") or "")
    pending = reported_state.startswith("PENDING_") or reported_state == "GATED_RESERVED"
    apply_status = str(row.get("apply_status") or "NOT_APPLIED")
    if apply_status not in {"NOT_APPLIED", "APPLY_ELIGIBLE", "APPLIED", "SUPERSEDED"}:
        raise ValueError("LEGACY_APPLY_STATUS_INVALID")

    if apply_status == "APPLIED":
        readback_status = str(row.get("readback_status") or "REQUIRED")
    else:
        readback_status = str(row.get("readback_status") or "NOT_DUE")
    if readback_status not in {"NOT_DUE", "REQUIRED", "VERIFIED", "FAILED", "UNKNOWN"}:
        raise ValueError("LEGACY_READBACK_STATUS_INVALID")

    requested_action = None
    freshness = "FRESH"
    action_evidence_fresh = True
    claim_status = "PASS"
    if pending:
        requested_action = "LEGACY_DISPATCH::" + work_order
        freshness = "UNKNOWN"
        action_evidence_fresh = False
        claim_status = "HOLD"

    artifact_id = "legacy-work-order:" + work_order
    identity = {
        "work_order": work_order,
        "slot": row.get("slot"),
        "project": row.get("project"),
        "reported_state": reported_state,
        "apply_status": apply_status,
        "readback_status": readback_status,
        "do_not_touch": row["do_not_touch"],
    }
    return {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": AUTO_CUT,
        "subject_id": "work-order:" + work_order,
        "artifact_id": artifact_id,
        "artifact_sha256": _sha(identity),
        "source_class": "AUDIT",
        "authority_class": "FACTUAL_OBSERVATION",
        "observed_at": observed_at,
        "freshness": freshness,
        "logical_version": None,
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": reported_state or None,
        "claim_status": claim_status,
        "current_observation": True,
        "evidence_debt": pending,
        "transport_status": str(row.get("transport_status") or "REGISTRY_OBSERVED"),
        "semantic_status": str(row.get("semantic_status") or "UNREVIEWED"),
        "apply_status": apply_status,
        "readback_status": readback_status,
        "owner": str(row.get("owner") or "CONTROL_CENTER"),
        "do_not_touch": row["do_not_touch"],
        "requested_action": requested_action,
        "human_gate_required": False,
        "action_evidence_fresh": action_evidence_fresh,
        "effect_authorized": False,
        "execution_authorized": False,
    }
