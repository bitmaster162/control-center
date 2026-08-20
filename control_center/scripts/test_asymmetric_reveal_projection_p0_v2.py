from __future__ import annotations

import copy
import unittest

from control_center.scripts.asymmetric_reveal_projection_p0_v2 import (
    AsymmetricRevealProjectionV2Error,
    build_asymmetric_reveal_projection_v2,
    sha256_obj,
)

EXTERNAL_ASSERTION = "a" * 64


class AsymmetricRevealProjectionV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.closure = {
            "schema": "bitevo.shadow_asymmetric_reveal_closure.v2",
            "case_id": "case-r6-v2",
            "case_sha256": "1" * 64,
            "reveal_sha256": "2" * 64,
            "subject_manifest_sha256": "3" * 64,
            "domain_history_closure_sha256": "4" * 64,
            "prior_asymmetric_reveal_closure_sha256": "5" * 64,
            "asymmetric_approval_verification_sha256": "6" * 64,
            "external_assertion_sha256": EXTERNAL_ASSERTION,
            "external_assertion_digest_consumed": True,
            "trust_upgrade": "INDEPENDENT_ASSERTION_AND_APPROVAL_DIGESTS_BOUND",
            "challenge_id": "7" * 64,
            "human_subject_id": "robert",
            "session_id": "session-r6-v2",
            "device_id": "device-r6-v2",
            "custody_provider_id": "custody-r6-v2",
            "credential_id_sha256": "8" * 64,
            "public_key_sha256": "9" * 64,
            "algorithm": "ED25519",
            "key_epoch": 4,
            "actual_choice": "LONG",
            "decided_at": "2026-08-20T03:25:00+07:00",
            "approved_reveal_intent_sha256": "b" * 64,
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
            "generated_at": "2026-08-20T03:28:00+07:00",
        }
        self.closure["asymmetric_reveal_closure_sha256"] = sha256_obj(self.closure)

    def build(self, closure=None, **overrides):
        closure = self.closure if closure is None else closure
        return build_asymmetric_reveal_projection_v2(
            closure,
            expected_closure_sha256=overrides.pop("expected_closure", closure["asymmetric_reveal_closure_sha256"]),
            expected_external_assertion_sha256=overrides.pop("expected_assertion", EXTERNAL_ASSERTION),
            **overrides,
        )

    @staticmethod
    def rehash(closure):
        closure["asymmetric_reveal_closure_sha256"] = sha256_obj(
            {k: v for k, v in closure.items() if k != "asymmetric_reveal_closure_sha256"}
        )
        return closure

    def test_valid_v2_closure_projects_non_authority_state(self):
        projection = self.build()
        self.assertEqual(projection["schema"], "control_center.shadow_asymmetric_reveal_projection.v2")
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_ASYMMETRIC_REVEAL_PROJECTION_V2")
        self.assertEqual(projection["external_assertion_sha256"], EXTERNAL_ASSERTION)
        self.assertTrue(projection["external_assertion_digest_consumed"])
        self.assertFalse(projection["apply"])
        self.assertTrue(all(value is False for value in projection["mutations"].values()))
        self.assertEqual(projection["effect_candidates_created"], 0)
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertEqual(projection["safety"]["capital_permission"], "DENY")

    def test_wrong_retained_assertion_digest_is_rejected(self):
        with self.assertRaisesRegex(AsymmetricRevealProjectionV2Error, "asymmetric_reveal_v2_external_assertion_digest_mismatch"):
            self.build(expected_assertion="0" * 64)

    def test_missing_assertion_digest_guard_is_rejected_even_if_rehashed(self):
        closure = copy.deepcopy(self.closure)
        closure["external_assertion_digest_consumed"] = False
        closure = self.rehash(closure)
        with self.assertRaisesRegex(AsymmetricRevealProjectionV2Error, "asymmetric_reveal_v2_assertion_guard_missing"):
            self.build(closure, expected_closure=closure["asymmetric_reveal_closure_sha256"])

    def test_local_signature_math_overclaim_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["local_signature_math_verified"] = True
        closure = self.rehash(closure)
        with self.assertRaisesRegex(AsymmetricRevealProjectionV2Error, "asymmetric_reveal_v2_local_crypto_overclaim"):
            self.build(closure, expected_closure=closure["asymmetric_reveal_closure_sha256"])

    def test_physical_presence_overclaim_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["physical_human_presence_proven"] = True
        closure = self.rehash(closure)
        with self.assertRaisesRegex(AsymmetricRevealProjectionV2Error, "asymmetric_reveal_v2_physical_presence_overclaim"):
            self.build(closure, expected_closure=closure["asymmetric_reveal_closure_sha256"])

    def test_effect_smuggling_is_rejected(self):
        closure = copy.deepcopy(self.closure)
        closure["effects"]["human_gate_write"] = True
        closure = self.rehash(closure)
        with self.assertRaisesRegex(AsymmetricRevealProjectionV2Error, "asymmetric_reveal_v2_effect_boundary_breached"):
            self.build(closure, expected_closure=closure["asymmetric_reveal_closure_sha256"])


if __name__ == "__main__":
    unittest.main()
