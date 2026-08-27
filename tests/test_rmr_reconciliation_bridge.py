from __future__ import annotations

import copy
import hashlib
import json

import pytest

from control_center.scripts.rmr_reconciliation_bridge import (
    PINNED_RMR_HEAD,
    PINNED_RMR_IDENTITY_SHA256,
    PINNED_RMR_TREE,
    RMRReconciliationBridgeError,
    bridge_rmr_evidence,
)
from control_center.scripts.reconciliation_v1 import resolve

CUT = "cut-" + hashlib.sha256(b"rmr-r87-source-cut").hexdigest()
SUBJECT = "rmr:memory-evidence"


def digest_json(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def raw_evidence(decision: str = "EVIDENCE_ACCEPTED_FOR_REVIEW") -> dict:
    if decision == "EVIDENCE_PARTIAL":
        provenance, has_more, conflict = "PARTIAL_PROVENANCE", False, False
    elif decision == "EVIDENCE_GAP":
        provenance, has_more, conflict = "DIRECT_SOURCE_BACKED", True, False
    elif decision == "EVIDENCE_CONFLICT":
        provenance, has_more, conflict = "DIRECT_SOURCE_BACKED", False, True
    else:
        provenance, has_more, conflict = "DIRECT_SOURCE_BACKED", False, False
    return {
        "operation": "search_messages",
        "read_only": True,
        "authority_class": "EVIDENCE_ONLY",
        "router_status": "CANDIDATE_NOT_LIVE",
        "returned_count": 1,
        "has_more": has_more,
        "provenance_status": provenance,
        "conflict_indication": conflict,
        "rows": [{"text": "opaque evidence", "provenance_status": provenance, "conflict_indication": conflict}],
    }


def envelope(decision: str = "EVIDENCE_ACCEPTED_FOR_REVIEW") -> dict:
    evidence = raw_evidence(decision)
    coverage = None
    return {
        "request_id": "r87-test-request",
        "timestamp_utc": "2026-08-27T13:57:30Z",
        "rmr_head": PINNED_RMR_HEAD,
        "rmr_tree": PINNED_RMR_TREE,
        "rmr_identity_sha256": PINNED_RMR_IDENTITY_SHA256,
        "rmr_identity_binding": "PINNED_CONFIG_PLUS_RUNTIME_IDENTITY_MATCH",
        "operation": "search_text",
        "input_digest_sha256": "a" * 64,
        "returned_count": 1,
        "has_more": evidence["has_more"],
        "authority_class": "EVIDENCE_ONLY",
        "router_status": "CANDIDATE_NOT_LIVE",
        "provenance_status": evidence["provenance_status"],
        "coverage_warning": coverage,
        "conflict_indication": evidence["conflict_indication"],
        "response_digest_sha256": digest_json(evidence),
        "consumer_decision": decision,
        "elapsed_ms": 11,
        "evidence": evidence,
        "current_truth_promoted": False,
        "execution_authority": "NONE",
    }


def test_clean_bridge_has_fixed_non_authority_mapping():
    record = bridge_rmr_evidence(envelope(), source_cut_id=CUT, subject_id=SUBJECT)
    assert record["source_class"] == "TRANSPORT_OBSERVATION"
    assert record["authority_class"] == "TRANSPORT_ONLY"
    assert record["semantic_status"] == "UNREVIEWED"
    assert record["apply_status"] == "NOT_APPLIED"
    assert record["current_observation"] is False
    assert record["requested_action"] is None
    assert record["human_gate_required"] is False
    assert record["action_evidence_fresh"] is False
    assert record["effect_authorized"] is False
    assert record["execution_authorized"] is False
    assert record["readback_status"] == "NOT_DUE"
    assert record["claim_status"] == "PASS"
    assert record["evidence_debt"] is False


def test_downstream_reducer_routes_transport_to_control_center_only():
    result = resolve([bridge_rmr_evidence(envelope(), source_cut_id=CUT, subject_id=SUBJECT)])
    assert (result["truth_status"], result["semantic_status"], result["route"]) == ("UNKNOWN", "UNREVIEWED", "CONTROL_CENTER")
    assert result["authority_granted"] is False
    assert result["auto_execute"] is False
    assert not any(result["effects"].values())
    assert result["can_trade"] is False
    assert result["capital_permission"] == "DENY"


@pytest.mark.parametrize("decision,claim", [("EVIDENCE_PARTIAL", "PARTIAL"), ("EVIDENCE_GAP", "PARTIAL"), ("EVIDENCE_CONFLICT", "HOLD")])
def test_nonclean_decisions_remain_unreviewed_transport(decision, claim):
    record = bridge_rmr_evidence(envelope(decision), source_cut_id=CUT, subject_id=SUBJECT)
    assert record["claim_status"] == claim
    assert record["evidence_debt"] is True
    result = resolve([record])
    assert result["semantic_status"] == "UNREVIEWED"
    assert result["route"] == "CONTROL_CENTER"


def test_r84_digest_tamper_still_fails_closed():
    payload = envelope()
    old = payload["response_digest_sha256"]
    payload["evidence"]["rows"][0]["text"] = "tampered"
    assert digest_json(payload["evidence"]) != old
    with pytest.raises(RMRReconciliationBridgeError, match="RESPONSE_DIGEST_MISMATCH"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_r86_has_more_and_decision_rewrite_fails_closed():
    payload = envelope("EVIDENCE_GAP")
    payload["has_more"] = False
    payload["consumer_decision"] = "EVIDENCE_ACCEPTED_FOR_REVIEW"
    with pytest.raises(RMRReconciliationBridgeError, match="DERIVED_METADATA_MISMATCH"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("returned_count", 0),
        ("has_more", True),
        ("provenance_status", "CANDIDATE_ONLY"),
        ("coverage_warning", "forged warning"),
        ("conflict_indication", True),
        ("consumer_decision", "EVIDENCE_GAP"),
    ],
)
def test_each_derived_field_is_bound_to_raw_evidence(field, bad_value):
    payload = envelope()
    payload[field] = bad_value
    with pytest.raises(RMRReconciliationBridgeError, match=f"DERIVED_METADATA_MISMATCH:{field}"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_raw_coverage_warning_reclassifies_and_top_level_must_match():
    payload = envelope()
    payload["evidence"]["coverage_warning"] = "bounded coverage"
    payload["response_digest_sha256"] = digest_json(payload["evidence"])
    with pytest.raises(RMRReconciliationBridgeError, match="DERIVED_METADATA_MISMATCH:coverage_warning"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_raw_operation_echo_must_match_search_text_translation():
    payload = envelope()
    payload["evidence"]["operation"] = "search_documents"
    payload["response_digest_sha256"] = digest_json(payload["evidence"])
    with pytest.raises(RMRReconciliationBridgeError, match="RAW_OPERATION_ECHO_MISMATCH"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


@pytest.mark.parametrize("field,bad", [("read_only", False), ("authority_class", "LIVE_AUTHORITY"), ("router_status", "LIVE")])
def test_raw_currentness_ceiling_is_rechecked(field, bad):
    payload = envelope()
    payload["evidence"][field] = bad
    payload["response_digest_sha256"] = digest_json(payload["evidence"])
    with pytest.raises(RMRReconciliationBridgeError, match="RAW_CURRENTNESS_MISMATCH"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_raw_optional_current_truth_and_execution_claims_fail_closed():
    for field, bad in [("current_truth_promoted", True), ("execution_authority", "EXECUTE")]:
        payload = envelope()
        payload["evidence"][field] = bad
        payload["response_digest_sha256"] = digest_json(payload["evidence"])
        with pytest.raises(RMRReconciliationBridgeError, match="RAW_CURRENTNESS_MISMATCH"):
            bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_raw_evidence_cannot_smuggle_semantic_or_apply_authority():
    payload = envelope()
    payload["evidence"].update({"semantic_status": "ACCEPTED", "apply_status": "APPLIED", "requested_action": "APPLY"})
    payload["response_digest_sha256"] = digest_json(payload["evidence"])
    record = bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)
    assert record["semantic_status"] == "UNREVIEWED"
    assert record["apply_status"] == "NOT_APPLIED"
    assert record["requested_action"] is None


def test_top_level_forged_semantic_field_is_rejected():
    payload = envelope(); payload["semantic_status"] = "ACCEPTED"
    with pytest.raises(RMRReconciliationBridgeError, match="UNEXPECTED_FIELDS"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


@pytest.mark.parametrize("field,bad", [("rmr_head", "0"*40), ("rmr_tree", "0"*40), ("rmr_identity_sha256", "0"*64), ("authority_class", "LIVE_AUTHORITY"), ("router_status", "LIVE"), ("current_truth_promoted", True), ("execution_authority", "EXECUTE")])
def test_top_level_identity_authority_drift_fails_closed(field, bad):
    payload = envelope(); payload[field] = bad
    with pytest.raises(RMRReconciliationBridgeError, match="BINDING_MISMATCH"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_rejected_consumer_decisions_never_bridge():
    for decision in ["EVIDENCE_REJECTED_STALE_OR_IDENTITY_MISMATCH", "EVIDENCE_REJECTED_HEALTH_OR_AUTH_FAILURE"]:
        payload = envelope("EVIDENCE_GAP"); payload["consumer_decision"] = decision
        with pytest.raises(RMRReconciliationBridgeError, match="RMR_EVIDENCE_NOT_BRIDGEABLE"):
            bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)


def test_operation_allowlist_and_controller_binding():
    payload = envelope(); payload["operation"] = "mutate_memory"
    with pytest.raises(RMRReconciliationBridgeError, match="UNSUPPORTED_OPERATION"):
        bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)
    with pytest.raises(RMRReconciliationBridgeError, match="INVALID_SOURCE_CUT_ID"):
        bridge_rmr_evidence(envelope(), source_cut_id="cut-bad", subject_id=SUBJECT)
    with pytest.raises(RMRReconciliationBridgeError, match="INVALID_SUBJECT_ID"):
        bridge_rmr_evidence(envelope(), source_cut_id=CUT, subject_id="")


def test_artifact_identity_is_deterministic_and_raw_evidence_not_projected():
    payload = envelope()
    a = bridge_rmr_evidence(payload, source_cut_id=CUT, subject_id=SUBJECT)
    b = bridge_rmr_evidence(copy.deepcopy(payload), source_cut_id=CUT, subject_id=SUBJECT)
    assert a["artifact_sha256"] == b["artifact_sha256"]
    assert a["artifact_id"] == "rmr-evidence-" + a["artifact_sha256"]
    assert "evidence" not in a["claim_value"]


def test_record_validates_against_existing_schema_when_jsonschema_available():
    jsonschema = pytest.importorskip("jsonschema")
    from pathlib import Path
    schema = json.loads((Path(__file__).resolve().parents[1] / "control_center/contracts/reconciliation-record.v1.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(bridge_rmr_evidence(envelope(), source_cut_id=CUT, subject_id=SUBJECT))
