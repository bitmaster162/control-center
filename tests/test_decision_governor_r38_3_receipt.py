from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/decision_governor_requal.py"
OBSERVED = ROOT / "data/decision_governor.r38.3.observed.json"
RECEIPT = ROOT / "data/decision_governor.r38.3.qualification.json"
FRESHNESS = ROOT / "data/freshness.r38.2.example.json"

spec = importlib.util.spec_from_file_location("decision_governor_requal_receipt", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
qualify = module.qualify


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_qualification_receipt_equals_deterministic_engine_output():
    assert load(RECEIPT) == qualify(load(OBSERVED))


def test_freshness_ledger_promotes_only_decision_governor_to_current():
    ledger = load(FRESHNESS)
    surfaces = {item["id"]: item for item in ledger["surfaces"]}
    governor = surfaces["decision-governor"]
    assert governor["operational_status"] == "OPERATIONAL"
    assert governor["freshness"] == "CURRENT"
    assert governor["current_proof"] is True
    assert governor["promotion_allowed"] is True
    assert "data/decision_governor.r38.3.qualification.json" in governor["proof_refs"]

    for surface_id in ("continuity-os", "archive-os", "fable-5", "codex-01", "codex-05"):
        surface = surfaces[surface_id]
        assert surface["freshness"] == "STALE"
        assert surface["current_proof"] is False
        assert surface["promotion_allowed"] is False


def test_decision_governor_current_row_preserves_effect_ceiling():
    ledger = load(FRESHNESS)
    assert ledger["invariants"] == {
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
        "auto_dispatch": False,
        "auto_promotion": False,
    }
