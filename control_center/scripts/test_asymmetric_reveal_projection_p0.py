from __future__ import annotations

import copy
import unittest

from control_center.scripts.asymmetric_reveal_projection_p0 import (
    AsymmetricRevealProjectionError,
    build_asymmetric_reveal_projection,
    sha256_obj,
)


class AsymmetricRevealProjectionP0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.closure = {
            "schema": "bitevo.shadow_asymmetric_reveal_closure.v1",
            "case_id": "case-r6-001",
            "case_sha256": "1" * 64,
            "reveal_sha256": "2" * 64,
            "subject_manifest_sha256": "3" * 64,
            "domain_history_closure_sha256": "4" * 64,
            "asymmetric_approval_verification_sha256": "5" * 64,
            "challenge_id": "6" * 64,
            "human_subject_id": "robert",
            "session_id": "session-r6",
            "device_id": "device-r6",
            "custody_provider_id": "custody-r6",
            "credential_id_sha256": "7" * 64,
            "public_key_sha256": "8" * 64,
            "algorithm": "ED25519",
            "key_epoch": 3,
            "actual_choice": "LONG",
            "decided_at": "2026-08-20T03:05:00+07:00",
            "approved_reveal_intent_sha256": "9" * 64,
            "authentication_status": "ASYMMETRIC_CUSTODY_VERIFIED_SHADOW_ONLY",
            "human_identity_scope": "CREDENTIAL_SUBJECT_ASSERTION_ONLY",
            "cryptographic_property": "EXTERNAL_ASYMMETRIC_SIGNATURE_VERIFIER_ASSERTION",
            "local_signature_math_verified": False,
            "physical_human_presence_proven": False,
            "single_use_nonce_candidate_verified": True,
            "credential_epoch_verified": True,
            "current_truth_promotion_allowed": False,
            "history_write_performed": False,
            "human_gate_write_performed": False,
            "semantic_acceptance": "NOT_PERFORMED",
            "apply_allowed": False,
            "execution_authority": "NONE",
            "can_execute": False,
            "effects": {
                "human_gate_write": False,
                "credential_registry_write": False,
                "nonce_registry_write": False,
                "registry_write": False,
                "ledger_write": False,
                "return_index_write": False,
                "current_truth_apply": False,
                "runtime_activation": False,
                "executor_dispatch": False,
                "signal": False,
                "order": False,
                "capital_effect": False,
            },
            "safety": {
                "mode": "SHADOW",
                "execution_authority": "NONE",
                "can_trade": False,
                "capital_permission": "DENY",
                "orders_allowed": False,
                "signals_allowed": False,
            },
            "generated_at": "2026-08-20T03:15:00+07:00",
        }
        self.closure["asymmetric_reveal_closure_sha256"] = sha256_obj(self.closure)

    def test_valid_closure_projects_read_only_asymmetric_state(self):
        projection = build_asymmetric_reveal_projection(self.closure)
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_ASYMMETRIC_REVEAL_PROJECTION")
        self.assertEqual(projection["asymmetric_custody"], "VERIFIED_BY_EXTERNAL_ASYMMETRIC_VERIFIER_SHADOW_ONLY")
        self.assertEqual(projection["local_signature_math"], "NOT_VERIFIED_HERE")
        self.assertEqual(projection["physical_human_presence"], "NOT_PROVEN")
        self.assertFalse(projection["apply"])
        self.assertTrue(all(value is False for value in projection["mutations"].values()))
        self.assertEqual(projection["effect_candidates_created"], 0)
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertEqual(projection["safety"]["capital_permission"], "DENY")

    def test_local_signature_math_overclaim_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["local_signature_math_verified"] = True
        closure["asymmetric_reveal_closure_sha256"] = sha256_obj({k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"})
        with self.assertRaisesRegex(AsymmetricRevealProjectionError, "asymmetric_reveal_local_crypto_overclaim"):
            build_asymmetric_reveal_projection(closure)

    def test_physical_presence_overclaim_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["physical_human_presence_proven"] = True
        closure["asymmetric_reveal_closure_sha256"] = sha256_obj({k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"})
        with self.assertRaisesRegex(AsymmetricRevealProjectionError, "asymmetric_reveal_physical_presence_overclaim"):
            build_asymmetric_reveal_projection(closure)

    def test_nonce_guard_is_required(self):
        closure = copy.deepcopy(self.closure)
        closure["single_use_nonce_candidate_verified"] = False
        closure["asymmetric_reveal_closure_sha256"] = sha256_obj({k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"})
        with self.assertRaisesRegex(AsymmetricRevealProjectionError, "asymmetric_reveal_nonce_guard_missing"):
            build_asymmetric_reveal_projection(closure)

    def test_current_truth_promotion_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["current_truth_promotion_allowed"] = True
        closure["asymmetric_reveal_closure_sha256"] = sha256_obj({k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"})
        with self.assertRaisesRegex(AsymmetricRevealProjectionError, "asymmetric_reveal_current_truth_promotion_forbidden"):
            build_asymmetric_reveal_projection(closure)

    def test_effect_smuggling_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["effects"]["credential_registry_write"] = True
        closure["asymmetric_reveal_closure_sha256"] = sha256_obj({k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"})
        with self.assertRaisesRegex(AsymmetricRevealProjectionError, "asymmetric_reveal_effect_boundary_breached"):
            build_asymmetric_reveal_projection(closure)


if __name__ == "__main__":
    unittest.main()
