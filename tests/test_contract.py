from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_validator_passes():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/validate.py")], cwd=ROOT)
    assert result.returncode == 0


def test_dashboard_is_openable_static():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data/snapshot.js' in html
    assert 'assets/app.js' in html
    assert '<title>HANRI Control Center R64</title>' in html


def test_safety_and_truth_labels_present():
    snapshot = (ROOT / "data/snapshot.js").read_text(encoding="utf-8")
    assert 'can_trade: false' in snapshot
    assert 'capital_permission: "DENY"' in snapshot
    assert 'SNAPSHOT / NOT LIVE' in snapshot
    assert 'EXACT_PHRASE_NOT_LOCATED' in snapshot
