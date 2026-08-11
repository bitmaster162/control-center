from __future__ import annotations

import copy
import json
from pathlib import Path

from build_decision_effect_ledger import build
from validate_decision_effect_ledger import validate

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE = ROOT / "data" / "work_order_lifecycle.generated.v1.json"
LEDGER = ROOT / "data" / "decision_effect_ledger.generated.v1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def expect_fail(lifecycle, ledger, needle: str) -> None:
    errors = validate(lifecycle, ledger)
    assert errors, f"expected failure containing {needle!r}"
    assert any(needle in err for err in errors), errors


def main() -> int:
    lifecycle = load(LIFECYCLE)
    ledger = load(LEDGER)
    assert not validate(lifecycle, ledger), "baseline decision ledger must validate"
    assert build(lifecycle) == ledger, "generated ledger must equal builder semantics"

    mutated = copy.deepcopy(ledger)
    mutated["policy"]["auto_apply"] = True
    expect_fail(lifecycle, mutated, "automatic_or_self_transition_forbidden")

    mutated = copy.deepcopy(ledger)
    ripe = next(d for d in mutated["decisions"] if d["work_order"] == "CODEX07-R43-RETURN-PLANE-V2")
    ripe["effect_authorized"] = True
    expect_fail(lifecycle, mutated, "effect_authorized_without_gate")

    mutated = copy.deepcopy(ledger)
    ripe = next(d for d in mutated["decisions"] if d["work_order"] == "CODEX07-R43-RETURN-PLANE-V2")
    ripe["execution_authorized"] = True
    expect_fail(lifecycle, mutated, "execution_authorized_without_execution_gate")

    mutated = copy.deepcopy(ledger)
    trading = next(d for d in mutated["decisions"] if d["work_order"] == "CODEX02-R50-TRADINGOS-DECISION-BRIEF-MVP")
    trading["owner"] = "CONTROL_CENTER"
    trading["decision_state"] = "OPEN"
    expect_fail(lifecycle, mutated, "do_not_touch_owner_boundary_broken")

    mutated = copy.deepcopy(ledger)
    blocked = next(d for d in mutated["decisions"] if d["work_order"] == "CODEX08-R57-PARASITE-KILLER-FRESH-READ-ONLY-SCAN")
    blocked["human_ripe"] = True
    blocked["decision_state"] = "OPEN"
    expect_fail(lifecycle, mutated, "blocked_dispatch_surfaced_as_ripe")

    mutated = copy.deepcopy(ledger)
    mutated["queues"]["human_ripe"].append("DEC::CODEX08-R57-PARASITE-KILLER-FRESH-READ-ONLY-SCAN")
    expect_fail(lifecycle, mutated, "human_ripe_queue_not_exactly_return_plane_gate")

    mutated = copy.deepcopy(ledger)
    decision = next(d for d in mutated["decisions"] if d["owner"] == "CONTROL_CENTER")
    decision["decision_outcome"] = "ACCEPT"
    expect_fail(lifecycle, mutated, "projection_must_not_record_new_outcome")

    print("DECISION_EFFECT_LEDGER_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
