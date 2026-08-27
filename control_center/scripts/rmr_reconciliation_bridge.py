"""Fail-closed RMR evidence -> Control Plane reconciliation-record bridge.

This module is deterministic and side-effect free. It does not call RMR, write
Current Truth, grant semantic authority, apply state, execute effects, deploy,
send externally, trade, or touch capital.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from typing import Any, Mapping

from control_center.scripts.rmr_evidence_consumer import (
    EvidenceConsumerError,
    RMREvidenceConsumer,
)

PINNED_RMR_HEAD = "8f82ad49c6ddcde7c698eec101b5f0ed985f24bc"
PINNED_RMR_TREE = "911467a1a1d355b51fbe70ff95b86cd63fb7a212"
PINNED_RMR_IDENTITY_SHA256 = "271ba9ba2f78c0cd03db7cb16ae3d2dbe9511926703658d5288677956bff02c2"
PINNED_IDENTITY_BINDING = "PINNED_CONFIG_PLUS_RUNTIME_IDENTITY_MATCH"
EXPECTED_AUTHORITY_CLASS = "EVIDENCE_ONLY"
EXPECTED_ROUTER_STATUS = "CANDIDATE_NOT_LIVE"
EXPECTED_SERVICE_STATUS = "READY_LOOPBACK_ONLY"

ALLOWED_OPERATIONS = frozenset(
    {
        "status", "search_text", "search_all", "search_messages", "search_documents",
        "search_events", "search_project_events", "search_claims", "get_message",
        "get_message_occurrences", "get_message_variants", "get_document", "get_event",
        "get_claim", "get_handoff", "get_checkpoint", "get_continuity_candidate",
        "get_current_truth_candidate", "get_project", "get_evidence", "get_git_refs",
        "get_conflicts", "coverage",
    }
)
BRIDGEABLE_DECISIONS = frozenset(
    {"EVIDENCE_ACCEPTED_FOR_REVIEW", "EVIDENCE_PARTIAL", "EVIDENCE_CONFLICT", "EVIDENCE_GAP"}
)
REJECTED_DECISIONS = frozenset(
    {"EVIDENCE_REJECTED_STALE_OR_IDENTITY_MISMATCH", "EVIDENCE_REJECTED_HEALTH_OR_AUTH_FAILURE"}
)
ALL_DECISIONS = BRIDGEABLE_DECISIONS | REJECTED_DECISIONS
EXPECTED_FIELDS = frozenset(
    {
        "request_id", "timestamp_utc", "rmr_head", "rmr_tree", "rmr_identity_sha256",
        "rmr_identity_binding", "operation", "input_digest_sha256", "returned_count",
        "has_more", "authority_class", "router_status", "provenance_status",
        "coverage_warning", "conflict_indication", "response_digest_sha256",
        "consumer_decision", "elapsed_ms", "evidence", "current_truth_promoted",
        "execution_authority",
    }
)
CUT_RE = re.compile(r"^cut-[0-9a-f]{64}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class RMRReconciliationBridgeError(ValueError):
    """Fail-closed bridge validation error."""


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RMRReconciliationBridgeError("ENVELOPE_NOT_CANONICAL_JSON") from exc


def _nonbool_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_hex64(value: Any, field: str) -> str:
    if not isinstance(value, str) or HEX64_RE.fullmatch(value) is None:
        raise RMRReconciliationBridgeError(f"INVALID_{field.upper()}")
    return value


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RMRReconciliationBridgeError("INVALID_TIMESTAMP_UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise RMRReconciliationBridgeError("INVALID_TIMESTAMP_UTC") from exc
    if parsed.tzinfo is None:
        raise RMRReconciliationBridgeError("TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return value


def _validate_provenance(value: Any) -> None:
    if value is None or isinstance(value, str):
        return
    if isinstance(value, list):
        if any(not isinstance(item, str) for item in value):
            raise RMRReconciliationBridgeError("INVALID_PROVENANCE_STATUS")
        if len(set(value)) != len(value):
            raise RMRReconciliationBridgeError("DUPLICATE_PROVENANCE_STATUS")
        return
    raise RMRReconciliationBridgeError("INVALID_PROVENANCE_STATUS")


def _require_raw_currentness(operation: str, evidence: Mapping[str, Any]) -> None:
    expected_operation = "search_messages" if operation == "search_text" else operation
    if evidence.get("operation") != expected_operation:
        raise RMRReconciliationBridgeError("RAW_OPERATION_ECHO_MISMATCH")
    if evidence.get("read_only") is not True:
        raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:read_only")
    if evidence.get("authority_class") != EXPECTED_AUTHORITY_CLASS:
        raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:authority_class")

    exact_optional = {
        "router_status": EXPECTED_ROUTER_STATUS,
        "service_status": EXPECTED_SERVICE_STATUS,
        "source_head": PINNED_RMR_HEAD,
        "source_tree": PINNED_RMR_TREE,
        "approved_source_head": PINNED_RMR_HEAD,
        "approved_source_tree": PINNED_RMR_TREE,
    }
    for field, expected in exact_optional.items():
        if field in evidence and evidence.get(field) != expected:
            raise RMRReconciliationBridgeError(f"RAW_CURRENTNESS_MISMATCH:{field}")

    if "query_only" in evidence:
        query_only = evidence.get("query_only")
        if not _nonbool_int(query_only) or query_only != 1:
            raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:query_only")
    if "source_identity_runtime_bound" in evidence and evidence.get("source_identity_runtime_bound") is not True:
        raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:source_identity_runtime_bound")
    if "tracked_file_hashes_match" in evidence and evidence.get("tracked_file_hashes_match") is not True:
        raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:tracked_file_hashes_match")
    if "source_identity" in evidence:
        source_identity = evidence.get("source_identity")
        if not isinstance(source_identity, Mapping) or source_identity.get("identity_match") is not True:
            raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:source_identity")
    if "build_identity" in evidence:
        build_identity = evidence.get("build_identity")
        if not isinstance(build_identity, Mapping):
            raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:build_identity")
        if build_identity.get("source_head") != PINNED_RMR_HEAD:
            raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:build_identity_head")
        if build_identity.get("source_tree") != PINNED_RMR_TREE:
            raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:build_identity_tree")
    if "current_truth_promoted" in evidence and evidence.get("current_truth_promoted") is not False:
        raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:current_truth_promoted")
    if "execution_authority" in evidence and evidence.get("execution_authority") != "NONE":
        raise RMRReconciliationBridgeError("RAW_CURRENTNESS_MISMATCH:execution_authority")


def _derive_consumer_metadata(operation: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Replay the accepted consumer's pure response-shape/classification semantics."""
    _require_raw_currentness(operation, evidence)
    try:
        RMREvidenceConsumer._validate_response_metadata(evidence)
        returned_count = RMREvidenceConsumer._returned_count(evidence)
        provenance_status = RMREvidenceConsumer._provenance_status(evidence)
        decision, coverage_warning, conflict_indication, has_more = RMREvidenceConsumer._classify(evidence)
    except EvidenceConsumerError as exc:
        raise RMRReconciliationBridgeError("RAW_EVIDENCE_RECLASSIFICATION_FAILED") from exc
    return {
        "returned_count": returned_count,
        "has_more": has_more,
        "provenance_status": provenance_status,
        "coverage_warning": coverage_warning,
        "conflict_indication": conflict_indication,
        "consumer_decision": decision,
    }


