from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

PILOT_VERSION = "decision-governor-pilot-01"
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _has_section(text: str, decision_id: str) -> bool:
    return f"## {decision_id} " in text or f"## {decision_id}—" in text or f"## {decision_id} —" in text


def _global_blocks(pointer: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    ceiling = pointer.get("effect_ceiling") if isinstance(pointer.get("effect_ceiling"), dict) else {}
    state_ceiling = state.get("global_effect_ceiling") if isinstance(state.get("global_effect_ceiling"), dict) else {}
    merged = dict(state_ceiling)
    merged.update(ceiling)
    return {
        "auto_accept": bool(merged.get("auto_accept", False)),
        "auto_dispatch": bool(merged.get("auto_dispatch", False)),
        "can_trade": bool(merged.get("can_trade", False)),
        "capital_permission": str(merged.get("capital_permission", "DENY")),
        "deploy": str(merged.get("deploy", "DENY")),
        "external_messages": str(merged.get("external_messages", "DENY")),
        "self_application": bool(merged.get("self_application", False)),
    }


def _reconciliation(pointer: Mapping[str, Any], state: Mapping[str, Any], digest_text: str) -> dict[str, Any]:
    activation = pointer.get("canonical_activation") if isinstance(pointer.get("canonical_activation"), dict) else {}
    pointer_active = activation.get("status") == "ACTIVE" and activation.get("decision") == "ACCEPT_R64_POINTER_PROMOTION"
    state_candidate_marker = state.get("canonicality_activation") == "CANDIDATE_NOT_ACTIVE_PENDING_ROBERT"
    d2_decided = (
        "Ожидают решения Роберта: **0**" in digest_text
        and "C-23d1b14c602d7564762c` → **ACCEPT**" in digest_text
        and "C-537663b99e7ff9c862a5` → **REJECT**" in digest_text
    )
    policy = state.get("active_policy_constraints") if isinstance(state.get("active_policy_constraints"), dict) else {}
    d3_active = policy.get("CONTROL_FREEZE") == "ACTIVE"
    return {
        "r64_pointer_promotion_pending": not pointer_active,
        "r64_state_candidate_marker_superseded": bool(pointer_active and state_candidate_marker),
        "r64_state_bytes_must_remain_immutable": bool(pointer_active and state_candidate_marker),
        "d2_df1_pending": not d2_decided,
        "d2_df1_resolved_by_later_digest": d2_decided,
        "d3_control_freeze_pending": not d3_active,
        "d3_control_freeze_active": d3_active,
    }


def _card(
    *,
    decision_id: str,
    severity: str,
    causal_interpretation: str,
    evidence_refs: list[str],
    authority_owner: str,
    human_choices: list[str],
    recommended_choice: str,
    minimal_effect_if_approved: str,
    independent_readback: str,
    blocked_effects: list[str],
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "status": "HUMAN_DECISION_REQUIRED",
        "severity": severity,
        "causal_interpretation": causal_interpretation,
        "evidence_refs": evidence_refs,
        "authority_owner": authority_owner,
        "human_choices": human_choices,
        "recommended_choice": recommended_choice,
        "minimal_effect_if_approved": minimal_effect_if_approved,
        "independent_readback_required": independent_readback,
        "blocked_effects": blocked_effects,
    }


def build_decision_governor_pilot(
    pointer: Mapping[str, Any],
    state: Mapping[str, Any],
    role_views: Mapping[str, Any],
    decision_queue_text: str,
    r28_digest_text: str,
) -> dict[str, Any]:
    reconciliation = _reconciliation(pointer, state, r28_digest_text)
    blocks = _global_blocks(pointer, state)

    cards: list[dict[str, Any]] = []
    p0 = state.get("p0_security") if isinstance(state.get("p0_security"), dict) else {}
    if _has_section(decision_queue_text, "D4") and p0.get("status") == "3_ITEMS_OPEN_NO_CLOSURE_RECEIPTS":
        cards.append(_card(
            decision_id="D4_P0_SECURITY_CLOSURE_WINDOW",
            severity="CRITICAL",
            causal_interpretation=(
                "Three P0 security items remain open without closure receipts. The current control policy says P0 work "
                "outranks control/meta work, so production-qualified security claims and effect expansion remain bounded."
            ),
            evidence_refs=["CURRENT_STATE.json#/p0_security", "R63_PENDING_HUMAN_DECISIONS.md#D4"],
            authority_owner="ROBERT",
            human_choices=["ACCEPT", "REVISE", "HOLD", "REJECT"],
            recommended_choice="ACCEPT",
            minimal_effect_if_approved=(
                "Authorize one bounded defensive closure window and one named executor; require a separate closure receipt "
                "for each P0 item. No unrelated deployment or authority change."
            ),
            independent_readback=(
                "Verify each P0 receipt against the target system/provider state before changing the P0 register or any production claim."
            ),
            blocked_effects=["AUTO_EXECUTION", "DEPLOYMENT_EXPANSION", "TRADING", "CAPITAL_USE"],
        ))

    roles = role_views.get("roles") if isinstance(role_views.get("roles"), dict) else {}
    claude = roles.get("CLAUDE-BITUNIX") if isinstance(roles.get("CLAUDE-BITUNIX"), dict) else {}
    if _has_section(decision_queue_text, "D1") and "UNREGISTERED_PENDING_D1" in str(claude.get("state", "")):
        cards.append(_card(
            decision_id="D1_REGISTER_CLAUDE_BITUNIX_BROKER_SLOT",
            severity="HIGH",
            causal_interpretation=(
                "A verified return lane is still marked unregistered. Without a broker-owned slot, the harvester can miss "
                "that lane silently even when return bytes already exist."
            ),
            evidence_refs=["ROLE_VIEWS.json#/roles/CLAUDE-BITUNIX", "R63_PENDING_HUMAN_DECISIONS.md#D1"],
            authority_owner="ROBERT",
            human_choices=["ACCEPT", "REVISE", "HOLD", "REJECT"],
            recommended_choice="ACCEPT",
            minimal_effect_if_approved=(
                "Authorize the controller to request exactly one CLAUDE-BITUNIX slot through the broker-owned mutation path. "
                "Do not edit CURRENT_RETURN_REGISTRY.json directly."
            ),
            independent_readback=(
                "Next broker/harvest readback must show the slot and the expected GEN003 pickup/registration before completion is declared."
            ),
            blocked_effects=["DIRECT_REGISTRY_EDIT", "AUTO_DISPATCH", "TRADING", "CAPITAL_USE"],
        ))

    if _has_section(decision_queue_text, "D5"):
        cards.append(_card(
            decision_id="D5_ROMAN_PILOT_OUTREACH",
            severity="MEDIUM",
            causal_interpretation=(
                "The outreach is the current queue item most directly capable of creating external product evidence, but "
                "external messaging remains separately human-gated and a draft is not authorization to send."
            ),
            evidence_refs=["R63_PENDING_HUMAN_DECISIONS.md#D5", "CURRENT_POINTER.json#/effect_ceiling/external_messages"],
            authority_owner="ROBERT",
            human_choices=["SEND", "REVISE", "HOLD"],
            recommended_choice="REVISE",
            minimal_effect_if_approved=(
                "After exact message review, authorize one bounded send to the intended recipient only. No follow-up automation or broader outreach."
            ),
            independent_readback=(
                "Require provider/message readback for the exact sent body and recipient; recipient response or refusal becomes external evidence."
            ),
            blocked_effects=["SEND_WITHOUT_EXACT_APPROVAL", "BULK_OUTREACH", "AUTO_FOLLOWUP", "TRADING", "CAPITAL_USE"],
        ))

    cards.sort(key=lambda item: (SEVERITY_ORDER.get(str(item["severity"]), 99), str(item["decision_id"])))
    cards = cards[:3]

    failures: list[str] = []
    if reconciliation["r64_pointer_promotion_pending"]:
        failures.append("R64_POINTER_NOT_ACTIVE")
    if reconciliation["d2_df1_pending"]:
        failures.append("D2_LATER_DECISION_EVIDENCE_MISSING")
    if reconciliation["d3_control_freeze_pending"]:
        failures.append("D3_CONTROL_FREEZE_NOT_ACTIVE")
    if len(cards) == 0:
        failures.append("NO_ACTIONABLE_DECISION_CARDS")
    if len(cards) > 3:
        failures.append("DECISION_CARD_LIMIT_EXCEEDED")
    if blocks["can_trade"] is not False or blocks["capital_permission"] != "DENY" or blocks["self_application"] is not False:
        failures.append("SAFETY_CEILING_MISMATCH")

    return {
        "schema_version": 1,
        "pilot_version": PILOT_VERSION,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "product_delta": "CONTROL_CENTER_EVIDENCE_TO_MAX_THREE_HUMAN_DECISION_CARDS",
        "source_reconciliation": reconciliation,
        "decision_count": len(cards),
        "decisions": cards,
        "global_effect_ceiling": blocks,
        "pilot_effects": {
            "drive_writes": 0,
            "external_model_api_calls": 0,
            "external_messages": 0,
            "scheduler_changes": 0,
            "source_repository_writes_at_runtime": False,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only HANRI Decision Governor Pilot 01")
    parser.add_argument("--current-pointer", type=Path, required=True)
    parser.add_argument("--current-state", type=Path, required=True)
    parser.add_argument("--role-views", type=Path, required=True)
    parser.add_argument("--decision-queue", type=Path, required=True)
    parser.add_argument("--r28-digest", type=Path, required=True)
    args = parser.parse_args(argv)

    result = build_decision_governor_pilot(
        _load_json(args.current_pointer),
        _load_json(args.current_state),
        _load_json(args.role_views),
        args.decision_queue.read_text(encoding="utf-8-sig"),
        args.r28_digest.read_text(encoding="utf-8-sig"),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
