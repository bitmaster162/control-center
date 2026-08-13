from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.archiveos_freshness_qual import qualify

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = ROOT / "data/archiveos.r38.5.observed.json"
QUALIFICATION = ROOT / "data/archiveos.r38.5.qualification.json"
DELTA = ROOT / "data/freshness.r38.5.archiveos.delta.json"
LEDGER = ROOT / "data/freshness.r38.2.example.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def positive_observed() -> dict:
    payload = copy.deepcopy(load(OBSERVED))
    root = payload["authoritative_root_readback"]
    root.update(
        {
            "provider_readback_available": True,
            "root_exists_verified": True,
            "full_integrity_receipt_present": True,
            "full_sha_performed": True,
            "bytes_hashed": 123456,
            "file_count": 321,
            "manifest_sha256": "a" * 64,
            "independent_readback_present": True,
            "independent_manifest_sha256": "a" * 64,
            "independent_file_count": 321,
        }
    )
    return payload


def test_observed_fixture_is_blocked_and_matches_receipt():
    observed = load(OBSERVED)
    expected = load(QUALIFICATION)
    assert qualify(observed) == expected
    assert expected["status"] == "BLOCKED_REVERIFY"
    assert expected["freshness"] == "STALE"
    assert expected["current_claim_allowed"] is False
    assert expected["promotion_eligible"] is False


def test_drive_mirror_and_handoff_checksum_cannot_fake_current():
    observed = load(OBSERVED)
    assert observed["provider_readbacks"]["drive_mirrors"]
    assert observed["provider_readbacks"]["archive_tooling_handoff"]["archive_sha256"]
    result = qualify(observed)
    assert result["status"] == "BLOCKED_REVERIFY"
    assert "authoritative root provider readback is missing" in result["proof_gap"]


def test_cached_stat_guard_cannot_substitute_for_full_integrity():
    observed = load(OBSERVED)
    r36 = observed["provider_readbacks"]["hanri_r36_integrity"]
    assert r36["integrity_mode"] == "CACHED_STAT_GUARD"
    assert r36["full_sha_performed"] is False
    assert r36["bytes_hashed"] == 0
    result = qualify(observed)
    assert result["claim_ceiling"]["cached_stat_guard_is_full_integrity"] is False
    assert result["current_claim_allowed"] is False


def test_complete_authoritative_full_hash_and_independent_readback_can_pass():
    result = qualify(positive_observed())
    assert result["status"] == "PASS"
    assert result["freshness"] == "CURRENT"
    assert result["operational_status"] == "OPERATIONAL"
    assert result["current_claim_allowed"] is True
    assert result["promotion_eligible"] is True
    assert result["proof_gap"] == []


def test_independent_manifest_mismatch_fails_closed():
    observed = positive_observed()
    observed["authoritative_root_readback"]["independent_manifest_sha256"] = "b" * 64
    result = qualify(observed)
    assert result["status"] == "BLOCKED_REVERIFY"
    assert "independent manifest SHA-256 does not match authoritative receipt" in result["proof_gap"]


def test_effect_ceiling_drift_fails_closed():
    observed = positive_observed()
    observed["effects"]["writes"] = 1
    observed["invariants"]["can_trade"] = True
    result = qualify(observed)
    assert result["status"] == "BLOCKED_REVERIFY"
    assert "effect ceiling drift: effects.writes" in result["proof_gap"]
    assert "effect ceiling drift: invariants.can_trade" in result["proof_gap"]


def test_source_precedence_cannot_be_widened():
    observed = positive_observed()
    observed["source_precedence"]["drive_role"] = "AUTHORITY"
    observed["source_precedence"]["archive_tooling_role"] = "ARCHIVE_ENGINE"
    result = qualify(observed)
    assert result["status"] == "BLOCKED_REVERIFY"
    assert "Drive source-precedence boundary is missing or widened" in result["proof_gap"]
    assert "Archive Tooling boundary is missing or widened" in result["proof_gap"]


def test_blocked_delta_is_additive_and_predecessor_ledger_stays_fail_closed():
    delta = load(DELTA)
    assert delta["surface_id"] == "archive-os"
    assert delta["classification"] == "ADDITIVE_EVIDENCE_ONLY_NO_CURRENT_PROMOTION"
    assert delta["operational_status"] == "BLOCKED_REVERIFY"
    assert delta["freshness"] == "STALE"
    assert delta["current_proof"] is False
    assert delta["promotion_allowed"] is False
    assert "data/archiveos.r38.5.qualification.json" in delta["proof_refs"]

    ledger = load(LEDGER)
    surfaces = {row["id"]: row for row in ledger["surfaces"]}
    archive = surfaces["archive-os"]
    assert archive["freshness"] == "STALE"
    assert archive["current_proof"] is False
    assert archive["promotion_allowed"] is False

    assert surfaces["continuity-os"]["freshness"] == "CURRENT"
    assert surfaces["decision-governor"]["freshness"] == "CURRENT"
    assert surfaces["fable-5"]["freshness"] == "STALE"
    assert surfaces["codex-01"]["freshness"] == "STALE"
    assert surfaces["codex-05"]["freshness"] == "STALE"
    assert surfaces["codex-05"]["operational_status"] == "DO_NOT_TOUCH"
