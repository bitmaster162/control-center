from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_snapshot():
    return json.loads((ROOT / "data/snapshot.v1.example.json").read_text(encoding="utf-8"))


def test_validator_passes():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate.py")], cwd=ROOT)
    assert result.returncode == 0


def test_json_schema_passes():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_snapshot.py")], cwd=ROOT)
    assert result.returncode == 0


def test_authority_and_effect_ceiling():
    meta = load_snapshot()["meta"]
    assert meta["authority_generation"] == "R63"
    assert meta["authority_status"] == "ACCEPTED"
    assert meta["control_generation_created"] is False
    assert meta["can_trade"] is False
    assert meta["capital_permission"] == "DENY"
    assert meta["deploy_permission"] == "DENY"
    assert meta["self_application"] is False


def test_every_material_projection_has_valid_evidence_refs():
    snapshot = load_snapshot()
    source_ids = {s["source_id"] for s in snapshot["sources"]}
    for key in ["kpis", "current_actions", "blockers", "events", "systems", "agents", "decisions", "memory_layers", "messages", "security"]:
        for item in snapshot[key]:
            assert item["evidence_refs"]
            assert set(item["evidence_refs"]) <= source_ids


def test_claimed_p0_never_renders_closed():
    for item in load_snapshot()["security"]:
        assert item["evidence_state"] == "CLAIMED"
        assert item["status"] == "CLAIMED_NOT_RECEIPTED"


def test_dashboard_has_audit_tab_and_nine_views():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-view="audit"' in html
    for view in ["overview", "systems", "agents", "decisions", "memory", "communications", "security", "audit", "arbiter"]:
        assert f'id="view-{view}"' in html


def test_standalone_is_self_contained_and_bound_to_snapshot_hash():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/generate_snapshot_assets.py")], cwd=ROOT)
    assert result.returncode == 0
    html = (ROOT / "HANRI_R64_DASHBOARD_STANDALONE_CONTRACT_V1.html").read_text(encoding="utf-8")
    assert 'href="assets/style.css"' not in html
    assert 'src="data/snapshot.js"' not in html
    assert 'src="assets/app.js"' not in html
    m = re.search(r'name="hanri-snapshot-sha256" content="([a-f0-9]{64})"', html)
    assert m
    assert m.group(1) == (ROOT / "data/snapshot.sha256").read_text(encoding="utf-8").split()[0]


def test_snapshot_generation_is_deterministic_for_identical_input():
    first = subprocess.run([sys.executable, str(ROOT / "scripts/generate_snapshot_assets.py")], cwd=ROOT)
    assert first.returncode == 0
    before_js = (ROOT / "data/snapshot.js").read_bytes()
    before_html = (ROOT / "HANRI_R64_DASHBOARD_STANDALONE_CONTRACT_V1.html").read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / "scripts/generate_snapshot_assets.py")], cwd=ROOT)
    assert result.returncode == 0
    assert (ROOT / "data/snapshot.js").read_bytes() == before_js
    assert (ROOT / "HANRI_R64_DASHBOARD_STANDALONE_CONTRACT_V1.html").read_bytes() == before_html


def test_invalid_effect_ceiling_fails_schema(tmp_path):
    snapshot = load_snapshot()
    snapshot["meta"]["can_trade"] = True
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(snapshot), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_snapshot.py"), "--snapshot", str(bad)], cwd=ROOT)
    assert result.returncode != 0


def test_unknown_evidence_ref_fails_validator(tmp_path):
    snapshot = load_snapshot()
    snapshot["systems"][0]["evidence_refs"] = ["missing-source"]
    bad = tmp_path / "bad-ref.json"
    bad.write_text(json.dumps(snapshot), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_snapshot.py"), "--snapshot", str(bad)], cwd=ROOT)
    assert result.returncode != 0


def test_p0_templates_do_not_contain_secret_values():
    for path in sorted((ROOT / "templates").glob("P0-*_CLOSURE.template.json")):
        text = path.read_text(encoding="utf-8")
        assert "password" not in text.lower()
        payload = json.loads(text)
        assert payload["secrets_exposed"] is False


def _valid_p0_receipt():
    return {
        "schema": "control_canter.p0_closure_receipt.v1",
        "p0_id": "P0-1",
        "status": "RECEIPTED_CLOSED",
        "action_class": "COMPENSATABLE",
        "started_at": "2026-07-29T20:00:00Z",
        "completed_at": "2026-07-29T20:10:00Z",
        "scope": "test scope",
        "negative_tests": [
            {"test_id": "external_connect", "expected": "REFUSED", "observed": "REFUSED", "status": "PASS", "timestamp": "2026-07-29T20:05:00Z", "command_redacted": "probe <redacted>", "exit_code": 1}
        ],
        "continuity_test": {"expected": "PASS", "observed": "PASS", "status": "PASS", "timestamp": "2026-07-29T20:06:00Z"},
        "rotation": {"new_access_activated_at": "2026-07-29T20:02:00Z", "old_access_revoked_at": "2026-07-29T20:04:00Z", "break_glass_status": "NOT_APPLICABLE"},
        "evidence": [{"locator": "receipt.log", "sha256": "a" * 64}],
        "secrets_exposed": False,
        "operator_presence_required": False,
        "notes": "redacted"
    }


def test_valid_p0_closure_receipt_passes(tmp_path):
    path = tmp_path / "p0.json"
    path.write_text(json.dumps(_valid_p0_receipt()), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_p0_receipt.py"), str(path)], cwd=ROOT)
    assert result.returncode == 0


def test_p0_closed_without_negative_test_pass_fails(tmp_path):
    payload = _valid_p0_receipt()
    payload["negative_tests"][0]["status"] = "NOT_RUN"
    path = tmp_path / "p0-bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_p0_receipt.py"), str(path)], cwd=ROOT)
    assert result.returncode != 0
