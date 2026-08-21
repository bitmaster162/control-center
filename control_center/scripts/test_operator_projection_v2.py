from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from control_center.scripts.hanri_p6_adapter_v1 import adapt_approval_item
from control_center.scripts.operator_projection_v2 import (
    compile_projection,
    compute_source_cut,
)
from control_center.scripts.reconciliation_v1 import resolve


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def authority():
    return {
        "available": True,
        "generation": "R64",
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


def source(source_id="github:cc", verdict="FRESH", required_for=None, payload=None):
    return {
        "schema": "control_plane.projection_source_envelope.v2",
        "source_id": source_id,
        "source_class": "PROVIDER_OBSERVATION",
        "authority_scope": "FACTUAL_ONLY",
        "locator": "github://example/" + source_id,
        "identity": {"ref": source_id},
        "observed_at": "2026-08-15T16:30:00Z",
        "fetched_at": "2026-08-15T16:30:01Z",
        "freshness": {
            "verdict": verdict,
            "policy": "fresh-per-compile",
            "expires_at": None,
        },
        "payload_sha256": h(payload or source_id),
        "required_for": list(required_for or []),
    }


def p6_record(cut, subject, artifact, source_class, **kw):
    row = {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": cut,
        "subject_id": subject,
        "artifact_id": artifact,
        "artifact_sha256": h(artifact),
        "source_class": source_class,
        "authority_class": "NONE",
        "observed_at": "2026-08-15T16:31:00Z",
        "freshness": "FRESH",
        "logical_version": None,
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": "ACTIVE",
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


def accepted_decision(cut, subject):
    return p6_record(
        cut, subject, "decision", "CONTROLLER_ADJUDICATION",
        authority_class="DETERMINISTIC_CONTROLLER",
        semantic_status="ACCEPTED",
        claim_value="APPROVED",
    )


def canonical(cut, subject, **kw):
    values = {"claim_value": "READY"}
    values.update(kw)
    return p6_record(
        cut, subject, "canon:" + subject, "CANONICAL_ACTIVE_STATE",
        **values,
    )


def compile_with(sources, results):
    return compile_projection(
        authority_anchor=authority(),
        return_plane_cursor=cursor(),
        sources=sources,
        reconciliations=results,
        generated_at="2026-08-15T23:49:00+07:00",
    )


def test_source_cut_is_deterministic_and_order_independent():
    a = source("a")
    b = source("b")
    one = compute_source_cut(authority(), cursor(), [a, b])
    two = compute_source_cut(authority(), cursor(), [b, a])
    assert one["source_cut_id"] == two["source_cut_id"]
    assert one["source_manifest_sha256"] == two["source_manifest_sha256"]


def test_source_cut_changes_when_provider_payload_changes():
    one = compute_source_cut(authority(), cursor(), [source("a", payload="one")])
    two = compute_source_cut(authority(), cursor(), [source("a", payload="two")])
    assert one["source_cut_id"] != two["source_cut_id"]


def test_ready_projection_one_source_cut_all_views():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    result = resolve([canonical(cut, "project:x")])
    projection = compile_with(sources, [result])
    assert projection["terminal"] == "PROJECTION_READY"
    assert projection["projection_kind"] == "NON_AUTHORITY_PROJECTION"
    assert {view["source_cut_id"] for view in projection["views"].values()} == {cut}


def test_projection_id_is_deterministic():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    result = resolve([canonical(cut, "project:x")])
    assert compile_with(sources, [result])["projection_id"] == compile_with(sources, [result])["projection_id"]


@pytest.mark.parametrize("verdict", ["STALE", "UNKNOWN", "UNAVAILABLE"])
def test_nonfresh_observation_degrades_projection(verdict):
    sources = [source(verdict=verdict)]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    result = resolve([canonical(cut, "project:x")])
    projection = compile_with(sources, [result])
    assert projection["terminal"] == "PROJECTION_DEGRADED"
    assert "NONFRESH_OBSERVATION_PRESENT" in projection["diagnostics"]["reason_codes"]


def test_identity_conflict_holds_projection():
    sources = [source(verdict="IDENTITY_CONFLICT")]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    result = resolve([canonical(cut, "project:x")])
    projection = compile_with(sources, [result])
    assert projection["terminal"] == "PROJECTION_HOLD"
    assert "SOURCE_IDENTITY_CONFLICT" in projection["diagnostics"]["reason_codes"]


def test_mixed_p6_source_cut_holds_and_does_not_render_foreign_result():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    foreign_cut = "cut-" + h("foreign")
    valid = resolve([canonical(cut, "project:valid")])
    foreign = resolve([canonical(foreign_cut, "project:foreign")])
    projection = compile_with(sources, [valid, foreign])
    assert projection["terminal"] == "PROJECTION_HOLD"
    assert projection["views"]["overview"]["subjects"] == 1
    assert projection["views"]["results"]["items"][0]["subject_id"] == "project:valid"
    assert foreign_cut in projection["diagnostics"]["mixed_result_cuts"]


def test_unavailable_authority_produces_unavailable_projection_not_exception():
    bad = {"available": False, "reason": "provider unavailable"}
    projection = compile_projection(
        authority_anchor=bad,
        return_plane_cursor=cursor(),
        sources=[],
        reconciliations=[],
        generated_at="2026-08-15T23:49:00+07:00",
    )
    assert projection["terminal"] == "PROJECTION_UNAVAILABLE"
    assert projection["source_cut"] is None
    assert projection["views"] == {}


def test_nonexact_authority_readback_is_unavailable():
    bad = authority()
    bad["provider_readback"] = "partial"
    projection = compile_projection(
        authority_anchor=bad,
        return_plane_cursor=cursor(),
        sources=[],
        reconciliations=[],
        generated_at="2026-08-15T23:49:00+07:00",
    )
    assert projection["terminal"] == "PROJECTION_UNAVAILABLE"


def test_missing_return_cursor_is_unavailable():
    bad = {"available": False, "generation": None, "cursor_sha256": None, "semantic_authority": False, "reason": "missing"}
    projection = compile_projection(
        authority_anchor=authority(),
        return_plane_cursor=bad,
        sources=[],
        reconciliations=[],
        generated_at="2026-08-15T23:49:00+07:00",
    )
    assert projection["terminal"] == "PROJECTION_UNAVAILABLE"


def test_conflict_route_appears_in_conflict_view():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    result = resolve([
        canonical(cut, "project:x", claim_value="ACTIVE"),
        p6_record(
            cut, "project:x", "provider", "PROVIDER_READBACK",
            authority_class="FACTUAL_OBSERVATION",
            claim_value="BROKEN",
            claim_status="REVISE",
            current_observation=True,
        ),
    ])
    projection = compile_with(sources, [result])
    assert projection["views"]["conflicts"]["items"] == ["project:x"]


def test_owner_only_route_appears_in_owner_view():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    result = resolve([canonical(cut, "project:t", do_not_touch=True)])
    projection = compile_with(sources, [result])
    assert projection["views"]["owner_only"]["items"] == ["project:t"]


def _queue():
    return {
        "queue_id": "AQ-P15",
        "status": "PENDING_APPROVAL",
        "action_hash": "a" * 64,
        "operation": "APPLY",
        "effect_class": "CANONICAL_STATE",
        "target": "ContinuityOS",
        "approval_required": True,
        "approval_command": "APPROVE_EFFECT:" + "a"*64,
        "expires_at": "2026-08-16T00:00:00Z",
    }


def test_full_p10_p6_p5_fresh_gate_enters_human_now():
    sources = [source("provider:effect", "FRESH", required_for=["subject:effect:continuityos"])]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    adapted = adapt_approval_item(
        cut, _queue(), "2026-08-15T16:32:00Z",
        "effect:continuityos", evidence_fresh=True,
    )
    result = resolve([
        canonical(cut, "effect:continuityos"),
        accepted_decision(cut, "effect:continuityos"),
        *adapted["records"],
    ])
    assert result["route"] == "HUMAN_GATE"
    projection = compile_with(sources, [result])
    assert projection["views"]["human_now"]["items"] == ["effect:continuityos"]
    assert projection["views"]["blocked"]["items"] == []


def test_p5_suppresses_human_gate_if_projection_required_source_is_stale():
    # Deliberately adversarial mismatch: P6 result claims ripe, but P5 source evidence is stale.
    sources = [source("provider:effect", "STALE", required_for=["subject:effect:continuityos"])]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    adapted = adapt_approval_item(
        cut, _queue(), "2026-08-15T16:32:00Z",
        "effect:continuityos", evidence_fresh=True,
    )
    result = resolve([
        canonical(cut, "effect:continuityos"),
        accepted_decision(cut, "effect:continuityos"),
        *adapted["records"],
    ])
    assert result["route"] == "HUMAN_GATE"
    projection = compile_with(sources, [result])
    assert projection["terminal"] == "PROJECTION_DEGRADED"
    assert projection["views"]["human_now"]["items"] == []
    assert projection["views"]["blocked"]["items"] == ["effect:continuityos"]
    assert projection["views"]["results"]["items"][0]["route"] == "BLOCKED"


def test_p10_stale_gate_is_blocked_before_p5():
    sources = [source("provider:effect", "STALE", required_for=["subject:effect:continuityos"])]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    adapted = adapt_approval_item(
        cut, _queue(), "2026-08-15T16:32:00Z",
        "effect:continuityos", evidence_fresh=False,
    )
    result = resolve([
        canonical(cut, "effect:continuityos"),
        accepted_decision(cut, "effect:continuityos"),
        *adapted["records"],
    ])
    assert result["route"] == "BLOCKED"
    projection = compile_with(sources, [result])
    assert projection["views"]["blocked"]["items"] == ["effect:continuityos"]


def test_queue_alone_never_appears_human_now():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    adapted = adapt_approval_item(
        cut, _queue(), "2026-08-15T16:32:00Z",
        "effect:continuityos", evidence_fresh=True,
    )
    result = resolve([canonical(cut, "effect:continuityos"), *adapted["records"]])
    projection = compile_with(sources, [result])
    assert projection["views"]["human_now"]["items"] == []
    assert result["semantic_status"] == "UNREVIEWED"


def test_projection_never_grants_effects():
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    projection = compile_with(sources, [resolve([canonical(cut, "project:x")])])
    assert projection["safety"] == {
        "can_trade": False,
        "capital_permission": "DENY",
        "deploy_permission": "DENY",
        "auto_dispatch": False,
        "auto_apply": False,
        "auto_execute": False,
        "self_application": False,
    }


def test_no_hardcoded_r64_required():
    alt = authority()
    alt["generation"] = "R999"
    sources = [source()]
    cut = compute_source_cut(alt, cursor(), sources)["source_cut_id"]
    result = resolve([canonical(cut, "project:x")])
    projection = compile_projection(
        authority_anchor=alt,
        return_plane_cursor=cursor(),
        sources=sources,
        reconciliations=[result],
        generated_at="2026-08-15T23:49:00+07:00",
    )
    assert projection["authority_anchor"]["generation"] == "R999"
    assert projection["terminal"] == "PROJECTION_READY"


def test_generated_at_must_be_timezone_aware():
    with pytest.raises(ValueError, match="TIME_MUST_BE_TIMEZONE_AWARE"):
        compile_projection(
            authority_anchor=authority(),
            return_plane_cursor=cursor(),
            sources=[],
            reconciliations=[],
            generated_at="2026-08-15T23:49:00",
        )


def test_source_envelope_schema_validates_fixture():
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = Path(__file__).resolve().parents[1] / "contracts" / "projection-source-envelope.v2.schema.json"
    schema = json.loads(schema_path.read_text())
    jsonschema.Draft202012Validator(schema).validate(source())


def test_projection_schema_validates_ready_projection():
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = Path(__file__).resolve().parents[1] / "contracts" / "operator-projection.v2.schema.json"
    schema = json.loads(schema_path.read_text())
    sources = [source()]
    cut = compute_source_cut(authority(), cursor(), sources)["source_cut_id"]
    projection = compile_with(sources, [resolve([canonical(cut, "project:x")])])
    jsonschema.Draft202012Validator(schema).validate(projection)


def test_projection_schema_validates_unavailable_projection():
    jsonschema = pytest.importorskip("jsonschema")
    schema_path = Path(__file__).resolve().parents[1] / "contracts" / "operator-projection.v2.schema.json"
    schema = json.loads(schema_path.read_text())
    projection = compile_projection(
        authority_anchor={"available": False, "reason": "missing"},
        return_plane_cursor={"available": False, "generation": None, "cursor_sha256": None, "semantic_authority": False, "reason": "missing"},
        sources=[],
        reconciliations=[],
        generated_at="2026-08-15T23:49:00+07:00",
    )
    jsonschema.Draft202012Validator(schema).validate(projection)
