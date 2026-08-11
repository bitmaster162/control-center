from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "control_center.work_order_lifecycle.v1"
EXPECTED_POINTER_SHA = "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3"
EXPECTED_REGISTRY_ID = "1BXdqWzA74SvkgcygO_ktO_2uolqFshWm"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _semantic_return_for(slot: str, current: dict[str, Any]) -> dict[str, Any] | None:
    for row in current.get("returns", []):
        evidence = str(row.get("evidence", ""))
        if slot == "CODEX-07" and "CODEX-07" in evidence:
            return row
    return None


def _stage(row: dict[str, Any]) -> str:
    if row.get("historical_predecessor") is True:
        return "HISTORICAL_EVIDENCE_ONLY"
    if row.get("apply_status") == "APPLIED":
        return "READBACK_REQUIRED"
    if row.get("semantic_status") == "ACCEPTED":
        return "EFFECT_GATE_WAIT"
    state = str(row.get("reported_state", ""))
    if state.startswith("PENDING_") or state == "GATED_RESERVED":
        return "DISPATCH_BLOCKED"
    return "SEMANTIC_REVIEW_REQUIRED"


def build(agent: dict[str, Any], entries: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    anchor = agent.get("authority_anchor", {})
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE":
        errors.append("r64_anchor_mismatch")
    if anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA or anchor.get("provider_readback") != "all_exact":
        errors.append("pointer_binding_mismatch")
    if agent.get("global_dispatch", {}).get("auto_dispatch") is not False or agent.get("global_dispatch", {}).get("auto_accept") is not False:
        errors.append("agent_control_must_block_auto_transition")
    if entries.get("registry", {}).get("stable_drive_file_id") != EXPECTED_REGISTRY_ID:
        errors.append("registry_identity_mismatch")
    if current.get("canonical_current", {}).get("generation") != "R64":
        errors.append("current_projection_generation_mismatch")
    if errors:
        raise ValueError(";".join(errors))

    records: dict[str, dict[str, Any]] = {}
    slot_rows = {str(row.get("slot")): row for row in agent.get("slots", []) if row.get("slot")}

    for slot, src in slot_rows.items():
        work_order = src.get("work_order")
        if not work_order:
            continue
        record = {
            "work_order": work_order,
            "slot": slot,
            "project": src.get("project_hint", "UNBOUND"),
            "source_views": ["CURRENT_SLOT"],
            "reported_state": src.get("reported_state"),
            "reported_next": src.get("reported_next"),
            "registry_verification": None,
            "transport_status": "REGISTRY_OBSERVED",
            "semantic_status": "UNREVIEWED",
            "apply_status": "NOT_APPLIED",
            "semantic_source": None,
            "return_id": None,
            "dispatch_authorized": False,
            "effect_authorized": False,
            "effect_gate": "OWNER_ONLY_DO_NOT_TOUCH" if src.get("do_not_touch") else "R64_NO_FURTHER_AGENT_WORK",
            "readback_status": "NOT_DUE_NO_EFFECT",
            "do_not_touch": bool(src.get("do_not_touch")),
            "historical_predecessor": src.get("current_route") == "HISTORICAL_PREDECESSOR_NO_ACTION",
        }
        if record["historical_predecessor"]:
            record["canonical_runtime"] = src.get("canonical_runtime")
            record["source_conflict"] = src.get("source_conflict")
        semantic_return = _semantic_return_for(slot, current)
        if semantic_return:
            record.update(
                transport_status=semantic_return.get("transport_status", "UNKNOWN"),
                semantic_status=semantic_return.get("content_status", "UNREVIEWED"),
                apply_status=semantic_return.get("apply_status", "NOT_APPLIED"),
                semantic_source="CURRENT_CONTROL_PLANE_RETURN",
                return_id=semantic_return.get("return_id"),
            )
            if record["historical_predecessor"]:
                record["effect_gate"] = "NONE_STALE_PREDECESSOR_R59_ACTIVE"
                record["readback_status"] = "NOT_DUE_HISTORICAL_EVIDENCE"
            elif record["semantic_status"] == "ACCEPTED" and not record["do_not_touch"]:
                record["effect_gate"] = src.get("reported_next") or "EXPLICIT_HUMAN_EFFECT_GATE"
        records[work_order] = record

    for entry in entries.get("entries", []):
        work_order = entry.get("work_order")
        if not work_order:
            continue
        slot = str(entry.get("slot") or "UNBOUND")
        if work_order in records:
            rec = records[work_order]
            rec["source_views"].append("REGISTERED_ENTRY")
            rec["registry_verification"] = entry.get("verification_status")
            rec["entry_key"] = entry.get("entry_key")
            continue
        do_not_touch = "TRADINGOS" in str(entry.get("project", "")).upper()
        records[work_order] = {
            "work_order": work_order,
            "slot": slot,
            "project": entry.get("project", "UNBOUND"),
            "source_views": ["REGISTERED_ENTRY"],
            "reported_state": entry.get("verdict"),
            "reported_next": entry.get("next"),
            "registry_verification": entry.get("verification_status"),
            "transport_status": "REGISTRY_OBSERVED",
            "semantic_status": "UNREVIEWED",
            "apply_status": "NOT_APPLIED",
            "semantic_source": None,
            "return_id": None,
            "dispatch_authorized": False,
            "effect_authorized": False,
            "effect_gate": "OWNER_ONLY_DO_NOT_TOUCH" if do_not_touch else "R64_NO_FURTHER_AGENT_WORK",
            "readback_status": "NOT_DUE_NO_EFFECT",
            "do_not_touch": do_not_touch,
            "historical_predecessor": False,
            "entry_key": entry.get("entry_key"),
        }

    rows = sorted(records.values(), key=lambda r: (str(r.get("slot")), str(r.get("work_order"))))
    for row in rows:
        row["lifecycle_stage"] = _stage(row)

    slot_to_work: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        slot_to_work[row["slot"]].append(row["work_order"])

    divergences: list[dict[str, Any]] = []
    entry_slots = {str(e.get("slot")) for e in entries.get("entries", []) if e.get("slot") and e.get("work_order")}
    for slot, src in slot_rows.items():
        if not src.get("work_order") and slot in entry_slots:
            divergences.append({
                "slot": slot,
                "kind": "SLOT_MISSING_WORK_ORDER_ID_ENTRY_PRESENT",
                "work_orders": slot_to_work.get(slot, []),
                "action": "PRESERVE_BOTH_VIEWS_NO_SILENT_BINDING",
            })
    for slot, work_orders in sorted(slot_to_work.items()):
        if len(set(work_orders)) > 1:
            divergences.append({
                "slot": slot,
                "kind": "MULTIPLE_WORK_ORDERS_SAME_SLOT",
                "work_orders": work_orders,
                "action": "PRESERVE_VERSIONED_WORK_ORDERS_NO_AUTO_SUPERSESSION",
            })

    by_work = {row["work_order"]: row for row in rows}
    attention = []
    for item in agent.get("operator_attention", []):
        slot = str(item.get("slot"))
        direct = slot_rows.get(slot, {}).get("work_order")
        candidates = slot_to_work.get(slot, [])
        selected = direct if direct in by_work else (candidates[-1] if len(candidates) == 1 else None)
        attention.append({
            "rank": item.get("rank"),
            "slot": slot,
            "project": item.get("project"),
            "reported_state": item.get("reported_state"),
            "reason": item.get("reason"),
            "requested_next": item.get("requested_next"),
            "work_order": selected,
            "binding": "DIRECT_SLOT_WORK_ORDER" if direct else ("SINGLE_REGISTERED_ENTRY_SLOT_MATCH" if selected else "AMBIGUOUS_OR_UNBOUND"),
            "human_gate": item.get("human_gate"),
            "auto_dispatch": False,
        })

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["lifecycle_stage"]] += 1

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_PROJECTION",
        "observed_at": entries.get("observed_at") or agent.get("observed_at"),
        "authority_anchor": anchor,
        "chain": ["WORK_ORDER", "SLOT_OR_ENTRY", "RETURN_TRANSPORT", "SEMANTIC_DECISION", "EFFECT_GATE", "READBACK"],
        "global_policy": {
            "auto_dispatch": False,
            "auto_accept": False,
            "auto_apply": False,
            "effect_authorized_by_projection": False,
            "readback_required_after_any_effect": True,
        },
        "summary": {
            "work_orders_total": len(rows),
            "stage_counts": dict(sorted(counts.items())),
            "source_divergences": len(divergences),
            "semantic_accepted": sum(1 for r in rows if r["semantic_status"] == "ACCEPTED"),
            "applied": sum(1 for r in rows if r["apply_status"] == "APPLIED"),
            "historical_predecessor": sum(1 for r in rows if r.get("historical_predecessor") is True),
        },
        "operator_attention": attention,
        "source_divergences": divergences,
        "work_orders": rows,
        "invariants": {
            "registry_observation_never_semantic_acceptance": True,
            "entry_verification_never_semantic_acceptance": True,
            "semantic_acceptance_never_implies_apply": True,
            "historical_predecessor_never_effect_gate": True,
            "no_effect_without_explicit_gate": True,
            "tradingos_do_not_touch": True,
            "readback_required_after_any_effect": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent_control", type=Path)
    parser.add_argument("registry_entries", type=Path)
    parser.add_argument("current_control", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        out = build(load(args.agent_control), load(args.registry_entries), load(args.current_control))
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": str(exc).split(";")}, indent=2))
        return 2
    rendered = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
