from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from control_center.scripts.legacy_p6_compat_v1 import adapt_legacy_work_order
from control_center.scripts.operator_projection_v2 import compile_projection, compute_source_cut
from control_center.scripts.reconciliation_v1 import resolve
from control_center.scripts.build_operator_projection_v2 import build_shadow_projection


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def authority():
    return {
        "available": True,
        "generation": "R777",
        "pointer_sha256": h("pointer"),
        "accepted_manifest_sha256": h("manifest"),
        "current_state_sha256": h("state"),
        "role_index_sha256": h("role-index"),
        "role_views_sha256": h("role-views"),
        "provider_readback": "all_exact",
    }


def cursor():
    return {
        "available": True,
        "generation": "R59",
        "cursor_sha256": h("cursor"),
        "semantic_authority": False,
        "reason": None,
    }


def source(required_for=None):
    return {
        "schema": "control_plane.projection_source_envelope.v2",
        "source_id": "github:p18",
        "source_class": "PROVIDER_OBSERVATION",
        "authority_scope": "FACTUAL_ONLY",
        "locator": "github://p18",
        "identity": {"ref": "p18"},
        "observed_at": "2026-08-16T00:40:00Z",
        "fetched_at": "2026-08-16T00:40:01Z",
        "freshness": {"verdict": "FRESH", "policy": "per-compile", "expires_at": None},
        "payload_sha256": h("provider"),
        "required_for": list(required_for or []),
    }


def bind(record, cut):
    row = dict(record)
    row["source_cut_id"] = cut
    return row


