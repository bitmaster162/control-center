from __future__ import annotations

import unittest

from control_center.scripts.human_approval_custody_p0 import build_human_approval_challenge
from control_center.scripts.human_asymmetric_custody_p0 import (
    ASYMMETRIC_ASSERTION_SCHEMA,
    HumanAsymmetricCustodyError,
    build_human_credential_registry_snapshot,
    build_nonce_epoch_registry_snapshot,
    sha256_obj,
)
from control_center.scripts.human_asymmetric_custody_p0_v2 import verify_asymmetric_human_approval_v2

ROOT = "1" * 64
CREDENTIAL_ID = "5" * 64
PUBLIC_KEY_SHA = "6" * 64


class HumanAsymmetricCustodyV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.challenge = build_human_approval_challenge(
            case_id="case-r6-v2",
            case_sha256="2" * 64,
            packet_sha256="3" * 64,
            twin_prediction_id="4" * 64,
            options=("LONG", "SHORT", "WAIT"),
            human_subject_id="robert",
            session_id="session-r6-v2",
            device_id="device-r6-v2",
            custody_provider_id="custody-r6-v2",
            nonce="nonce-r6-v2-unique",
            issued_at="2026-08-20T03:20:00+07:00",
            expires_at="2026-08-20T03:30:00+07:00",
        )
        self.credentials = build_human_credential_registry_snapshot(
            registry_id="credentials-r6-v2",
            authority_root_sha256=ROOT,
            entries=(
                {
                    "human_subject_id": "robert",
                    "device_id": "device-r6-v2",
                    "custody_provider_id": "custody-r6-v2",
                    "credential_id_sha256": CREDENTIAL_ID,
                    "public_key_sha256": PUBLIC_KEY_SHA,
                    "algorithm": "ED25519",
                    "key_epoch": 4,
                    "status": "ACTIVE",
                    "not_before": "2026-08-20T00:00:00+07:00",
                    "not_after": "2026-08-21T00:00:00+07:00",
                    "revoked_at": None,
                    "counter_supported": True,
                    "sign_count": 9,
                },
            ),
        )
        self.nonces = build_nonce_epoch_registry_snapshot(
            registry_id="nonces-r6-v2",
            authority_root_sha256=ROOT,
            epoch_number=20,
            epoch_started_at="2026-08-20T00:00:00+07:00",
            epoch_expires_at="2026-08-21T00:00:00+07:00",
            previous_epoch_sha256="8" * 64,
        )
        self.assertion = {
            "schema": ASYMMETRIC_ASSERTION_SCHEMA,
            "challenge_id": self.challenge["challenge_id"],
            "challenge_sha256": self.challenge["challenge_sha256"],
            "case_id": self.challenge["case_id"],
            "case_sha256": self.challenge["case_sha256"],
            "packet_sha256": self.challenge["packet_sha256"],
            "twin_prediction_id": self.challenge["twin_prediction_id"],
            "human_subject_id": "robert",
            "session_id": "session-r6-v2",
            "device_id": "device-r6-v2",
            "custody_provider_id": "custody-r6-v2",
            "nonce": "nonce-r6-v2-unique",
            "credential_id_sha256": CREDENTIAL_ID,
            "public_key_sha256": PUBLIC_KEY_SHA,
            "algorithm": "ED25519",
            "key_epoch": 4,
            "signature_sha256": "7" * 64,
            "verifier_id": "external-webauthn-verifier",
            "verifier_key_id": "external-verifier-key-04",
            "origin": "https://control.example.invalid",
            "rp_id": "control.example.invalid",
            "actual_choice": "LONG",
            "responded_at": "2026-08-20T03:25:00+07:00",
            "signature_verified": True,
            "external_asymmetric_verifier_assertion": True,
            "local_signature_math_verified": False,
            "user_present": True,
            "user_verified": True,
            "physical_human_presence_proven": False,
            "counter_supported": True,
            "sign_count_before": 9,
            "sign_count_after": 10,
            "execution_authority": "NONE",
            "can_execute": False,
            "safety": {
                "mode": "SHADOW",
                "execution_authority": "NONE",
                "can_trade": False,
                "capital_permission": "DENY",
                "orders_allowed": False,
                "signals_allowed": False,
            },
            "effects": {
                "human_gate_write": False,
                "credential_registry_write": False,
                "nonce_registry_write": False,
                "current_truth_apply": False,
                "decision_ledger_write": False,
                "command_queue_write": False,
                "runtime_activation": False,
                "executor_dispatch": False,
                "signal": False,
                "order": False,
                "capital_effect": False,
            },
        }
        self.assertion["assertion_sha256"] = sha256_obj(self.assertion)

    def verify(self, assertion=None, expected_assertion=None):
        assertion = self.assertion if assertion is None else assertion
        return verify_asymmetric_human_approval_v2(
            self.challenge,
            assertion,
            self.credentials,
            self.nonces,
            expected_assertion_sha256=self.assertion["assertion_sha256"] if expected_assertion is None else expected_assertion,
            expected_credential_registry_sha256=self.credentials["registry_sha256"],
            expected_nonce_registry_sha256=self.nonces["registry_sha256"],
            expected_authority_root_sha256=ROOT,
            expected_human_subject_id="robert",
            expected_custody_provider_id="custody-r6-v2",
            expected_verifier_id="external-webauthn-verifier",
            expected_verifier_key_id="external-verifier-key-04",
            expected_origin="https://control.example.invalid",
            expected_rp_id="control.example.invalid",
            expected_key_epoch=4,
            verified_at="2026-08-20T03:26:00+07:00",
        )

    def test_valid_assertion_requires_independent_digest(self):
        receipt = self.verify()
        self.assertEqual(receipt["schema"], "control_center.shadow_asymmetric_human_approval_verification.v2")
        self.assertTrue(receipt["external_assertion_digest_consumed"])
        self.assertEqual(receipt["external_assertion_sha256"], self.assertion["assertion_sha256"])
        self.assertEqual(receipt["external_asymmetric_verifier_evidence"], "EXPECTED_DIGEST_BOUND")
        self.assertEqual(receipt["trust_upgrade"], "SELF_HASH_TO_INDEPENDENT_ASSERTION_DIGEST")
        self.assertFalse(receipt["registry_write_performed"])
        self.assertEqual(receipt["execution_authority"], "NONE")

    def test_locally_rehashed_forged_assertion_is_rejected_against_retained_digest(self):
        forged = dict(self.assertion)
        forged["signature_sha256"] = "9" * 64
        forged["assertion_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "assertion_sha256"})
        self.assertNotEqual(forged["assertion_sha256"], self.assertion["assertion_sha256"])
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "assertion_external_digest_mismatch"):
            self.verify(forged)

    def test_wrong_retained_assertion_digest_is_rejected_before_semantic_acceptance(self):
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "assertion_external_digest_mismatch"):
            self.verify(expected_assertion="0" * 64)


if __name__ == "__main__":
    unittest.main()
