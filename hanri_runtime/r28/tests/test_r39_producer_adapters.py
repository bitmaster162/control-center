from __future__ import annotations

import copy
import datetime as dt
import json
import os
from pathlib import Path

from hanri.attention_fabric import run_attention_fabric
from hanri.attention_governor import run_attention_governor
from hanri.producer_adapters import adapt_artifact, adapt_artifacts, collect_source_rows

ROOT = Path(__file__).resolve().parents[1]
GOV_POLICY = json.loads((ROOT / "config" / "r39.attention-governor.json").read_text(encoding="utf-8"))
FABRIC_POLICY = json.loads((ROOT / "config" / "r39.1.attention-fabric.json").read_text(encoding="utf-8"))
UTC = dt.timezone.utc


def coverage_env(domain: str, n: int) -> dict:
    return {
        "envelope_id": f"COV-{domain}-{n}",
        "source_type": "AUDIT_COVERAGE",
        "observed_at": "2026-08-12T05:00:00+07:00",
        "producer": "TEST",
        "subject_id": domain,
        "evidence_refs": [f"EVIDENCE:{domain}:{n}"],
        "payload": {"domain": domain},
    }


def test_healthy_coverage_all_domains_creates_no_false_findings_or_proposals():
    out = run_attention_fabric(
        {
            "fabric_run_id": "R39.2-COVERAGE-ONLY",
            "generated_at": "2026-08-12T05:00:00+07:00",
            "envelopes": [coverage_env(d, 1) for d in ("SELF", "AGENT", "SYSTEM", "OPERATOR")],
        },
        governor_policy=GOV_POLICY,
        fabric_policy=FABRIC_POLICY,
    )
    assert out["attention_summary"]["coverage_complete"] is True
    assert out["attention_summary"]["domain_counts"] == {"SELF": 1, "AGENT": 1, "SYSTEM": 1, "OPERATOR": 1}
    assert out["attention_summary"]["material_domain_counts"] == {"SELF": 0, "AGENT": 0, "SYSTEM": 0, "OPERATOR": 0}
    assert out["governor"]["findings"] == []
    assert out["prioritized_proposals"] == []
    assert out["ledger"]["coverage_count"] == 4


def test_material_observation_also_counts_as_attention_coverage():
    out = run_attention_governor(
        {
            "run_id": "R39.2-MATERIAL-COVERAGE",
            "generated_at": "2026-08-12T05:00:00+07:00",
            "observations": [{
                "observation_id": "A1",
                "domain": "AGENT",
                "subject_id": "CODEX-01",
                "signal": "SKILL_GAP",
                "severity": "HIGH",
                "summary": "missing verification skill",
                "evidence_refs": ["RETURN:1"],
            }],
            "attention_coverage": [
                {"coverage_id": "S1", "domain": "SELF", "evidence_refs": ["SELF:1"]},
                {"coverage_id": "Y1", "domain": "SYSTEM", "evidence_refs": ["SYS:1"]},
                {"coverage_id": "O1", "domain": "OPERATOR", "evidence_refs": ["OP:1"]},
            ],
        },
        policy=GOV_POLICY,
    )
    assert out["meta_audit"]["coverage_complete"] is True
    assert out["meta_audit"]["domain_counts"] == {"SELF": 1, "AGENT": 1, "SYSTEM": 1, "OPERATOR": 1}
    assert out["meta_audit"]["material_domain_counts"]["AGENT"] == 1
    assert len(out["proposals"]) == 1


def test_failed_agent_return_becomes_skill_candidate_end_to_end():
    adapted = adapt_artifact(
        adapter_type="RETURN_ARTIFACT",
        source_id="broker:CODEX-01:return-77.json",
        source_sha256="1" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={
            "agent_id": "CODEX-01",
            "status": "FAILED",
            "repeated_count": 3,
            "summary": "verification repeatedly missed",
            "evidence_refs": ["WO:R39.2"],
        },
    )
    assert adapted["disposition"] == "EMITTED_MATERIAL"
    assert adapted["envelope"]["source_type"] == "AGENT_RETURN"

    envelopes = [adapted["envelope"], coverage_env("SELF", 1), coverage_env("SYSTEM", 1), coverage_env("OPERATOR", 1)]
    out = run_attention_fabric(
        {"fabric_run_id": "RETURN-E2E", "generated_at": "2026-08-12T05:00:00+07:00", "envelopes": envelopes},
        governor_policy=GOV_POLICY,
        fabric_policy=FABRIC_POLICY,
    )
    skills = [p for p in out["prioritized_proposals"] if p["kind"] == "SKILL_CANDIDATE"]
    assert len(skills) == 1
    assert skills[0]["subject_id"] == "CODEX-01"
    assert skills[0]["skill_spec"]["install_authorized"] is False


def test_healthy_agent_return_emits_coverage_not_false_skill():
    adapted = adapt_artifact(
        adapter_type="RETURN_ARTIFACT",
        source_id="broker:CODEX-02:return-ok.json",
        source_sha256="2" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"agent_id": "CODEX-02", "status": "PASS", "summary": "strict return verified"},
    )
    assert adapted["disposition"] == "EMITTED_COVERAGE"
    assert adapted["envelope"]["source_type"] == "AUDIT_COVERAGE"
    assert adapted["envelope"]["payload"]["domain"] == "AGENT"


