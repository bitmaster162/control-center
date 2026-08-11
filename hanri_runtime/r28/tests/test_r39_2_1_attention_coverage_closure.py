from __future__ import annotations

from hanri.producer_adapters_coverage import (
    adapt_artifact,
    normalize_operator_contract,
    summarize_skips,
)


def test_canonical_operator_feedback_is_schema_bound_even_when_actor_is_hanri():
    raw = {
        "task_id": "T1",
        "step_id": "S1",
        "event_type": "OPERATOR_FEEDBACK",
        "actor": "HANRI",
        "can_trade": False,
        "status": "PASS",
        "human_summary": "operator reviewed the candidate",
    }
    normalized = normalize_operator_contract(adapter_type="OPERATOR_EVENT_ARTIFACT", data=raw)
    assert normalized["operator_event"] is True
    assert normalized["subject_id"] == "ROBERT"
    assert "EVENT_SCHEMA:OPERATOR_FEEDBACK" in normalized["evidence_refs"]

    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="R36_OPERATOR_EVENT_INBOX:feedback.json",
        source_sha256="a" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data=raw,
    )
    assert out["disposition"] == "EMITTED_COVERAGE"
    assert out["envelope"]["source_type"] == "AUDIT_COVERAGE"
    assert out["envelope"]["payload"]["domain"] == "OPERATOR"
    assert out["envelope"]["subject_id"] == "ROBERT"
    assert out["operator_contract"]["schema_bound"] is True


def test_operator_feedback_does_not_create_false_material_finding():
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="operator:healthy-feedback",
        source_sha256="b" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={
            "event_type": "OPERATOR_FEEDBACK",
            "actor": "HANRI",
            "status": "PASS",
            "summary": "operator feedback captured",
        },
    )
    assert out["disposition"] == "EMITTED_COVERAGE"
    assert out["envelope"]["source_type"] == "AUDIT_COVERAGE"


def test_operator_feedback_with_real_friction_remains_material():
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="operator:friction",
        source_sha256="c" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={
            "event_type": "OPERATOR_FEEDBACK",
            "actor": "HANRI",
            "signal": "MANUAL_REPEAT",
            "repeated_count": 3,
            "summary": "operator repeated the same correction",
        },
    )
    assert out["disposition"] == "EMITTED_MATERIAL"
    assert out["envelope"]["source_type"] == "OPERATOR_EVENT"
    assert out["envelope"]["payload"]["signal"] == "MANUAL_REPEAT"


def test_non_operator_event_is_still_not_reclassified():
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="event:tool-result",
        source_sha256="d" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"event_type": "TOOL_RESULT", "actor": "HANRI", "status": "PASS", "summary": "tool result"},
    )
    assert out["disposition"] == "SKIPPED_NOT_OPERATOR_EVENT"
    assert out["envelope"] is None


def test_skip_summary_explains_reason_and_source_counts():
    skipped = [
        {"source_id": "R36_OPERATOR_EVENT_INBOX:a.json", "reason": "SOURCE_TOO_OLD"},
        {"source_id": "R36_OPERATOR_EVENT_INBOX:b.json", "reason": "SOURCE_TOO_OLD"},
        {"source_id": "R36_AGENT_RETURN_INTAKE:c.json", "reason": "SOURCE_NOT_JSON"},
        {"source_id": "R23_RETURN_SYNC_STATE", "reason": "SOURCE_PATH_MISSING"},
    ]
    out = summarize_skips(skipped)
    assert out["scan_skip_count"] == 4
    assert out["scan_skip_reason_counts"] == {
        "SOURCE_NOT_JSON": 1,
        "SOURCE_PATH_MISSING": 1,
        "SOURCE_TOO_OLD": 2,
    }
    assert out["scan_skip_source_counts"] == {
        "R23_RETURN_SYNC_STATE": 1,
        "R36_AGENT_RETURN_INTAKE": 1,
        "R36_OPERATOR_EVENT_INBOX": 2,
    }


def test_r39_2_1_preserves_zero_effect_boundary():
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="operator:boundary",
        source_sha256="e" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"event_type": "OPERATOR_FEEDBACK", "actor": "HANRI", "status": "PASS", "summary": "ok"},
    )
    assert out["envelope"] is not None
    # Adapter results contain no execution directive; execution remains downstream of Effect Gateway.
    assert "execute" not in out
    assert "provider_call" not in out
