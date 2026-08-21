from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from control_center.scripts.reconciliation_v1 import resolve

CUT = "cut-" + hashlib.sha256(b"p6-a-real-tests").hexdigest()


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def rec(subject: str, artifact: str, source_class: str, **kw):
    row = {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": CUT,
        "subject_id": subject,
        "artifact_id": artifact,
        "artifact_sha256": h(artifact),
        "source_class": source_class,
        "authority_class": "NONE",
        "observed_at": "2026-08-15T15:00:00Z",
        "freshness": "FRESH",
        "logical_version": None,
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": "OPEN",
        "claim_status": "UNKNOWN",
        "current_observation": False,
        "evidence_debt": False,
        "transport_status": "NONE",
        "semantic_status": "UNREVIEWED",
        "apply_status": "NOT_APPLIED",
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


def triple(result):
    return result["truth_status"], result["semantic_status"], result["route"]


def assert_no_authority(result):
    assert result["authority_granted"] is False
    assert result["auto_execute"] is False
    assert result["can_trade"] is False
    assert result["capital_permission"] == "DENY"
    assert not any(result["effects"].values())


def test_current_clean():
    result = resolve([rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS")])
    assert triple(result) == ("CURRENT", "UNREVIEWED", "CONTROL_CENTER")
    assert_no_authority(result)


def test_current_with_conditions():
    result = resolve([rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS", evidence_debt=True)])
    assert triple(result) == ("CURRENT_WITH_CONDITIONS", "UNREVIEWED", "CONTROL_CENTER")


def test_fresh_provider_contradiction_holds_without_authority():
    result = resolve([
        rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("p:x", "provider", "PROVIDER_READBACK", authority_class="FACTUAL_OBSERVATION",
            claim_value="BROKEN", claim_status="REVISE", current_observation=True),
    ])
    assert triple(result) == ("CONFLICT", "HOLD", "CONTROL_CENTER")
    assert result["contradiction_refs"] == ["provider"]
    assert_no_authority(result)


def test_verified_return_is_unreviewed():
    result = resolve([
        rec("w:x", "ret", "VERIFIED_RETURN", authority_class="TRANSPORT_ONLY",
            transport_status="PHYSICALLY_ACCEPTED")
    ])
    assert triple(result) == ("UNKNOWN", "UNREVIEWED", "CONTROL_CENTER")


def test_owner_only_survives_priority_and_candidate_action():
    result = resolve([
        rec("p:t", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS", do_not_touch=True),
        rec("p:t", "audit", "AUDIT", authority_class="FACTUAL_OBSERVATION",
            requested_action="MERGE", human_gate_required=True, action_evidence_fresh=True, do_not_touch=True),
    ])
    assert triple(result) == ("CURRENT", "UNREVIEWED", "OWNER_ONLY")


def test_human_gate_requires_external_accepted_semantic_and_fresh_action():
    result = resolve([
        rec("e:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="READY", claim_status="PASS"),
        rec("e:x", "decision", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            semantic_status="ACCEPTED"),
        rec("e:x", "gate", "AUDIT", authority_class="FACTUAL_OBSERVATION",
            requested_action="APPLY", human_gate_required=True, action_evidence_fresh=True, claim_status="PASS"),
    ])
    assert triple(result) == ("CURRENT", "ACCEPTED", "HUMAN_GATE")
    assert result["human_ripe"] is True
    assert_no_authority(result)


def test_stale_action_blocks_human_gate():
    result = resolve([
        rec("e:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="READY", claim_status="PASS"),
        rec("e:x", "decision", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            semantic_status="ACCEPTED"),
        rec("e:x", "gate", "AUDIT", authority_class="FACTUAL_OBSERVATION",
            freshness="STALE", requested_action="APPLY", human_gate_required=True, action_evidence_fresh=False),
    ])
    assert triple(result) == ("CURRENT", "ACCEPTED", "BLOCKED")


def test_identity_conflict_blocks():
    result = resolve([
        rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("p:x", "other", "AUDIT", freshness="IDENTITY_CONFLICT"),
    ])
    assert triple(result) == ("CONFLICT", "HOLD", "BLOCKED")


def test_canonical_supersession_is_terminal():
    result = resolve([
        rec("w:old", "canon", "CANONICAL_ACTIVE_STATE", claim_value="SUPERSEDED",
            claim_status="UNKNOWN", semantic_status="SUPERSEDED")
    ])
    assert triple(result) == ("SUPERSEDED", "SUPERSEDED", "NO_ACTION")


def test_accepted_successor_does_not_self_apply():
    result = resolve([
        rec("w:old", "canon-old", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("w:old", "successor", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            semantic_status="ACCEPTED", supersedes_id="canon-old"),
    ])
    assert result["truth_status"] == "CURRENT"
    assert "ACCEPTED_SUCCESSOR_NOT_YET_CANONICALLY_APPLIED" in result["reason_codes"]
    assert result["effects"]["state_apply"] is False


def test_newer_same_authority_semantic_decision_wins():
    result = resolve([
        rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("p:x", "old", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            observed_at="2026-08-15T14:00:00Z", semantic_status="HOLD"),
        rec("p:x", "new", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            observed_at="2026-08-15T15:00:00Z", semantic_status="ACCEPTED"),
    ])
    assert result["semantic_status"] == "ACCEPTED"
    assert "new" in result["selected_refs"]


def test_equal_authority_equal_time_semantic_conflict_fails_closed():
    result = resolve([
        rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("p:x", "a", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            observed_at="2026-08-15T15:00:00Z", semantic_status="ACCEPTED"),
        rec("p:x", "b", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            observed_at="2026-08-15T15:00:00Z", semantic_status="REJECTED"),
    ])
    assert triple(result) == ("CONFLICT", "HOLD", "CONTROL_CENTER")


def test_human_decision_outranks_newer_controller_decision():
    result = resolve([
        rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("p:x", "human", "HUMAN_DECISION", authority_class="HUMAN",
            observed_at="2026-08-15T14:00:00Z", semantic_status="HOLD"),
        rec("p:x", "controller", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            observed_at="2026-08-15T16:00:00Z", semantic_status="ACCEPTED"),
    ])
    assert result["semantic_status"] == "HOLD"
    assert "human" in result["selected_refs"]


def test_rejected_semantic_is_no_action():
    result = resolve([
        rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS"),
        rec("p:x", "decision", "CONTROLLER_ADJUDICATION", authority_class="DETERMINISTIC_CONTROLLER",
            semantic_status="REJECTED"),
    ])
    assert triple(result) == ("CURRENT", "REJECTED", "NO_ACTION")


@pytest.mark.parametrize("field,value,code", [
    ("source_cut_id", "cut-" + "a"*64, "MIXED_SOURCE_CUT"),
    ("subject_id", "different", "MULTIPLE_SUBJECTS"),
])
def test_mixed_envelope_fails(field, value, code):
    a = rec("p:x", "a", "AUDIT")
    b = rec("p:x", "b", "AUDIT")
    b[field] = value
    with pytest.raises(ValueError, match=code):
        resolve([a, b])


def test_input_effect_authority_is_rejected():
    row = rec("p:x", "a", "AUDIT")
    row["effect_authorized"] = True
    with pytest.raises(ValueError, match="INPUT_EFFECT_AUTHORITY_NOT_ALLOWED"):
        resolve([row])


def test_timezone_naive_observed_at_rejected():
    row = rec("p:x", "a", "AUDIT", observed_at="2026-08-15T15:00:00")
    with pytest.raises(ValueError, match="OBSERVED_AT_MUST_BE_TIMEZONE_AWARE"):
        resolve([row])


def test_result_id_is_deterministic():
    rows = [rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS")]
    assert resolve(rows)["result_id"] == resolve(rows)["result_id"]


def test_schemas_validate_reference_record_and_result():
    jsonschema = pytest.importorskip("jsonschema")
    base = Path(__file__).resolve().parents[1] / "contracts"
    record_schema = json.loads((base / "reconciliation-record.v1.schema.json").read_text())
    result_schema = json.loads((base / "reconciliation-result.v1.schema.json").read_text())
    row = rec("p:x", "canon", "CANONICAL_ACTIVE_STATE", claim_value="ACTIVE", claim_status="PASS")
    result = resolve([row])
    jsonschema.Draft202012Validator(record_schema).validate(row)
    jsonschema.Draft202012Validator(result_schema).validate(result)
