from __future__ import annotations

import copy
import json
from pathlib import Path

from build_human_gate_packets import build, load, response_contract

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def expect_fail(name: str, command_queue, lifecycle, ledger, effect) -> None:
    try:
        build(command_queue, lifecycle, ledger, effect)
    except ValueError:
        return
    raise AssertionError(f"expected_fail::{name}")


def main() -> int:
    command_queue = load(DATA / "command_queue.generated.v1.json")
    lifecycle = load(DATA / "work_order_lifecycle.generated.v1.json")
    ledger = load(DATA / "decision_effect_ledger.generated.v1.json")
    effect = load(DATA / "effect_readback_plane.generated.v1.json")

    baseline = build(command_queue, lifecycle, ledger, effect)
    assert baseline["summary"]["human_now_commands"] == 0
    assert baseline["summary"]["packets_total"] == 0
    assert baseline["summary"]["execution_ready_packets"] == 0
    assert baseline["packets"] == []
    assert baseline["policy"]["generic_continuation_is_authorization"] is False

    try:
        response_contract("GO")
    except ValueError as exc:
        assert "unsupported_human_response::GO" in str(exc)
    else:
        raise AssertionError("generic GO must never be a valid decision token")

    forged = copy.deepcopy(command_queue)
    forged["policy"]["auto_apply"] = True
    expect_fail("queue_auto_apply", forged, lifecycle, ledger, effect)

    forged = copy.deepcopy(command_queue)
    forged["authority_anchor"]["pointer_sha256"] = "00" * 32
    expect_fail("tampered_r64_anchor", forged, lifecycle, ledger, effect)

    forged_queue = copy.deepcopy(command_queue)
    forged_queue["queues"]["HUMAN_NOW"] = ["CMD::CODEX07-R43-RETURN-PLANE-V2"]
    forged_queue["human_now"] = [{
        "command_id":"CMD::CODEX07-R43-RETURN-PLANE-V2",
        "decision_id":"DEC::CODEX07-R43-RETURN-PLANE-V2",
        "work_order":"CODEX07-R43-RETURN-PLANE-V2",
        "project":"Return Plane",
        "requested_action":"ROBERT_MIGRATION_DECISION",
        "allowed_decisions":["AUTHORIZE_APPLY","HOLD","REJECT_EFFECT"],
        "effect_stage":"NOT_EFFECT_CANDIDATE",
        "authority_granted":False,
        "auto_execute":False
    }]
    expect_fail("stale_historical_gate_reintroduced", forged_queue, lifecycle, ledger, effect)

    print(json.dumps({"status":"PASS","baseline_packets":0,"execution_ready":0,"adversarial_cases":4}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
