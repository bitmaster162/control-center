from __future__ import annotations

import copy
from pathlib import Path

from build_effect_readback_plane import build, load

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = load(ROOT / "data" / "decision_effect_ledger.generated.v1.json")
RECEIPTS = load(ROOT / "data" / "effect_receipts.current.v1.json")


def must_fail(decisions, receipts, needle: str) -> None:
    try:
        build(decisions, receipts)
    except ValueError as exc:
        assert needle in str(exc), (needle, str(exc))
        return
    raise AssertionError(f"expected failure containing {needle}")


def main() -> int:
    current = build(copy.deepcopy(DECISIONS), copy.deepcopy(RECEIPTS))
    assert current["summary"]["effects_authorized"] == 0
    assert current["summary"]["executions_authorized"] == 0
    assert current["summary"]["execution_receipts"] == 0
    assert current["summary"]["readback_receipts"] == 0
    assert current["effect_candidates"][0]["stage"] == "AWAITING_HUMAN_EFFECT_AUTHORIZATION"

    fake_execution = copy.deepcopy(RECEIPTS)
    fake_execution["execution_receipts"] = [{
        "receipt_id": "EXEC-FAKE-1",
        "decision_id": "DEC::CODEX07-R43-RETURN-PLANE-V2",
        "work_order": "CODEX07-R43-RETURN-PLANE-V2"
    }]
    must_fail(copy.deepcopy(DECISIONS), fake_execution, "unauthorized_execution_receipt")

    fake_orphan = copy.deepcopy(RECEIPTS)
    fake_orphan["execution_receipts"] = [{
        "receipt_id": "EXEC-ORPHAN-1",
        "decision_id": "DEC::DOES-NOT-EXIST"
    }]
    must_fail(copy.deepcopy(DECISIONS), fake_orphan, "orphan_execution_receipt")

    fake_readback = copy.deepcopy(RECEIPTS)
    fake_readback["readback_receipts"] = [{
        "receipt_id": "READBACK-FAKE-1",
        "decision_id": "DEC::CODEX07-R43-RETURN-PLANE-V2",
        "execution_receipt_id": "EXEC-MISSING"
    }]
    must_fail(copy.deepcopy(DECISIONS), fake_readback, "readback_without_execution_receipt")

    bad_policy = copy.deepcopy(DECISIONS)
    bad_policy["policy"]["auto_apply"] = True
    must_fail(bad_policy, copy.deepcopy(RECEIPTS), "decision_policy_must_fail_closed")

    print("EFFECT_READBACK_PLANE_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
