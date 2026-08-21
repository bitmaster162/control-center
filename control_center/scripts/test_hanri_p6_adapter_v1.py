from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from control_center.scripts.hanri_p6_adapter_v1 import (
    adapt_approval_item,
    adapt_attention,
    adapt_effect_decision,
    adapt_freshness_surface,
)
from control_center.scripts.reconciliation_v1 import resolve

CUT = "cut-" + hashlib.sha256(b"p14-stack").hexdigest()


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(subject: str, artifact: str = "canon", value: str = "ACTIVE", **kw):
    row = {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": CUT,
        "subject_id": subject,
        "artifact_id": artifact,
        "artifact_sha256": h(artifact),
        "source_class": "CANONICAL_ACTIVE_STATE",
        "authority_class": "NONE",
        "observed_at": "2026-08-15T16:00:00Z",
        "freshness": "FRESH",
        "logical_version": None,
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": value,
        "claim_status": "PASS",
        "current_observation": False,
        "evidence_debt": False,
        "transport_status": "NONE",
        "semantic_status": "UNREVIEWED",
        "apply_status": "APPLIED",
        "owner": "CONTROL_CENTER",
        "do_not_touch": False,
        "requested_action": None,
        "human_gate_required": False,
        "action_evidence_fresh": True,
        "effect_authorized": False,
        "execution_authorized": False,
    }
    row.update(kw)
    return row


def accepted_decision(subject: str):
    return {
        **canonical(subject, "decision", "APPROVED"),
        "source_class": "CONTROLLER_ADJUDICATION",
        "authority_class": "DETERMINISTIC_CONTROLLER",
        "apply_status": "NOT_APPLIED",
        "semantic_status": "ACCEPTED",
    }


def assert_adapter_ceiling(output):
    inv = output["invariants"]
    assert inv == {
        "hanri_semantic_authority": False,
        "hanri_current_truth_authority": False,
        "hanri_apply_authority": False,
        "hanri_execution_authority": False,
        "can_trade": False,
        "capital_permission": "DENY",
    }
    for record in output["records"]:
        assert record["effect_authorized"] is False
        assert record["execution_authorized"] is False
        assert record["semantic_status"] == "UNREVIEWED"
        assert record["apply_status"] == "NOT_APPLIED"
        assert record["source_class"] not in {
            "HUMAN_DECISION",
            "CONTROLLER_ADJUDICATION",
            "PROJECT_OWNER_DECISION",
        }
    for candidate in output["effect_gate_candidates"]:
        assert candidate["authority_granted"] is False
        assert candidate["effect_authorized"] is False
        assert candidate["execution_authorized"] is False
        assert candidate["auto_execute"] is False


def test_operator_event_stays_factual_observation_even_if_payload_claims_acceptance():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-OP",
        "source_type": "OPERATOR_EVENT",
        "observed_at": "2026-08-15T16:01:00Z",
        "subject_id": "project:cc",
        "evidence_refs": ["event://operator/1"],
        "payload": {
            "claim_status": "PASS",
            "claim_value": "clicked",
            "semantic_status": "ACCEPTED",
            "effect_authorized": True,
        },
    })
    assert out["terminal"] == "ADAPTER_PASS"
    assert out["records"][0]["source_class"] == "AUDIT"
    assert out["records"][0]["authority_class"] == "FACTUAL_OBSERVATION"
    assert_adapter_ceiling(out)


def test_agent_return_without_return_plane_binding_is_transport_observation():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-R1",
        "source_type": "AGENT_RETURN",
        "observed_at": "2026-08-15T16:02:00Z",
        "subject_id": "work:x",
        "evidence_refs": ["agent://return/x"],
        "payload": {"claim_value": "returned"},
    })
    assert out["records"][0]["source_class"] == "TRANSPORT_OBSERVATION"
    assert out["records"][0]["transport_status"] == "REPORTED"
    assert_adapter_ceiling(out)


def test_agent_return_with_exact_return_plane_binding_is_verified_return():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-R2",
        "source_type": "AGENT_RETURN",
        "observed_at": "2026-08-15T16:03:00Z",
        "subject_id": "work:x",
        "evidence_refs": [{"locator": "broker://delivery/d1", "sha256": "a"*64}],
        "payload": {
            "claim_value": "returned",
            "return_plane_binding": {
                "delivery_id": "d1",
                "artifact_sha256": "a"*64,
            },
        },
    })
    assert out["records"][0]["source_class"] == "VERIFIED_RETURN"
    assert out["records"][0]["transport_status"] == "PHYSICALLY_ACCEPTED"
    assert_adapter_ceiling(out)


