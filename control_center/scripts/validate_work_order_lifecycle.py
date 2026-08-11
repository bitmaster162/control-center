from __future__ import annotations

import json
from pathlib import Path

from build_work_order_lifecycle import build, load

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "data" / "agent_control_plane.generated.v1.json"
ENTRIES = ROOT / "data" / "work_order_registry_entries.current.v1.json"
CURRENT = ROOT / "data" / "current_control_plane.generated.v1.json"
GENERATED = ROOT / "data" / "work_order_lifecycle.generated.v1.json"


def main() -> int:
    expected = build(load(AGENT), load(ENTRIES), load(CURRENT))
    actual = load(GENERATED)
    errors: list[str] = []
    if actual != expected:
        errors.append("generated_lifecycle_semantic_mismatch")

    rows = {r.get("work_order"): r for r in actual.get("work_orders", [])}
    if actual.get("summary", {}).get("work_orders_total") != 14:
        errors.append("work_order_total_mismatch")
    if actual.get("summary", {}).get("applied") != 0:
        errors.append("unexpected_applied_work_order")
    if any(r.get("dispatch_authorized") is not False or r.get("effect_authorized") is not False for r in rows.values()):
        errors.append("unauthorized_transition_detected")

    return_plane = rows.get("CODEX07-R43-RETURN-PLANE-V2", {})
    if not (
        return_plane.get("transport_status") == "ACKNOWLEDGED"
        and return_plane.get("semantic_status") == "ACCEPTED"
        and return_plane.get("apply_status") == "NOT_APPLIED"
        and return_plane.get("effect_gate") == "ROBERT_MIGRATION_DECISION"
        and return_plane.get("effect_authorized") is False
    ):
        errors.append("return_plane_lifecycle_boundary_mismatch")

    trading = [r for r in rows.values() if r.get("slot") == "CODEX-02"]
    if len(trading) != 2 or any(not r.get("do_not_touch") or r.get("effect_gate") != "OWNER_ONLY_DO_NOT_TOUCH" for r in trading):
        errors.append("tradingos_owner_boundary_mismatch")

    divergences = {(d.get("slot"), d.get("kind")) for d in actual.get("source_divergences", [])}
    if ("CODEX-04", "SLOT_MISSING_WORK_ORDER_ID_ENTRY_PRESENT") not in divergences:
        errors.append("codex04_slot_entry_divergence_missing")
    if ("CODEX-02", "MULTIPLE_WORK_ORDERS_SAME_SLOT") not in divergences:
        errors.append("codex02_version_divergence_missing")

    status = "PASS" if not errors else "FAIL"
    print(json.dumps({"status": status, "errors": errors, "work_orders": len(rows)}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
