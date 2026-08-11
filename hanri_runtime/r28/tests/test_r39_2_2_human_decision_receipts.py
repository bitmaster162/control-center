from __future__ import annotations

import json
from pathlib import Path

from hanri.attention_fabric import run_attention_fabric
from hanri.producer_adapters_operator_receipts import (
    HUMAN_DECISION_SCHEMA,
    adapt_artifact,
    adapt_artifacts,
    normalize_human_decision_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
GOV_POLICY = json.loads((ROOT / "config" / "r39.attention-governor.json").read_text(encoding="utf-8"))
FABRIC_POLICY = json.loads((ROOT / "config" / "r39.1.attention-fabric.json").read_text(encoding="utf-8"))


def human_receipt(**overrides):
    row = {
        "schema": HUMAN_DECISION_SCHEMA,
        "generation": "R64",
        "decider": "Robert",
        "authorization_utterance": "D1,D2,D3,D4,D5 go",
        "decisions": [
            {"id": "D1", "verdict": "ACCEPT", "scope": "bounded decision one"},
            {"id": "D2", "verdict": "ACCEPT", "scope": "bounded decision two"},
        ],
        "boundaries": {
            "can_trade": False,
            "capital_permission": "DENY",
            "production_promotion": False,
            "secret_values_in_receipts": False,
        },
    }
    row.update(overrides)
    return row


def coverage_env(domain: str) -> dict:
    return {
        "envelope_id": f"COV-{domain}",
        "source_type": "AUDIT_COVERAGE",
        "observed_at": "2026-08-12T06:00:00+07:00",
        "producer": "TEST",
        "subject_id": domain,
        "evidence_refs": [f"EVIDENCE:{domain}"],
        "payload": {"domain": domain},
    }


def test_valid_current_generation_human_receipt_becomes_operator_coverage():
    normalized, contract = normalize_human_decision_receipt(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        data=human_receipt(),
    )
    assert contract is not None
    assert contract["valid"] is True
    assert contract["decision_count"] == 2
    assert normalized["operator_event"] is True
    assert normalized["subject_id"] == "ROBERT"
    assert normalized["actor"] == "ROBERT"

    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="CONTROL_CENTER_HUMAN_DECISION_RECEIPT:D1_D5_DECISION_RECEIPT.json",
        source_sha256="a" * 64,
        observed_at_fallback="2026-08-12T06:00:00+07:00",
        data=human_receipt(),
    )
    assert out["disposition"] == "EMITTED_COVERAGE"
    assert out["envelope"]["source_type"] == "AUDIT_COVERAGE"
    assert out["envelope"]["payload"]["domain"] == "OPERATOR"
    assert out["envelope"]["subject_id"] == "ROBERT"
    assert out["human_decision_contract"]["valid"] is True


def test_human_receipt_is_coverage_not_material_operator_finding():
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="decision:healthy",
        source_sha256="b" * 64,
        observed_at_fallback="2026-08-12T06:00:00+07:00",
        data=human_receipt(),
    )
    assert out["disposition"] == "EMITTED_COVERAGE"
    assert out["envelope"]["source_type"] == "AUDIT_COVERAGE"


def test_wrong_generation_does_not_close_operator_coverage():
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="decision:old-generation",
        source_sha256="c" * 64,
        observed_at_fallback="2026-08-12T06:00:00+07:00",
        data=human_receipt(generation="R63"),
    )
    assert out["disposition"] == "SKIPPED_NOT_OPERATOR_EVENT"
    assert out["envelope"] is None
    assert out["human_decision_contract"]["valid"] is False
    assert "GENERATION_MISMATCH" in out["human_decision_contract"]["reasons"]


def test_safety_boundary_mismatch_does_not_close_operator_coverage():
    bad = human_receipt(boundaries={"can_trade": True, "capital_permission": "ALLOW"})
    out = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="decision:unsafe-boundary",
        source_sha256="d" * 64,
        observed_at_fallback="2026-08-12T06:00:00+07:00",
        data=bad,
    )
    assert out["disposition"] == "SKIPPED_NOT_OPERATOR_EVENT"
    assert out["envelope"] is None
    assert "SAFETY_BOUNDARY_MISMATCH" in out["human_decision_contract"]["reasons"]


def test_authorization_utterance_and_decision_scopes_are_not_persisted():
    secret_phrase = "EXACT-HUMAN-AUTHORIZATION-DO-NOT-PROJECT"
    secret_scope = "PRIVATE-DECISION-SCOPE-DO-NOT-PROJECT"
    source = human_receipt(
        authorization_utterance=secret_phrase,
        decisions=[{"id": "D1", "verdict": "ACCEPT", "scope": secret_scope}],
    )
    out = adapt_artifacts([{
        "adapter_type": "OPERATOR_EVENT_ARTIFACT",
        "source_id": "decision:redaction-boundary",
        "source_sha256": "e" * 64,
        "observed_at_fallback": "2026-08-12T06:00:00+07:00",
        "data": source,
    }])
    serialized = json.dumps(out, ensure_ascii=False, sort_keys=True)
    assert secret_phrase not in serialized
    assert secret_scope not in serialized
    assert out["receipt"]["human_decision_receipts_validated"] == 1
    assert out["receipt"]["effect_boundary"]["human_decision_execution"] is False


def test_valid_human_receipt_closes_operator_attention_when_other_domains_are_covered():
    adapted = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT",
        source_id="decision:coverage",
        source_sha256="f" * 64,
        observed_at_fallback="2026-08-12T06:00:00+07:00",
        data=human_receipt(),
    )
    envelopes = [
        adapted["envelope"],
        coverage_env("SELF"),
        coverage_env("AGENT"),
        coverage_env("SYSTEM"),
    ]
    out = run_attention_fabric(
        {
            "fabric_run_id": "R39.2.2-DECISION-COVERAGE",
            "generated_at": "2026-08-12T06:00:00+07:00",
            "envelopes": envelopes,
        },
        governor_policy=GOV_POLICY,
        fabric_policy=FABRIC_POLICY,
    )
    assert out["attention_summary"]["coverage_complete"] is True
    assert out["attention_summary"]["domain_counts"]["OPERATOR"] == 1
    assert out["attention_summary"]["material_domain_counts"]["OPERATOR"] == 0


def test_r39_2_2_is_observation_only():
    out = adapt_artifacts([{
        "adapter_type": "OPERATOR_EVENT_ARTIFACT",
        "source_id": "decision:boundary",
        "source_sha256": "1" * 64,
        "observed_at_fallback": "2026-08-12T06:00:00+07:00",
        "data": human_receipt(),
    }])
    boundary = out["receipt"]["effect_boundary"]
    assert boundary["producer_reads_only"] is True
    assert boundary["provider_calls"] is False
    assert boundary["human_decision_execution"] is False
    assert boundary["synthetic_operator_events"] is False
    assert boundary["self_apply"] is False
    assert boundary["auto_dispatch"] is False
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"
