from __future__ import annotations

import unittest

from hanri.decision_governor_pilot import build_decision_governor_pilot


class DecisionGovernorPilotTests(unittest.TestCase):
    def _pointer(self) -> dict[str, object]:
        return {
            "canonical_activation": {
                "status": "ACTIVE",
                "decision": "ACCEPT_R64_POINTER_PROMOTION",
            },
            "effect_ceiling": {
                "auto_accept": False,
                "auto_dispatch": False,
                "can_trade": False,
                "capital_permission": "DENY",
                "deploy": "DENY",
                "external_messages": "DENY_WITHOUT_EXACT_SEPARATE_HUMAN_AUTHORIZATION",
                "self_application": False,
            },
        }

    def _state(self) -> dict[str, object]:
        return {
            "canonicality_activation": "CANDIDATE_NOT_ACTIVE_PENDING_ROBERT",
            "active_policy_constraints": {
                "CONTROL_FREEZE": "ACTIVE",
                "NO_FURTHER_AGENT_WORK": True,
            },
            "global_effect_ceiling": {
                "auto_accept": False,
                "auto_dispatch": False,
                "can_trade": False,
                "capital_permission": "DENY",
                "deploy": "DENY",
                "self_application": False,
            },
            "p0_security": {"status": "3_ITEMS_OPEN_NO_CLOSURE_RECEIPTS"},
        }

    def _roles(self) -> dict[str, object]:
        return {
            "roles": {
                "CLAUDE-BITUNIX": {
                    "state": "GEN003_UNREGISTERED_PENDING_D1; observation waits dispatch"
                }
            }
        }

    def _queue(self) -> str:
        return """
## D1 — Register slot
## D2 — Decision intake
## D3 — CONTROL_FREEZE
## D4 — P0 closure window
## D5 — Roman pilot outreach
"""

    def _digest(self) -> str:
        return """
- Ожидают решения Роберта: **0**
- `C-23d1b14c602d7564762c` → **ACCEPT**
- `C-537663b99e7ff9c862a5` → **REJECT**
"""

    def test_live_like_case_reconciles_stale_markers_and_emits_exact_three(self) -> None:
        result = build_decision_governor_pilot(
            self._pointer(), self._state(), self._roles(), self._queue(), self._digest()
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["decision_count"], 3)
        self.assertEqual(
            [item["decision_id"] for item in result["decisions"]],
            [
                "D4_P0_SECURITY_CLOSURE_WINDOW",
                "D1_REGISTER_CLAUDE_BITUNIX_BROKER_SLOT",
                "D5_ROMAN_PILOT_OUTREACH",
            ],
        )
        reconciliation = result["source_reconciliation"]
        self.assertFalse(reconciliation["r64_pointer_promotion_pending"])
        self.assertTrue(reconciliation["r64_state_candidate_marker_superseded"])
        self.assertFalse(reconciliation["d2_df1_pending"])
        self.assertTrue(reconciliation["d2_df1_resolved_by_later_digest"])
        self.assertFalse(reconciliation["d3_control_freeze_pending"])
        self.assertTrue(reconciliation["d3_control_freeze_active"])

    def test_no_card_can_grant_effect_authority(self) -> None:
        result = build_decision_governor_pilot(
            self._pointer(), self._state(), self._roles(), self._queue(), self._digest()
        )
        self.assertFalse(result["global_effect_ceiling"]["auto_accept"])
        self.assertFalse(result["global_effect_ceiling"]["auto_dispatch"])
        self.assertFalse(result["global_effect_ceiling"]["can_trade"])
        self.assertEqual(result["global_effect_ceiling"]["capital_permission"], "DENY")
        self.assertFalse(result["global_effect_ceiling"]["self_application"])
        self.assertEqual(result["pilot_effects"]["drive_writes"], 0)
        self.assertEqual(result["pilot_effects"]["external_messages"], 0)
        for card in result["decisions"]:
            self.assertEqual(card["status"], "HUMAN_DECISION_REQUIRED")
            self.assertEqual(card["authority_owner"], "ROBERT")

    def test_d1_requires_broker_path_not_direct_registry_edit(self) -> None:
        result = build_decision_governor_pilot(
            self._pointer(), self._state(), self._roles(), self._queue(), self._digest()
        )
        card = next(item for item in result["decisions"] if item["decision_id"].startswith("D1_"))
        self.assertIn("broker-owned mutation path", card["minimal_effect_if_approved"])
        self.assertIn("Do not edit CURRENT_RETURN_REGISTRY.json directly", card["minimal_effect_if_approved"])
        self.assertIn("DIRECT_REGISTRY_EDIT", card["blocked_effects"])

    def test_d5_never_sends_without_exact_human_choice(self) -> None:
        result = build_decision_governor_pilot(
            self._pointer(), self._state(), self._roles(), self._queue(), self._digest()
        )
        card = next(item for item in result["decisions"] if item["decision_id"].startswith("D5_"))
        self.assertEqual(card["human_choices"], ["SEND", "REVISE", "HOLD"])
        self.assertIn("SEND_WITHOUT_EXACT_APPROVAL", card["blocked_effects"])
        self.assertEqual(result["pilot_effects"]["external_messages"], 0)

    def test_missing_later_d2_evidence_fails_closed(self) -> None:
        result = build_decision_governor_pilot(
            self._pointer(), self._state(), self._roles(), self._queue(), "pending unknown"
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("D2_LATER_DECISION_EVIDENCE_MISSING", result["failures"])

    def test_inactive_pointer_fails_closed_instead_of_promoting_state(self) -> None:
        pointer = self._pointer()
        pointer["canonical_activation"] = {"status": "PENDING", "decision": "NONE"}
        result = build_decision_governor_pilot(
            pointer, self._state(), self._roles(), self._queue(), self._digest()
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("R64_POINTER_NOT_ACTIVE", result["failures"])


if __name__ == "__main__":
    unittest.main()