def test_agent_return_invalid_binding_does_not_upgrade():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-R3",
        "source_type": "AGENT_RETURN",
        "observed_at": "2026-08-15T16:04:00Z",
        "subject_id": "work:x",
        "evidence_refs": ["agent://return/x"],
        "payload": {
            "return_plane_binding": {"delivery_id": "d1", "artifact_sha256": "bad"}
        },
    })
    assert out["records"][0]["source_class"] == "TRANSPORT_OBSERVATION"


def test_missing_subject_fails_closed():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-X",
        "source_type": "OBSERVATION",
        "observed_at": "2026-08-15T16:05:00Z",
        "evidence_refs": ["evidence://x"],
        "payload": {},
    })
    assert out["terminal"] == "ADAPTER_REVISE_SUBJECT_UNBOUND"
    assert out["records"] == []


def test_missing_evidence_fails_closed():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-X",
        "source_type": "OBSERVATION",
        "observed_at": "2026-08-15T16:05:00Z",
        "subject_id": "project:x",
        "evidence_refs": [],
        "payload": {},
    })
    assert out["terminal"] == "ADAPTER_REVISE_EVIDENCE_UNBOUND"


def test_evidence_locator_hash_conflict_holds():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-X",
        "source_type": "OBSERVATION",
        "observed_at": "2026-08-15T16:05:00Z",
        "subject_id": "project:x",
        "evidence_refs": [
            {"locator": "provider://x", "sha256": "a"*64},
            {"locator": "provider://x", "sha256": "b"*64},
        ],
        "payload": {},
    })
    assert out["terminal"] == "ADAPTER_HOLD_IDENTITY_CONFLICT"


def test_current_freshness_requires_current_proof():
    fresh = adapt_freshness_surface(CUT, {
        "id": "surface-1", "freshness": "CURRENT", "current_proof": True,
        "operational_status": "READY",
    }, "2026-08-15T16:06:00Z")
    unknown = adapt_freshness_surface(CUT, {
        "id": "surface-2", "freshness": "CURRENT", "current_proof": False,
        "operational_status": "READY",
    }, "2026-08-15T16:06:00Z")
    assert fresh["records"][0]["freshness"] == "FRESH"
    assert unknown["records"][0]["freshness"] == "UNKNOWN"


def test_do_not_touch_maps_to_owner_boundary_in_p6():
    out = adapt_freshness_surface(CUT, {
        "id": "codex-05",
        "owner": "TRADINGOS_OWNER",
        "freshness": "CURRENT",
        "current_proof": True,
        "operational_status": "DO_NOT_TOUCH",
    }, "2026-08-15T16:07:00Z")
    result = resolve([
        canonical("surface:codex-05", "canon-c05", owner="TRADINGOS_OWNER", do_not_touch=True),
        *out["records"],
    ])
    assert result["route"] == "OWNER_ONLY"
    assert_adapter_ceiling(out)


def _queue(queue_id: str, action_hash: str, status: str = "PENDING_APPROVAL"):
    return {
        "queue_id": queue_id,
        "status": status,
        "action_hash": action_hash,
        "operation": "APPLY",
        "effect_class": "CANONICAL_STATE",
        "target": "ContinuityOS",
        "approval_required": True,
        "approval_command": "APPROVE_EFFECT:" + action_hash,
        "expires_at": "2026-08-16T00:00:00Z",
    }


def test_approval_queue_alone_never_creates_human_gate_or_authority():
    out = adapt_approval_item(
        CUT, _queue("AQ-1", "1"*64), "2026-08-15T16:08:00Z",
        "effect:continuityos", evidence_fresh=True,
    )
    result = resolve([canonical("effect:continuityos"), *out["records"]])
    assert result["semantic_status"] == "UNREVIEWED"
    assert result["route"] == "CONTROL_CENTER"
    assert_adapter_ceiling(out)


def test_fresh_queue_plus_separate_accepted_cc_decision_becomes_human_gate():
    out = adapt_approval_item(
        CUT, _queue("AQ-2", "2"*64), "2026-08-15T16:09:00Z",
        "effect:continuityos", evidence_fresh=True,
    )
    result = resolve([
        canonical("effect:continuityos"),
        accepted_decision("effect:continuityos"),
        *out["records"],
    ])
    assert (result["truth_status"], result["semantic_status"], result["route"]) == (
        "CURRENT", "ACCEPTED", "HUMAN_GATE"
    )
    assert result["authority_granted"] is False
    assert result["auto_execute"] is False
    assert_adapter_ceiling(out)