def base(subject: str, artifact: str, source_class: str, **kw):
    row = {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": "AUTO_SOURCE_CUT",
        "subject_id": subject,
        "artifact_id": artifact,
        "artifact_sha256": h(artifact),
        "source_class": source_class,
        "authority_class": "NONE",
        "observed_at": "2026-08-16T00:41:00Z",
        "freshness": "FRESH",
        "logical_version": None,
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": "READY",
        "claim_status": "PASS",
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


def canonical(subject):
    return base(subject, "canon:" + subject, "CANONICAL_ACTIVE_STATE", apply_status="APPLIED")


def accepted(subject):
    return base(
        subject, "decision:" + subject, "CONTROLLER_ADJUDICATION",
        authority_class="DETERMINISTIC_CONTROLLER", semantic_status="ACCEPTED",
    )


def gate(subject):
    return base(
        subject, "gate:" + subject, "AUDIT",
        authority_class="FACTUAL_OBSERVATION", requested_action="APPLY",
        human_gate_required=True, action_evidence_fresh=True,
    )


def test_pending_execution_compat_maps_to_blocked():
    row = adapt_legacy_work_order({
        "work_order": "WO-PENDING", "reported_state": "PENDING_EXECUTION",
        "apply_status": "NOT_APPLIED", "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("pending")
    result = resolve([row])
    assert result["route"] == "BLOCKED"
    assert "STALE_OR_MISSING_REQUIRED_EVIDENCE" in result["reason_codes"]


def test_gated_reserved_compat_maps_to_blocked():
    row = adapt_legacy_work_order({
        "work_order": "WO-GATED", "reported_state": "GATED_RESERVED",
        "apply_status": "NOT_APPLIED", "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("gated")
    assert resolve([row])["route"] == "BLOCKED"


def test_nonpending_legacy_record_remains_review_only():
    row = adapt_legacy_work_order({
        "work_order": "WO-REVIEW", "reported_state": "OUTCOME_PASS",
        "apply_status": "NOT_APPLIED", "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("review")
    assert resolve([row])["route"] == "CONTROL_CENTER"


def test_owner_boundary_must_be_explicit_not_project_substring():
    row = adapt_legacy_work_order({
        "work_order": "WO-NAME", "project": "NOTTRADINGOS-DEMO",
        "reported_state": "OUTCOME_PASS", "apply_status": "NOT_APPLIED",
        "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("name")
    assert resolve([row])["route"] == "CONTROL_CENTER"
    with pytest.raises(ValueError, match="LEGACY_EXPLICIT_OWNER_BOUNDARY_REQUIRED"):
        adapt_legacy_work_order({"work_order": "WO-MISSING", "project": "TradingOS"}, observed_at="2026-08-16T00:42:00Z")


def test_applied_legacy_defaults_to_explicit_readback_required():
    row = adapt_legacy_work_order({
        "work_order": "WO-APPLIED", "reported_state": "OUTCOME_PASS",
        "apply_status": "APPLIED", "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("applied")
    result = resolve([row])
    assert result["readback_required"] is True
    assert result["readback_status"] == "REQUIRED"
    assert result["route"] == "CONTROL_CENTER"
    assert "POST_APPLY_READBACK_REQUIRED" in result["reason_codes"]


def test_verified_readback_closes_obligation_without_granting_effect():
    row = adapt_legacy_work_order({
        "work_order": "WO-VERIFIED", "reported_state": "OUTCOME_PASS",
        "apply_status": "APPLIED", "readback_status": "VERIFIED",
        "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("verified")
    result = resolve([row])
    assert result["readback_required"] is False
    assert result["readback_status"] == "VERIFIED"
    assert result["authority_granted"] is False
    assert result["auto_execute"] is False


def test_noncanonical_applied_record_without_readback_status_fails_closed():
    row = base("x", "audit", "AUDIT", apply_status="APPLIED")
    row["source_cut_id"] = "cut-" + h("missing-readback")
    with pytest.raises(ValueError, match="APPLIED_RECORD_READBACK_STATUS_REQUIRED"):
        resolve([row])


def test_projection_exposes_readback_required_view():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    legacy = adapt_legacy_work_order({
        "work_order": "WO-RB", "reported_state": "OUTCOME_PASS",
        "apply_status": "APPLIED", "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    result = resolve([bind(legacy, cut)])
    projection = compile_projection(
        authority_anchor=authority(), return_plane_cursor=cursor(), sources=sources,
        reconciliations=[result], generated_at="2026-08-16T07:43:00+07:00",
    )
    assert projection["views"]["readback_required"]["items"] == ["work-order:WO-RB"]
    assert projection["views"]["overview"]["readback_required"] == 1
    assert projection["views"]["results"]["items"][0]["readback_status"] == "REQUIRED"


def test_four_human_gates_preserve_all_and_top3_plus_overflow():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    results = []
    for i in range(4):
        subject = f"effect:{i}"
        results.append(resolve([bind(canonical(subject), cut), bind(accepted(subject), cut), bind(gate(subject), cut)]))
    projection = compile_projection(
        authority_anchor=authority(), return_plane_cursor=cursor(), sources=sources,
        reconciliations=results, generated_at="2026-08-16T07:43:00+07:00",
    )
    human = projection["views"]["human_now"]
    assert human["items"] == ["effect:0", "effect:1", "effect:2", "effect:3"]
    assert human["top_items"] == ["effect:0", "effect:1", "effect:2"]
    assert human["overflow_count"] == 1
    assert human["overflow_items"] == ["effect:3"]


def test_builder_accepts_legacy_work_orders_and_routes_pending_blocked(tmp_path):
    authority_snapshot = {
        "schema": "control_center.provider_snapshot.v1",
        "snapshot_kind": "NON_AUTHORITY_PROVIDER_READBACK",
        "canonical_roots": {
            "generation": "R64", "status": "ACTIVE", "pointer_sha256": h("p"),
            "manifest_sha256": h("m"), "current_state_sha256": h("s"),
            "role_index_sha256": h("ri"), "role_views_sha256": h("rv"),
            "provider_readback": "all_exact", "r63_is_current": False,
        },
    }
    live = {"schema": "control_return_broker.v1.live_index", "generation": "R59", "updated_at_utc": "2026-08-16T00:40:00Z", "slots": {}, "entry_count": 0}
    provider = {
        "source_id": "github:p18", "locator": "github://p18", "identity": {"ref": "p18"},
        "observed_at": "2026-08-16T00:40:00Z", "freshness": {"verdict": "FRESH", "policy": "per-compile", "expires_at": None},
        "payload": {"head": "x"}, "required_for": [],
    }
    subjects = {
        "subjects": [], "legacy_observed_at": "2026-08-16T00:42:00Z",
        "legacy_work_orders": [{"work_order": "WO-PENDING", "reported_state": "PENDING_EXECUTION", "apply_status": "NOT_APPLIED", "do_not_touch": False}],
    }
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value) + "\n")
        return path
    projection = build_shadow_projection(
        authority_snapshot_path=write("a.json", authority_snapshot),
        return_live_index_path=write("l.json", live),
        provider_observation_paths=[write("p.json", provider)],
        subject_records_path=write("s.json", subjects),
        fetched_at="2026-08-16T00:43:00Z", generated_at="2026-08-16T07:43:01+07:00",
    )
    assert projection["views"]["blocked"]["items"] == ["work-order:WO-PENDING"]


def test_result_schema_accepts_explicit_readback_fields():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((Path(__file__).resolve().parents[1] / "contracts" / "reconciliation-result.v1.schema.json").read_text())
    row = adapt_legacy_work_order({
        "work_order": "WO-SCHEMA", "reported_state": "OUTCOME_PASS",
        "apply_status": "APPLIED", "do_not_touch": False,
    }, observed_at="2026-08-16T00:42:00Z")
    row["source_cut_id"] = "cut-" + h("schema")
    jsonschema.Draft202012Validator(schema).validate(resolve([row]))