def _require_derived_metadata_binding(envelope: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
    derived = _derive_consumer_metadata(str(envelope["operation"]), evidence)
    for field, expected in derived.items():
        if envelope.get(field) != expected:
            raise RMRReconciliationBridgeError(f"DERIVED_METADATA_MISMATCH:{field}")


def validate_rmr_envelope(envelope: Mapping[str, Any]) -> None:
    if not isinstance(envelope, Mapping):
        raise RMRReconciliationBridgeError("ENVELOPE_NOT_OBJECT")
    keys = set(envelope)
    missing = EXPECTED_FIELDS - keys
    unexpected = keys - EXPECTED_FIELDS
    if missing:
        raise RMRReconciliationBridgeError("MISSING_FIELDS:" + ",".join(sorted(missing)))
    if unexpected:
        raise RMRReconciliationBridgeError("UNEXPECTED_FIELDS:" + ",".join(sorted(unexpected)))

    request_id = envelope.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise RMRReconciliationBridgeError("INVALID_REQUEST_ID")
    _validate_timestamp(envelope.get("timestamp_utc"))

    exact = {
        "rmr_head": PINNED_RMR_HEAD,
        "rmr_tree": PINNED_RMR_TREE,
        "rmr_identity_sha256": PINNED_RMR_IDENTITY_SHA256,
        "rmr_identity_binding": PINNED_IDENTITY_BINDING,
        "authority_class": EXPECTED_AUTHORITY_CLASS,
        "router_status": EXPECTED_ROUTER_STATUS,
        "current_truth_promoted": False,
        "execution_authority": "NONE",
    }
    for field, expected in exact.items():
        if envelope.get(field) != expected:
            raise RMRReconciliationBridgeError(f"BINDING_MISMATCH:{field}")

    operation = envelope.get("operation")
    if operation not in ALLOWED_OPERATIONS:
        raise RMRReconciliationBridgeError("UNSUPPORTED_OPERATION")
    _require_hex64(envelope.get("input_digest_sha256"), "input_digest_sha256")
    declared_response_digest = _require_hex64(envelope.get("response_digest_sha256"), "response_digest_sha256")

    returned_count = envelope.get("returned_count")
    if not _nonbool_int(returned_count) or returned_count < 0:
        raise RMRReconciliationBridgeError("INVALID_RETURNED_COUNT")
    if not isinstance(envelope.get("has_more"), bool):
        raise RMRReconciliationBridgeError("INVALID_HAS_MORE")
    _validate_provenance(envelope.get("provenance_status"))
    coverage_warning = envelope.get("coverage_warning")
    if coverage_warning is not None and not isinstance(coverage_warning, str):
        raise RMRReconciliationBridgeError("INVALID_COVERAGE_WARNING")
    if not isinstance(envelope.get("conflict_indication"), bool):
        raise RMRReconciliationBridgeError("INVALID_CONFLICT_INDICATION")

    elapsed_ms = envelope.get("elapsed_ms")
    if not _nonbool_int(elapsed_ms) or elapsed_ms < 0:
        raise RMRReconciliationBridgeError("INVALID_ELAPSED_MS")
    evidence = envelope.get("evidence")
    if not isinstance(evidence, Mapping):
        raise RMRReconciliationBridgeError("INVALID_EVIDENCE_OBJECT")

    actual_response_digest = hashlib.sha256(_canonical_json_bytes(dict(evidence))).hexdigest()
    if actual_response_digest != declared_response_digest:
        raise RMRReconciliationBridgeError("RESPONSE_DIGEST_MISMATCH")

    decision = envelope.get("consumer_decision")
    if decision not in ALL_DECISIONS:
        raise RMRReconciliationBridgeError("INVALID_CONSUMER_DECISION")
    if decision in REJECTED_DECISIONS:
        raise RMRReconciliationBridgeError("RMR_EVIDENCE_NOT_BRIDGEABLE:" + str(decision))

    # Stronger than R85: the top-level transport metadata must be exactly the
    # metadata that the accepted consumer deterministically derives from the
    # digested raw evidence body. No caller may rewrite pagination, provenance,
    # coverage, conflict, or the consumer decision after evidence production.
    _require_derived_metadata_binding(envelope, evidence)

    _canonical_json_bytes(dict(envelope))


def bridge_rmr_evidence(envelope: Mapping[str, Any], *, source_cut_id: str, subject_id: str) -> dict[str, Any]:
    """Return one authority-bounded reconciliation record; perform no effects."""
    validate_rmr_envelope(envelope)
    if not isinstance(source_cut_id, str) or CUT_RE.fullmatch(source_cut_id) is None:
        raise RMRReconciliationBridgeError("INVALID_SOURCE_CUT_ID")
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise RMRReconciliationBridgeError("INVALID_SUBJECT_ID")

    canonical = _canonical_json_bytes(dict(envelope))
    artifact_sha256 = hashlib.sha256(canonical).hexdigest()
    decision = str(envelope["consumer_decision"])
    claim_status = {
        "EVIDENCE_ACCEPTED_FOR_REVIEW": "PASS",
        "EVIDENCE_PARTIAL": "PARTIAL",
        "EVIDENCE_GAP": "PARTIAL",
        "EVIDENCE_CONFLICT": "HOLD",
    }[decision]
    evidence_debt = decision != "EVIDENCE_ACCEPTED_FOR_REVIEW"
    claim_value = {
        "kind": "RMR_EVIDENCE_TRANSPORT_OBSERVATION_V1",
        "request_id": envelope["request_id"],
        "operation": envelope["operation"],
        "input_digest_sha256": envelope["input_digest_sha256"],
        "response_digest_sha256": envelope["response_digest_sha256"],
        "consumer_decision": decision,
        "returned_count": envelope["returned_count"],
        "has_more": envelope["has_more"],
        "provenance_status": envelope["provenance_status"],
        "coverage_warning": envelope["coverage_warning"],
        "conflict_indication": envelope["conflict_indication"],
        "rmr_head": envelope["rmr_head"],
        "rmr_tree": envelope["rmr_tree"],
        "rmr_identity_sha256": envelope["rmr_identity_sha256"],
    }
    return {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": source_cut_id,
        "subject_id": subject_id.strip(),
        "artifact_id": "rmr-evidence-" + artifact_sha256,
        "artifact_sha256": artifact_sha256,
        "source_class": "TRANSPORT_OBSERVATION",
        "authority_class": "TRANSPORT_ONLY",
        "observed_at": envelope["timestamp_utc"],
        "freshness": "FRESH",
        "logical_version": "RMR_EVIDENCE_ENVELOPE_V1",
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": claim_value,
        "claim_status": claim_status,
        "current_observation": False,
        "evidence_debt": evidence_debt,
        "transport_status": decision,
        "semantic_status": "UNREVIEWED",
        "apply_status": "NOT_APPLIED",
        "owner": "CONTROL_CENTER",
        "do_not_touch": False,
        "requested_action": None,
        "human_gate_required": False,
        "action_evidence_fresh": False,
        "effect_authorized": False,
        "execution_authorized": False,
        "readback_status": "NOT_DUE",
    }
