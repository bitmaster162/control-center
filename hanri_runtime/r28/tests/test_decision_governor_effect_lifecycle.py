from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hanri.decision_governor_effect_lifecycle import P0_REQUIREMENTS, build_effect_lifecycle_governor


class DecisionGovernorEffectLifecycleTests(unittest.TestCase):
    def _pointer(self) -> dict[str, object]:
        return {
            "canonical_activation": {"status": "ACTIVE", "decision": "ACCEPT_R64_POINTER_PROMOTION"},
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
            "active_policy_constraints": {"CONTROL_FREEZE": "ACTIVE", "NO_FURTHER_AGENT_WORK": True},
            "global_effect_ceiling": {"can_trade": False, "capital_permission": "DENY", "self_application": False},
            "p0_security": {"status": "3_ITEMS_OPEN_NO_CLOSURE_RECEIPTS"},
        }

    def _roles(self) -> dict[str, object]:
        return {"roles": {"CLAUDE-BITUNIX": {"state": "GEN003_UNREGISTERED_PENDING_D1"}}}

    def _queue(self) -> str:
        return "## D1 — Register slot\n## D4 — P0 closure window\n## D5 — Roman pilot outreach\n"

    def _digest(self) -> str:
        return "- Ожидают решения Роберта: **0**\n- `C-23d1b14c602d7564762c` → **ACCEPT**\n- `C-537663b99e7ff9c862a5` → **REJECT**\n"

    def _write_receipt(self, root: Path, p0_id: str, *, complete: bool = True, safety_ok: bool = True) -> None:
        evidence = {key: f"proof:{key}" for key in P0_REQUIREMENTS[p0_id]}
        if not complete:
            evidence[next(iter(P0_REQUIREMENTS[p0_id]))] = None
        payload = {
            "schema": "control_canter.p0_closure_receipt.v1",
            "p0_id": p0_id,
            "status": "CLOSED" if complete else "OPEN",
            "item": p0_id,
            "closed_by": "ROBERT" if complete else None,
            "closed_at_utc": "2026-08-11T06:00:00Z" if complete else None,
            "required_evidence": evidence,
            "off_host_negative_test_attached": complete,
            "can_trade": False if safety_ok else True,
            "capital_permission": "DENY",
        }
        (root / f"{p0_id}_CLOSURE.json").write_text(json.dumps(payload), encoding="utf-8")

    def _build(self, receipts: Path, accepted: set[str] | None = None) -> dict[str, object]:
        return build_effect_lifecycle_governor(
            self._pointer(), self._state(), self._roles(), self._queue(), self._digest(),
            receipts_dir=receipts, accepted_decisions=accepted or set(),
        )

    def test_no_receipts_focuses_first_open_p0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._build(Path(tmp), {"D4"})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["p0_effect_lifecycle"]["first_incomplete"], "P0-1")
        self.assertFalse(result["p0_effect_lifecycle"]["all_closed"])
        d4 = next(card for card in result["decisions"] if card["decision_id"].startswith("D4_"))
        self.assertEqual(d4["status"], "EFFECT_READBACK_REQUIRED")
        self.assertIn("P0-1", d4["causal_interpretation"])

    def test_complete_p0_1_advances_focus_to_p0_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_receipt(root, "P0-1")
            result = self._build(root, {"D4"})
        self.assertEqual(result["p0_effect_lifecycle"]["first_incomplete"], "P0-2")
        first = result["p0_effect_lifecycle"]["items"][0]
        self.assertEqual(first["status"], "RECEIPTED_CLOSED")

    def test_all_receipts_closed_suppresses_d4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p0_id in P0_REQUIREMENTS:
                self._write_receipt(root, p0_id)
            result = self._build(root, {"D4"})
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["p0_effect_lifecycle"]["all_closed"])
        self.assertEqual(result["decision_count"], 2)
        self.assertNotIn("D4_P0_SECURITY_CLOSURE_WINDOW", [x["decision_id"] for x in result["decisions"]])

    def test_partial_receipt_never_closes_item(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_receipt(root, "P0-1", complete=False)
            result = self._build(root, {"D4"})
        first = result["p0_effect_lifecycle"]["items"][0]
        self.assertEqual(first["status"], "VERIFIED_PARTIAL")
        self.assertTrue(first["missing_evidence"])

    def test_receipt_safety_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_receipt(root, "P0-1", safety_ok=False)
            result = self._build(root, {"D4"})
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("P0-1:SAFETY_CEILING_MISMATCH", result["failures"])


if __name__ == "__main__":
    unittest.main()
