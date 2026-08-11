from __future__ import annotations

import copy
import json
from pathlib import Path

from build_human_gate_packets import build, load

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
    assert baseline["summary"]["packets_total"] == 1
    assert baseline["summary"]["execution_ready_packets"] == 0
    packet = baseline["packets"][0]
    assert packet["work_order"] == "CODEX07-R43-RETURN-PLANE-V2"
    assert packet["gate"] == "ROBERT_MIGRATION_DECISION"
    assert packet["executor_binding"]["executor"] is None
    assert packet["executor_binding"]["state"] == "UNBOUND_REQUIRES_SEPARATE_BINDING"
    assert packet["effect_scope"]["execution_ready"] is False
    assert packet["current_state"]["effect_authorized"] is False
    assert packet["current_state"]["execution_authorized"] is False
    assert baseline["policy"]["generic_continuation_is_authorization"] is False

    authorize = next(x for x in packet["allowed_responses"] if x["response"] == "AUTHORIZE_APPLY")
    assert authorize["effect_authority_result"] == "BOUNDED_EFFECT_AUTHORIZATION_FOR_PACKET_SCOPE_ONLY"
    assert authorize["execution_authority_result"] == "NOT_GRANTED"
    assert "BIND_EXECUTOR" in authorize["next_required"]
    assert "SEPARATE_EXECUTION_AUTHORIZATION" in authorize["next_required"]
    assert "EXECUTION" in authorize["does_not_authorize"]

    forged = copy.deepcopy(command_queue)
    forged["policy"]["auto_apply"] = True
    expect_fail("queue_auto_apply", forged, lifecycle, ledger, effect)

    forged = copy.deepcopy(command_queue)
    forged["human_now"][0]["authority_granted"] = True
    expect_fail("command_authority_granted", forged, lifecycle, ledger, effect)

    forged = copy.deepcopy(ledger)
    target = next(x for x in forged["decisions"] if x["decision_id"] == "DEC::CODEX07-R43-RETURN-PLANE-V2")
    target["human_ripe"] = False
    expect_fail("decision_not_human_ripe", command_queue, lifecycle, forged, effect)

    forged = copy.deepcopy(ledger)
    target = next(x for x in forged["decisions"] if x["decision_id"] == "DEC::CODEX07-R43-RETURN-PLANE-V2")
    target["decision_class"] = "SEMANTIC_ADJUDICATION"
    expect_fail("wrong_decision_class", command_queue, lifecycle, forged, effect)

    forged = copy.deepcopy(ledger)
    target = next(x for x in forged["decisions"] if x["decision_id"] == "DEC::CODEX07-R43-RETURN-PLANE-V2")
    target["allowed_decisions"] = ["AUTHORIZE_APPLY", "HOLD", "REJECT_EFFECT", "GO"]
    forged_queue = copy.deepcopy(command_queue)
    forged_queue["human_now"][0]["allowed_decisions"] = ["AUTHORIZE_APPLY", "HOLD", "REJECT_EFFECT", "GO"]
    expect_fail("generic_go_not_valid_decision", forged_queue, lifecycle, forged, effect)

    forged = copy.deepcopy(effect)
    target = next(x for x in forged["effect_candidates"] if x["decision_id"] == "DEC::CODEX07-R43-RETURN-PLANE-V2")
    target["effect_authorized"] = True
    expect_fail("preauthorized_effect", command_queue, lifecycle, ledger, forged)

    forged = copy.deepcopy(effect)
    target = next(x for x in forged["effect_candidates"] if x["decision_id"] == "DEC::CODEX07-R43-RETURN-PLANE-V2")
    target["execution_receipt_id"] = "FORGED_RECEIPT"
    expect_fail("forged_execution_receipt", command_queue, lifecycle, ledger, forged)

    forged = copy.deepcopy(effect)
    forged["effect_candidates"] = []
    expect_fail("missing_effect_candidate", command_queue, lifecycle, ledger, forged)

    forged = copy.deepcopy(lifecycle)
    target = next(x for x in forged["work_orders"] if x["work_order"] == "CODEX07-R43-RETURN-PLANE-V2")
    target["apply_status"] = "APPLIED"
    expect_fail("already_applied", command_queue, forged, ledger, effect)

    forged = copy.deepcopy(command_queue)
    forged["authority_anchor"]["pointer_sha256"] = "00" * 32
    expect_fail("tampered_r64_anchor", forged, lifecycle, ledger, effect)

    print(json.dumps({
        "status": "PASS",
        "baseline_packets": baseline["summary"]["packets_total"],
        "execution_ready": baseline["summary"]["execution_ready_packets"],
        "adversarial_cases": 10,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
