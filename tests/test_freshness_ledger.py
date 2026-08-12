from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data/freshness.r38.2.example.json"
VALIDATOR = ROOT / "scripts/validate_freshness_ledger.py"


def load_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def run_validator(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--ledger", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_freshness_ledger_example_passes():
    result = run_validator(LEDGER)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HANRI_R38_2_FRESHNESS_LEDGER_VALIDATION_PASS" in result.stdout


def test_exact_six_surface_set_is_required(tmp_path):
    payload = load_ledger()
    payload["surfaces"] = payload["surfaces"][:-1]
    path = tmp_path / "missing-surface.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert run_validator(path).returncode != 0


def test_source_readback_cannot_fake_current(tmp_path):
    payload = load_ledger()
    surface = payload["surfaces"][0]
    assert surface["source_available"] is True
    surface["freshness"] = "CURRENT"
    surface["current_proof"] = False
    path = tmp_path / "source-only-current.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = run_validator(path)
    assert result.returncode != 0
    assert "CURRENT requires current_proof=true" in result.stdout


def test_current_proof_requires_durable_refs(tmp_path):
    payload = load_ledger()
    surface = payload["surfaces"][0]
    surface["freshness"] = "CURRENT"
    surface["current_proof"] = True
    surface["proof_refs"] = []
    path = tmp_path / "missing-proof-refs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = run_validator(path)
    assert result.returncode != 0
    assert "current_proof=true requires proof_refs" in result.stdout


def test_promotion_requires_current_proof(tmp_path):
    payload = load_ledger()
    surface = payload["surfaces"][2]
    surface["promotion_allowed"] = True
    surface["current_proof"] = False
    path = tmp_path / "promotion-without-proof.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = run_validator(path)
    assert result.returncode != 0
    assert "promotion_allowed requires current_proof=true" in result.stdout


def test_do_not_touch_cannot_be_promoted(tmp_path):
    payload = load_ledger()
    surface = next(x for x in payload["surfaces"] if x["id"] == "codex-05")
    assert surface["operational_status"] == "DO_NOT_TOUCH"
    surface["promotion_allowed"] = True
    surface["current_proof"] = True
    surface["proof_refs"] = ["example-current-proof"]
    surface["freshness"] = "CURRENT"
    path = tmp_path / "do-not-touch-promoted.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = run_validator(path)
    assert result.returncode != 0
    assert "DO_NOT_TOUCH cannot be auto-promoted" in result.stdout


def test_effect_ceiling_is_fail_closed(tmp_path):
    for key, value in [
        ("can_trade", True),
        ("capital_permission", "ALLOW"),
        ("self_application", True),
        ("auto_dispatch", True),
        ("auto_promotion", True),
    ]:
        payload = copy.deepcopy(load_ledger())
        payload["invariants"][key] = value
        path = tmp_path / f"bad-{key}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert run_validator(path).returncode != 0
