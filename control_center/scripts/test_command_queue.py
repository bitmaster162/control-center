from __future__ import annotations

import copy
import json
from pathlib import Path

from build_command_queue import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def expect_fail(name: str, fn) -> None:
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"{name}: expected ValueError")


def sources():
    return (
        load(DATA / "agent_control_plane.generated.v1.json"),
        load(DATA / "work_order_lifecycle.generated.v1.json"),
        load(DATA / "decision_effect_ledger.generated.v1.json"),
        load(DATA / "effect_readback_plane.generated.v1.json"),
    )


def main() -> int:
    agent, lifecycle, ledger, effect = sources()
    one = build(agent, lifecycle, ledger, effect)
    two = build(copy.deepcopy(agent), copy.deepcopy(lifecycle), copy.deepcopy(ledger), copy.deepcopy(effect))
    assert one == two, "deterministic replay mismatch"
    assert one["summary"] == {
        "commands_total": 14,
        "human_now": 0,
        "control_center_queue": 8,
        "project_owner_queue": 2,
        "blocked_queue": 3,
        "historical_queue": 1,
        "effect_candidates": 0,
        "provenance_divergences": 2,
        "effects_authorized": 0,
        "executions_authorized": 0,
    }
    assert one["queues"]["HUMAN_NOW"] == []
    assert one["human_now"] == []
    assert one["queues"]["HISTORICAL_QUEUE"] == ["CMD::CODEX07-R43-RETURN-PLANE-V2"]
    assert all(x["queue"] == "CONTROL_CENTER_QUEUE" for x in one["attention_routing"])
    assert set(one["owner_only_do_not_touch"]) == {
        "CMD::CODEX02-R43-TRADINGOS-CONTRACT-CLOSURE",
        "CMD::CODEX02-R50-TRADINGOS-DECISION-BRIEF-MVP",
    }
    divergence_by_work = {d["work_order"]: d for d in one["provenance_divergences"]}
    assert divergence_by_work["CODEX02-R50-TRADINGOS-DECISION-BRIEF-MVP"]["lifecycle_reported_state"] == "PRODUCT_MVP_PASS"
    assert divergence_by_work["CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR"]["lifecycle_reported_state"] == "TRUTH_REPAIR_CANDIDATE_PASS"

    def stale_history_promoted():
        a, l, d, e = sources(); d = copy.deepcopy(d)
        row = next(x for x in d["decisions"] if x["work_order"] == "CODEX07-R43-RETURN-PLANE-V2")
        row["human_ripe"] = True; row["owner"] = "ROBERT"; row["decision_state"] = "OPEN"
        build(a, l, d, e)
    expect_fail("historical predecessor promoted to human", stale_history_promoted)

    def extra_human_escalation():
        a, l, d, e = sources(); d = copy.deepcopy(d)
        row = next(x for x in d["decisions"] if x["work_order"] == "CODEX08-R57-PARASITE-KILLER-FRESH-READ-ONLY-SCAN")
        row["human_ripe"] = True
        build(a, l, d, e)
    expect_fail("blocked dispatch promoted to human", extra_human_escalation)

    def tradingos_takeover():
        a, l, d, e = sources(); d = copy.deepcopy(d)
        row = next(x for x in d["decisions"] if x["work_order"] == "CODEX02-R50-TRADINGOS-DECISION-BRIEF-MVP")
        row["owner"] = "CONTROL_CENTER"; row["decision_state"] = "OPEN"
        build(a, l, d, e)
    expect_fail("TradingOS takeover", tradingos_takeover)

    def fabricated_effect_candidate():
        a, l, d, e = sources(); e = copy.deepcopy(e)
        e["effect_candidates"] = [{"decision_id":"DEC::CODEX07-R43-RETURN-PLANE-V2","effect_authorized":False,"execution_authorized":False}]
        build(a, l, d, e)
    expect_fail("historical effect candidate", fabricated_effect_candidate)

    def auto_apply_regression():
        a, l, d, e = sources(); e = copy.deepcopy(e); e["policy"]["auto_apply"] = True
        build(a, l, d, e)
    expect_fail("auto apply regression", auto_apply_regression)

    def broken_lifecycle_binding():
        a, l, d, e = sources(); l = copy.deepcopy(l)
        l["work_orders"] = [x for x in l["work_orders"] if x["work_order"] != "CODEX01-R43-CONTINUITY-186-CLOSURE"]
        build(a, l, d, e)
    expect_fail("broken lifecycle binding", broken_lifecycle_binding)

    print(json.dumps({"status":"PASS","tests":["deterministic_replay","zero_human_now","historical_queue_exact","attention_routing","tradingos_owner_only","provenance_divergence_preserved","historical_human_escalation_rejected","blocked_human_escalation_rejected","tradingos_takeover_rejected","historical_effect_candidate_rejected","auto_apply_rejected","broken_lifecycle_binding_rejected"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
