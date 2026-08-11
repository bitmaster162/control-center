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

    # VERIFIED registry entries are evidence only and never self-promote semantics.
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

    # Separately accepted CODEX-07 return still cannot self-apply.
    rp = rows["CODEX07-R43-RETURN-PLANE-V2"]
    assert rp["semantic_status"] == "ACCEPTED"
    assert rp["apply_status"] == "NOT_APPLIED"
    assert rp["effect_gate"] == "ROBERT_MIGRATION_DECISION"
    assert rp["effect_authorized"] is False
    assert rp["lifecycle_stage"] == "EFFECT_GATE_WAIT"

    # Pending work remains blocked, including a slot literally named PENDING_EXECUTION.
    assert rows["CODEX08-R57-PARASITE-KILLER-FRESH-READ-ONLY-SCAN"]["lifecycle_stage"] == "DISPATCH_BLOCKED"
    assert rows["CLAUDE-BITUNIX-R57-WO107-OBSERVATION-WINDOW"]["lifecycle_stage"] == "DISPATCH_BLOCKED"
    assert rows["FABLE5-R57-GATED-ADJUDICATION"]["lifecycle_stage"] == "DISPATCH_BLOCKED"

    # Same-slot version divergence is preserved rather than silently superseded.
    codex02 = [r for r in out["work_orders"] if r["slot"] == "CODEX-02"]
    assert len(codex02) == 2
    assert all(r["do_not_touch"] is True for r in codex02)

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