def test_stale_queue_blocks_even_with_accepted_cc_decision():
    out = adapt_approval_item(
        CUT, _queue("AQ-3", "3"*64), "2026-08-15T16:10:00Z",
        "effect:continuityos", evidence_fresh=False,
    )
    result = resolve([
        canonical("effect:continuityos"),
        accepted_decision("effect:continuityos"),
        *out["records"],
    ])
    assert (result["truth_status"], result["semantic_status"], result["route"]) == (
        "CURRENT", "ACCEPTED", "BLOCKED"
    )


def test_approved_not_executed_queue_status_still_does_not_grant_authority():
    out = adapt_approval_item(
        CUT, _queue("AQ-4", "4"*64, "APPROVED_NOT_EXECUTED"),
        "2026-08-15T16:11:00Z", "effect:x", evidence_fresh=True,
    )
    assert out["effect_gate_candidates"][0]["queue_status"] == "APPROVED_NOT_EXECUTED"
    assert_adapter_ceiling(out)


def test_invalid_action_hash_fails_closed():
    out = adapt_approval_item(
        CUT, _queue("AQ-X", "bad"), "2026-08-15T16:11:00Z",
        "effect:x", evidence_fresh=True,
    )
    assert out["terminal"] == "ADAPTER_HOLD_INVALID_ACTION_HASH"


def test_effect_human_approval_is_only_audit_evidence():
    out = adapt_effect_decision(CUT, {
        "action_hash": "5"*64,
        "policy_verdict": "HUMAN_APPROVAL",
        "execution_authorized": False,
        "action": {"operation": "MERGE", "target": "PR30"},
    }, "2026-08-15T16:12:00Z", "effect:pr30")
    result = resolve([canonical("effect:pr30"), *out["records"]])
    assert result["semantic_status"] == "UNREVIEWED"
    assert result["route"] == "CONTROL_CENTER"
    assert_adapter_ceiling(out)


def test_effect_allow_does_not_become_execution_authority():
    out = adapt_effect_decision(CUT, {
        "action_hash": "6"*64,
        "policy_verdict": "ALLOW",
        "execution_authorized": False,
        "action": {"operation": "READ_ONLY_CHECK", "target": "PR30"},
    }, "2026-08-15T16:13:00Z", "effect:pr30")
    assert out["records"][0]["claim_status"] == "PASS"
    assert_adapter_ceiling(out)


def test_adversarial_effect_execution_authority_is_rejected():
    out = adapt_effect_decision(CUT, {
        "action_hash": "7"*64,
        "policy_verdict": "ALLOW",
        "execution_authorized": True,
        "action": {"operation": "DEPLOY"},
    }, "2026-08-15T16:14:00Z", "effect:x")
    assert out["terminal"] == "ADAPTER_HOLD_AUTHORITY_ESCALATION"
    assert out["records"] == []


def test_unsupported_attention_source_fails_closed():
    out = adapt_attention(CUT, {
        "envelope_id": "ATT-BAD",
        "source_type": "MAGIC_AUTHORITY",
        "observed_at": "2026-08-15T16:15:00Z",
        "subject_id": "project:x",
        "evidence_refs": ["evidence://x"],
        "payload": {},
    })
    assert out["terminal"] == "ADAPTER_HOLD_UNSUPPORTED_STATUS"


def test_adapter_output_schema_validates():
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = Path(__file__).resolve().parents[1] / "contracts" / "hanri-p6-adapter-output.v1.schema.json"
    schema = json.loads(schema_path.read_text())
    out = adapt_approval_item(
        CUT, _queue("AQ-SCHEMA", "8"*64), "2026-08-15T16:16:00Z",
        "effect:x", evidence_fresh=True,
    )
    jsonschema.Draft202012Validator(schema).validate(out)


def test_mapping_keeps_all_forbidden_promotions():
    mapping_path = Path(__file__).resolve().parents[1] / "contracts" / "hanri-to-p6-mapping.v1.json"
    mapping = json.loads(mapping_path.read_text())
    forbidden = "\n".join(mapping["forbidden_promotions"])
    assert "HUMAN_DECISION" in forbidden
    assert "CONTROLLER_ADJUDICATION" in forbidden
    assert "effect_authorized=true" in forbidden
    assert "execution_authorized=true" in forbidden


def test_adapter_is_deterministic_for_same_input():
    env = {
        "envelope_id": "ATT-DET",
        "source_type": "OBSERVATION",
        "observed_at": "2026-08-15T16:17:00Z",
        "subject_id": "project:x",
        "evidence_refs": ["evidence://x"],
        "payload": {"claim_status": "PASS", "claim_value": {"b": 2, "a": 1}},
    }
    assert adapt_attention(CUT, env) == adapt_attention(CUT, env)
