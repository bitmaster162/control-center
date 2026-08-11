from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from build_work_order_lifecycle import build, load

ROOT = Path(__file__).resolve().parents[1]
AGENT = load(ROOT / "data" / "agent_control_plane.generated.v1.json")
ENTRIES = load(ROOT / "data" / "work_order_registry_entries.current.v1.json")
CURRENT = load(ROOT / "data" / "current_control_plane.generated.v1.json")


def expect_fail(agent, entries, current, marker: str) -> None:
    try:
        build(agent, entries, current)
    except ValueError as exc:
        if marker not in str(exc):
            raise AssertionError(f"expected {marker}, got {exc}") from exc
        return
    raise AssertionError(f"expected failure: {marker}")


def main() -> int:
    out = build(deepcopy(AGENT), deepcopy(ENTRIES), deepcopy(CURRENT))
    rows = {r["work_order"]: r for r in out["work_orders"]}

    for wo in (
        "CODEX03-R49B-MAWORLD-PHYSICAL-RLS-21OF21",
        "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE",
        "CODEX02-R50-TRADINGOS-DECISION-BRIEF-MVP",
        "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR",
        "ANTIGRAVITY-R57-PRODUCT-SURFACE-SMOKE-AND-RETURN-INTAKE",
    ):
        assert rows[wo]["semantic_status"] == "UNREVIEWED"
        assert rows[wo]["apply_status"] == "NOT_APPLIED"
        assert rows[wo]["effect_authorized"] is False

    rp = rows["CODEX07-R43-RETURN-PLANE-V2"]
    assert rp["semantic_status"] == "ACCEPTED"
    assert rp["apply_status"] == "NOT_APPLIED"
    assert rp["historical_predecessor"] is True
    assert rp["effect_gate"] == "NONE_STALE_PREDECESSOR_R59_ACTIVE"
    assert rp["effect_authorized"] is False
    assert rp["lifecycle_stage"] == "HISTORICAL_EVIDENCE_ONLY"
    assert rp["canonical_runtime"]["watcher_generation"] == "R59"
    assert out["summary"]["stage_counts"].get("EFFECT_GATE_WAIT", 0) == 0

    assert rows["CODEX08-R57-PARASITE-KILLER-FRESH-READ-ONLY-SCAN"]["lifecycle_stage"] == "DISPATCH_BLOCKED"
    assert rows["CLAUDE-BITUNIX-R57-WO107-OBSERVATION-WINDOW"]["lifecycle_stage"] == "DISPATCH_BLOCKED"
    assert rows["FABLE5-R57-GATED-ADJUDICATION"]["lifecycle_stage"] == "DISPATCH_BLOCKED"

    codex02 = [r for r in out["work_orders"] if r["slot"] == "CODEX-02"]
    assert len(codex02) == 2
    assert all(r["do_not_touch"] is True for r in codex02)

    # If canonical routing evidence is removed, the builder must not silently treat
    # the historical row as current; the agent projection itself is the fail-closed boundary.
    stale_agent = deepcopy(AGENT)
    code7 = next(s for s in stale_agent["slots"] if s["slot"] == "CODEX-07")
    code7.pop("current_route", None)
    code7.pop("canonical_runtime", None)
    code7.pop("source_conflict", None)
    stale = build(stale_agent, deepcopy(ENTRIES), deepcopy(CURRENT))
    stale_rp = next(r for r in stale["work_orders"] if r["work_order"] == "CODEX07-R43-RETURN-PLANE-V2")
    assert stale_rp["lifecycle_stage"] == "EFFECT_GATE_WAIT"
    assert stale_rp["effect_gate"] == "ROBERT_MIGRATION_DECISION"
    assert stale_rp["historical_predecessor"] is False

    bad_agent = deepcopy(AGENT)
    bad_agent["global_dispatch"]["auto_dispatch"] = True
    expect_fail(bad_agent, deepcopy(ENTRIES), deepcopy(CURRENT), "agent_control_must_block_auto_transition")

    bad_entries = deepcopy(ENTRIES)
    bad_entries["registry"]["stable_drive_file_id"] = "wrong"
    expect_fail(deepcopy(AGENT), bad_entries, deepcopy(CURRENT), "registry_identity_mismatch")

    bad_agent = deepcopy(AGENT)
    bad_agent["authority_anchor"]["pointer_sha256"] = "wrong"
    expect_fail(bad_agent, deepcopy(ENTRIES), deepcopy(CURRENT), "pointer_binding_mismatch")

    print("WORK_ORDER_LIFECYCLE_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
