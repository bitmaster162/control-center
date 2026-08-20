from __future__ import annotations

import copy
import unittest

from control_center.scripts.unified_shadow_projection_p0 import (
    ShadowProjectionError,
    build_unified_shadow_projection,
    sha256_obj,
    validate_unified_shadow_transaction,
)


class UnifiedShadowProjectionP0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tx = {
            "schema": "bitevo.unified_shadow_transaction.v2",
            "frozen_at": "2026-08-19T16:32:00Z",
            "case_id": "trade-control-001",
            "trade_case_sha256": "a" * 64,
            "decision_packet_sha256": "b" * 64,
            "federation_sha256": "c" * 64,
            "route_sha256": "d" * 64,
            "control_plane_sha256": "e" * 64,
            "registered_node_count": 63,
            "system_recommendation": "WAIT",
            "control_gate": "HOLD",
            "control_plane_action": "WAIT",
            "hanri_freshness": "STALE",
            "hanri_attention_required": True,
            "twin_prediction_status": "UNIQUE",
            "divergence": True,
            "effect_boundary": {
                "executor_enabled": False,
                "current_truth_apply": False,
                "continuity_write": False,
                "runtime_registration": False,
                "external_model_call": False,
                "exchange_call": False,
                "signal": False,
                "order": False,
                "credential_mutation": False,
                "merge": False,
                "deploy": False,
            },
            "semantics": {
                "one_transaction_one_case": True,
                "route_federation_and_control_are_hash_bound": True,
                "prediction_is_not_permission": True,
                "federation_accounting_is_not_runtime_invocation": True,
                "shadow_projection_is_not_current_truth": True,
                "stale_control_evidence_can_block_without_mutation": True,
            },
            "safety": {
                "mode": "SHADOW",
                "execution_authority": "NONE",
                "can_trade": False,
                "capital_permission": "DENY",
                "orders_allowed": False,
                "signals_allowed": False,
            },
        }
        self.tx["transaction_sha256"] = sha256_obj(self.tx)

    def test_valid_stale_transaction_projects_hold_without_apply(self) -> None:
        errors = validate_unified_shadow_transaction(self.tx)
        self.assertEqual(errors, [])
        projection = build_unified_shadow_projection(self.tx)
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_SHADOW_PROJECTION")
        self.assertEqual(projection["decision_view"]["disposition"], "HOLD_NO_APPLY")
        self.assertEqual(projection["decision_view"]["control_plane_action"], "WAIT")
        self.assertFalse(projection["apply"])
        self.assertFalse(projection["mutations"]["current_truth"])
        self.assertFalse(projection["mutations"]["runtime"])
        self.assertFalse(projection["mutations"]["trading"])
        self.assertFalse(projection["mutations"]["capital"])
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertEqual(projection["safety"]["capital_permission"], "DENY")

    def test_stale_freshness_cannot_pass_shadow(self) -> None:
        tx = copy.deepcopy(self.tx)
        tx["control_gate"] = "PASS_SHADOW"
        tx["transaction_sha256"] = sha256_obj({k: v for k, v in tx.items() if k != "transaction_sha256"})
        errors = validate_unified_shadow_transaction(tx)
        self.assertIn("stale_freshness_must_hold", errors)
        with self.assertRaises(ShadowProjectionError):
            build_unified_shadow_projection(tx)

    def test_attention_cannot_pass_shadow(self) -> None:
        tx = copy.deepcopy(self.tx)
        tx["hanri_freshness"] = "FRESH"
        tx["control_gate"] = "PASS_SHADOW"
        tx["control_plane_action"] = "WAIT"
        tx["transaction_sha256"] = sha256_obj({k: v for k, v in tx.items() if k != "transaction_sha256"})
        errors = validate_unified_shadow_transaction(tx)
        self.assertIn("attention_requires_hold", errors)

    def test_effect_boundary_breach_is_rejected(self) -> None:
        tx = copy.deepcopy(self.tx)
        tx["effect_boundary"]["current_truth_apply"] = True
        tx["transaction_sha256"] = sha256_obj({k: v for k, v in tx.items() if k != "transaction_sha256"})
        errors = validate_unified_shadow_transaction(tx)
        self.assertIn("effect_boundary_not_false:current_truth_apply", errors)

    def test_hold_requires_wait(self) -> None:
        tx = copy.deepcopy(self.tx)
        tx["control_plane_action"] = "LONG"
        tx["transaction_sha256"] = sha256_obj({k: v for k, v in tx.items() if k != "transaction_sha256"})
        errors = validate_unified_shadow_transaction(tx)
        self.assertIn("hold_must_force_wait", errors)

    def test_tampered_transaction_hash_is_rejected(self) -> None:
        tx = copy.deepcopy(self.tx)
        tx["system_recommendation"] = "LONG"
        errors = validate_unified_shadow_transaction(tx)
        self.assertIn("transaction_hash_mismatch", errors)

    def test_projection_is_deterministic(self) -> None:
        first = build_unified_shadow_projection(self.tx)
        second = build_unified_shadow_projection(self.tx)
        self.assertEqual(first, second)
        self.assertEqual(first["projection_sha256"], second["projection_sha256"])


if __name__ == "__main__":
    unittest.main()
