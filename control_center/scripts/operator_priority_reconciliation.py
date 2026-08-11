from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
QUEUE = BASE / "data" / "command_queue.generated.v1.json"
LIFECYCLE = BASE / "data" / "work_order_lifecycle.generated.v1.json"
LEDGER = BASE / "data" / "decision_effect_ledger.generated.v1.json"
REGISTRY = BASE / "data" / "work_order_registry_entries.current.v1.json"
EVIDENCE = BASE / "data" / "operator_priority_evidence.current.v1.json"
OUTPUT = BASE / "data" / "operator_priority_reconciliation.generated.v1.json"

SCHEMA = "control_center.operator_priority_reconciliation.v1"
PROJECTION_KIND = "NON_AUTHORITY_OPERATOR_PRIORITY_RECONCILIATION"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _work_order(lifecycle: dict[str, Any], work_order: str) -> dict[str, Any] | None:
    for item in lifecycle.get("work_orders", []):
        if item.get("work_order") == work_order:
            return item
    return None


def _decision(ledger: dict[str, Any], work_order: str) -> dict[str, Any] | None:
    for item in ledger.get("decisions", []):
        if item.get("work_order") == work_order:
            return item
    return None


def _external(evidence: dict[str, Any], work_order: str) -> dict[str, Any] | None:
    for item in evidence.get("top3_external_evidence", []):
        if item.get("work_order") == work_order:
            return item
    return None


def _queue_rank(queue: dict[str, Any], work_order: str) -> int | None:
    for item in queue.get("attention_routing", []):
        if item.get("work_order") == work_order:
            return item.get("rank")
    return None


def safety() -> dict[str, Any]:
    return {
        "current_truth_mutation_authorized": False,
        "return_registry_mutation_authorized": False,
        "routing_mutation_authorized": False,
        "dispatch_authorized": False,
        "semantic_acceptance_authorized_by_projection": False,
        "apply_authorized": False,
        "execution_authorized": False,
        "deploy_authorized": False,
        "external_message_authorized": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
    }