def test_system_pass_is_coverage_but_stale_is_material_improvement():
    healthy = adapt_artifact(
        adapter_type="SYSTEM_RECEIPT", source_id="r36:health-ok", source_sha256="3" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"system_id": "HANRI_R36", "status": "PASS", "freshness": "CURRENT", "summary": "healthy"},
    )
    stale = adapt_artifact(
        adapter_type="SYSTEM_RECEIPT", source_id="r36:health-stale", source_sha256="4" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"system_id": "HANRI_R36", "status": "PASS", "freshness": "STALE", "summary": "heartbeat stale"},
    )
    assert healthy["envelope"]["source_type"] == "AUDIT_COVERAGE"
    assert stale["envelope"]["source_type"] == "SYSTEM_HEALTH"


def test_operator_adapter_requires_explicit_human_binding():
    skipped = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT", source_id="event:agent", source_sha256="5" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"actor": "CODEX-07", "status": "PASS", "summary": "agent event"},
    )
    assert skipped["disposition"] == "SKIPPED_NOT_OPERATOR_EVENT"
    assert skipped["envelope"] is None

    material = adapt_artifact(
        adapter_type="OPERATOR_EVENT_ARTIFACT", source_id="event:robert", source_sha256="6" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"actor": "ROBERT", "signal": "MANUAL_REPEAT", "repeated_count": 4, "summary": "manual correction repeated"},
    )
    assert material["envelope"]["source_type"] == "OPERATOR_EVENT"


def test_hanri_pass_receipt_is_self_coverage_and_fail_is_self_finding():
    passed = adapt_artifact(
        adapter_type="HANRI_RECEIPT", source_id="hanri:pass", source_sha256="7" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"status": "PASS", "summary": "self audit passed"},
    )
    failed = adapt_artifact(
        adapter_type="HANRI_RECEIPT", source_id="hanri:fail", source_sha256="8" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"status": "FAIL", "missed_defect": True, "summary": "missed stale pointer"},
    )
    assert passed["envelope"]["source_type"] == "AUDIT_COVERAGE"
    assert passed["envelope"]["payload"]["domain"] == "SELF"
    assert failed["envelope"]["source_type"] == "HANRI_SELF_TRACE"


def test_secrets_are_redacted_and_never_persisted_raw():
    secret = "super-secret-token-123456"
    adapted = adapt_artifact(
        adapter_type="RETURN_ARTIFACT", source_id="broker:return-secret", source_sha256="9" * 64,
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={
            "agent_id": "CODEX-01",
            "status": "FAILED",
            "summary": f"api_key={secret}",
            "evidence_refs": [f"authorization: bearer {secret}"],
        },
    )
    serialized = json.dumps(adapted, ensure_ascii=False, sort_keys=True)
    assert secret not in serialized
    assert "REDACTED" in serialized
    assert adapted["secret_boundary"]["raw_values_persisted"] is False


def test_same_source_bytes_are_deterministic_and_changed_bytes_change_envelope_id():
    kwargs = dict(
        adapter_type="RETURN_ARTIFACT",
        source_id="broker:return-deterministic",
        observed_at_fallback="2026-08-12T05:00:00+07:00",
        data={"agent_id": "CODEX-01", "status": "PASS", "summary": "ok"},
    )
    a = adapt_artifact(source_sha256="a" * 64, **kwargs)
    b = adapt_artifact(source_sha256="a" * 64, **kwargs)
    c = adapt_artifact(source_sha256="b" * 64, **kwargs)
    assert a["envelope"] == b["envelope"]
    assert a["envelope"]["envelope_id"] != c["envelope"]["envelope_id"]


def test_source_scan_is_read_only_and_uses_actual_files(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    item = source / "return.json"
    item.write_text(json.dumps({"agent_id": "CODEX-01", "status": "PASS", "summary": "ok"}), encoding="utf-8")
    before = item.read_bytes()
    stamp = dt.datetime(2026, 8, 12, 0, 0, tzinfo=UTC).timestamp()
    os.utime(item, (stamp, stamp))

    config = {
        "max_file_bytes": 100000,
        "sources": [{
            "source_id": "TEST_RETURNS",
            "adapter_type": "RETURN_ARTIFACT",
            "path": str(source),
            "glob": "*.json",
            "recursive": False,
            "max_files": 10,
            "max_age_seconds": 0,
            "enabled": True,
        }],
    }
    rows, skipped = collect_source_rows(config, now=dt.datetime(2026, 8, 12, 1, 0, tzinfo=UTC))
    assert len(rows) == 1
    assert skipped == []
    assert item.read_bytes() == before
    adapted = adapt_artifacts(rows)
    assert adapted["receipt"]["effect_boundary"]["producer_reads_only"] is True
    assert adapted["receipt"]["effect_boundary"]["provider_calls"] is False
    assert adapted["receipt"]["effect_boundary"]["can_trade"] is False
    assert adapted["receipt"]["effect_boundary"]["capital_permission"] == "DENY"