def build_projection(
    queue: dict[str, Any],
    lifecycle: dict[str, Any],
    ledger: dict[str, Any],
    registry: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    human_now_before = len(queue.get("human_now", []))
    effect_before = int(queue.get("summary", {}).get("effect_candidates", 0))

    continuity_current = _work_order(lifecycle, "CODEX01-R43-CONTINUITY-186-CLOSURE")
    continuity_newer = _external(evidence, "CODEX01-R52-CONTINUITYOS-CANONICAL-ADOPTION")

    maworld_current = _work_order(lifecycle, "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE")
    maworld_forensics = _external(
        evidence,
        "ANTIGRAVITY-WO042-R52-RETURN-HARVEST-AND-MAWORLD-INITDB-FORENSICS",
    )
    maworld_repair = _external(evidence, "CODEX03-R52-MAWORLD-INITDB-REPAIR")

    arena_current = _work_order(lifecycle, "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR")
    arena_decision = _decision(ledger, "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR")
    arena_external = _external(evidence, "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR")

    candidates: list[dict[str, Any]] = []

    if (
        continuity_current
        and continuity_newer
        and continuity_newer.get("status") == "VERIFIED_PASS"
        and continuity_current.get("work_order") != continuity_newer.get("work_order")
    ):
        candidates.append(
            {
                "rank": 1,
                "project": "ContinuityOS",
                "gap_class": "VERIFIED_NEWER_RETURN_NOT_BOUND_IN_CURRENT_TOP3_CHAIN",
                "current_queue_rank": _queue_rank(queue, "CODEX01-R43-CONTINUITY-186-CLOSURE"),
                "current_work_order": continuity_current.get("work_order"),
                "newer_evidence_work_order": continuity_newer.get("work_order"),
                "newer_evidence_status": continuity_newer.get("status"),
                "selected_action": "CONTINUITYOS_R52_EXISTING_RETURN_BINDING_RECONCILIATION",
                "bounded_scope": [
                    "LOCATE_EXISTING_R52_STRICT_RETURN_BYTES_OR_EXACT_CONTROLLER_COPY",
                    "VERIFY_IDENTITY_SHA_READY_AND_NO_EFFECT_RECEIPTS_WITHOUT_RERUN",
                    "COMPARE_R52_ADOPTION_RESULT_AGAINST_CURRENT_R43_BINDING",
                    "PROPOSE_SUPERSESSION_OR_EXACT_MISSING_BYTES_HOLD_WITHOUT_APPLY",
                ],
                "stop_condition": "STOP_AFTER_BINDING_PROPOSAL_OR_EXACT_MISSING_BYTES_HOLD",
                "reason": "R61 precedence places the physically verified R55 controller bundle above the stable older registry, while current R64 top-3 still references the R43 ContinuityOS closure.",
            }
        )

    if (
        maworld_current
        and maworld_forensics
        and maworld_forensics.get("status") == "VERIFIED_PASS"
        and maworld_repair
        and maworld_repair.get("status") == "USER_REPORTED_DONE_RETURN_MISSING"
    ):
        candidates.append(
            {
                "rank": 2,
                "project": "MAWorld",
                "gap_class": "NEWER_FORENSICS_VERIFIED_REPAIR_RETURN_MISSING",
                "current_queue_rank": _queue_rank(queue, "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE"),
                "current_work_order": maworld_current.get("work_order"),
                "newer_forensics_work_order": maworld_forensics.get("work_order"),
                "newer_forensics_status": maworld_forensics.get("status"),
                "repair_work_order": maworld_repair.get("work_order"),
                "repair_status": maworld_repair.get("status"),
                "selected_action": "MAWORLD_R52_EXISTING_REPAIR_RETURN_DISCOVERY_NO_RERUN",
                "stop_condition": "STOP_AT_FOUND_STRICT_BYTES_OR_CONFIRMED_MISSING_RETURN",
                "reason": "Physical initdb forensics passed, but the later repair was only user-reported done and its strict return bytes were missing; rerun or root-cause guessing is not authorized.",
            }
        )

    if (
        arena_current
        and arena_external
        and arena_external.get("status") == "VERIFIED_PASS"
        and arena_decision
        and arena_decision.get("human_ripe") is False
    ):
        candidates.append(
            {
                "rank": 3,
                "project": "Sovereign Arena",
                "gap_class": "SLOT_GATE_VS_LEDGER_RIPENESS_DIVERGENCE",
                "current_queue_rank": _queue_rank(queue, "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR"),
                "current_work_order": arena_current.get("work_order"),
                "external_status": arena_external.get("status"),
                "ledger_human_ripe": arena_decision.get("human_ripe"),
                "selected_action": "ARENA_GATE_COMPRESSION_RECONCILIATION_NO_HUMAN_PROMOTION",
                "stop_condition": "STOP_AFTER_EXPLAINING_SLOT_VS_LEDGER_GATE_STATE",
                "reason": "The slot reports HUMAN_GATE_READY while the Decision/Effect Ledger keeps the same R51 case human_ripe=false; no human promotion is allowed until that compression is reconciled.",
            }
        )

    candidates.sort(key=lambda item: int(item["rank"]))
    selected = candidates[0] if candidates else None

    return {
        "schema": SCHEMA,
        "projection_kind": PROJECTION_KIND,
        "observed_at": evidence.get("observed_at"),
        "authority_anchor": queue.get("authority_anchor"),
        "source_precedence": evidence.get("source_precedence"),
        "summary": {
            "candidate_count": len(candidates),
            "human_now_before": human_now_before,
            "human_now_after": human_now_before,
            "effect_candidates_before": effect_before,
            "effect_candidates_after": effect_before,
            "selected_project": selected.get("project") if selected else None,
            "selected_action": selected.get("selected_action") if selected else None,
        },
        "priority_candidates": candidates,
        "selected_next_action": selected,
        "invariants": {
            "current_queue_not_mutated": True,
            "current_lifecycle_not_mutated": True,
            "decision_ledger_not_mutated": True,
            "return_registry_not_mutated": True,
            "human_now_unchanged": True,
            "effect_candidates_unchanged": True,
            "verified_bundle_not_silently_promoted_to_semantic_acceptance": True,
            "user_reported_completion_not_physical_acceptance": True,
            "missing_return_never_authorizes_rerun": True,
            "exactly_one_next_bounded_action_selected": len(candidates) > 0,
        },
        "safety": safety(),
    }


def validate_projection(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if data.get("projection_kind") != PROJECTION_KIND:
        errors.append("projection_kind_mismatch")

    summary = data.get("summary", {})
    if summary.get("human_now_before") != summary.get("human_now_after"):
        errors.append("human_now_changed")
    if summary.get("effect_candidates_before") != summary.get("effect_candidates_after"):
        errors.append("effect_candidates_changed")

    candidates = data.get("priority_candidates", [])
    selected = data.get("selected_next_action")
    if candidates:
        if not selected:
            errors.append("selected_action_missing")
        elif selected != candidates[0]:
            errors.append("selected_action_not_first_candidate")
        if summary.get("selected_action") != candidates[0].get("selected_action"):
            errors.append("summary_selected_action_mismatch")
    elif selected is not None:
        errors.append("selected_action_present_without_candidates")

    if candidates:
        first = candidates[0]
        if first.get("project") != "ContinuityOS":
            errors.append("continuityos_source_gap_not_first")
        if first.get("gap_class") != "VERIFIED_NEWER_RETURN_NOT_BOUND_IN_CURRENT_TOP3_CHAIN":
            errors.append("continuityos_gap_class_mismatch")
        if first.get("selected_action") != "CONTINUITYOS_R52_EXISTING_RETURN_BINDING_RECONCILIATION":
            errors.append("continuityos_action_mismatch")

    for candidate in candidates:
        action = str(candidate.get("selected_action", ""))
        if any(token in action for token in ("DISPATCH", "DEPLOY", "APPLY", "SEND", "TRADE")):
            errors.append(f"forbidden_effect_action:{action}")

    inv = data.get("invariants", {})
    for key in (
        "current_queue_not_mutated",
        "current_lifecycle_not_mutated",
        "decision_ledger_not_mutated",
        "return_registry_not_mutated",
        "human_now_unchanged",
        "effect_candidates_unchanged",
        "verified_bundle_not_silently_promoted_to_semantic_acceptance",
        "user_reported_completion_not_physical_acceptance",
        "missing_return_never_authorizes_rerun",
        "exactly_one_next_bounded_action_selected",
    ):
        if inv.get(key) is not True:
            errors.append(f"invariant_not_true:{key}")

    safe = data.get("safety", {})
    for key in (
        "current_truth_mutation_authorized",
        "return_registry_mutation_authorized",
        "routing_mutation_authorized",
        "dispatch_authorized",
        "semantic_acceptance_authorized_by_projection",
        "apply_authorized",
        "execution_authorized",
        "deploy_authorized",
        "external_message_authorized",
        "can_trade",
        "self_application",
    ):
        if safe.get(key) is not False:
            errors.append(f"authority_leak:{key}")
    if safe.get("capital_permission") != "DENY":
        errors.append("capital_permission_not_deny")

    return errors


def serialize(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _minimal_queue() -> dict[str, Any]:
    return {
        "authority_anchor": {"generation": "R64", "status": "ACTIVE"},
        "human_now": [],
        "summary": {"effect_candidates": 0},
        "attention_routing": [
            {"rank": 1, "work_order": "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE"},
            {"rank": 2, "work_order": "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR"},
            {"rank": 3, "work_order": "CODEX01-R43-CONTINUITY-186-CLOSURE"},
        ],
    }


def _minimal_lifecycle() -> dict[str, Any]:
    return {
        "work_orders": [
            {"work_order": "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE"},
            {"work_order": "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR"},
            {"work_order": "CODEX01-R43-CONTINUITY-186-CLOSURE"},
        ]
    }


def _minimal_ledger() -> dict[str, Any]:
    return {
        "decisions": [
            {
                "work_order": "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR",
                "human_ripe": False,
            }
        ]
    }


def self_test() -> None:
    ev = load(EVIDENCE)
    built = build_projection(_minimal_queue(), _minimal_lifecycle(), _minimal_ledger(), {}, ev)
    assert validate_projection(built) == []
    assert built["summary"]["selected_project"] == "ContinuityOS"

    no_cont = copy.deepcopy(ev)
    for item in no_cont["top3_external_evidence"]:
        if item["work_order"] == "CODEX01-R52-CONTINUITYOS-CANONICAL-ADOPTION":
            item["status"] = "USER_REPORTED_DONE_RETURN_MISSING"
    built = build_projection(_minimal_queue(), _minimal_lifecycle(), _minimal_ledger(), {}, no_cont)
    assert built["summary"]["selected_project"] == "MAWorld"

    no_old = _minimal_lifecycle()
    no_old["work_orders"] = [
        {"work_order": "CODEX01-R52-CONTINUITYOS-CANONICAL-ADOPTION"},
        {"work_order": "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE"},
        {"work_order": "CODEX04-R51-SOVEREIGN-ARENA-TRUTH-REPAIR"},
    ]
    built = build_projection(_minimal_queue(), no_old, _minimal_ledger(), {}, ev)
    assert built["summary"]["selected_project"] == "MAWorld"

    no_ma = copy.deepcopy(ev)
    for item in no_ma["top3_external_evidence"]:
        if item["work_order"] == "CODEX03-R52-MAWORLD-INITDB-REPAIR":
            item["status"] = "VERIFIED_PASS"
    built = build_projection(_minimal_queue(), _minimal_lifecycle(), _minimal_ledger(), {}, no_ma)
    assert [x["project"] for x in built["priority_candidates"]] == ["ContinuityOS", "Sovereign Arena"]

    ripe_ledger = _minimal_ledger()
    ripe_ledger["decisions"][0]["human_ripe"] = True
    built = build_projection(_minimal_queue(), _minimal_lifecycle(), ripe_ledger, {}, ev)
    assert "Sovereign Arena" not in [x["project"] for x in built["priority_candidates"]]

    mutated = build_projection(_minimal_queue(), _minimal_lifecycle(), _minimal_ledger(), {}, ev)
    mutated["safety"]["dispatch_authorized"] = True
    assert "authority_leak:dispatch_authorized" in validate_projection(mutated)

    mutated = build_projection(_minimal_queue(), _minimal_lifecycle(), _minimal_ledger(), {}, ev)
    mutated["summary"]["human_now_after"] = 1
    assert "human_now_changed" in validate_projection(mutated)

    print("OPERATOR_PRIORITY_RECONCILIATION_ADVERSARIAL_TEST_PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    built = build_projection(load(QUEUE), load(LIFECYCLE), load(LEDGER), load(REGISTRY), load(EVIDENCE))
    errors = validate_projection(built)
    if errors:
        raise SystemExit(";".join(errors))

    if args.check:
        committed = load(OUTPUT)
        if committed != built:
            raise SystemExit("operator_priority_reconciliation_generated_mismatch")
        print("OPERATOR_PRIORITY_RECONCILIATION_VALIDATION_PASS")
        return 0

    OUTPUT.write_text(serialize(built), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
