from __future__ import annotations

import copy
import unittest

from control_center.scripts.human_approval_custody_p0 import build_human_approval_challenge
from control_center.scripts.human_asymmetric_custody_p0 import (
    ASYMMETRIC_ASSERTION_SCHEMA,
    HumanAsymmetricCustodyError,
    build_human_credential_registry_snapshot,
    build_nonce_epoch_registry_snapshot,
    sha256_obj,
    verify_asymmetric_human_approval,
)

ROOT = "1" * 64
CASE_SHA = "2" * 64
PACKET_SHA = "3" * 64
TWIN_SHA = "4" * 64
CREDENTIAL_ID = "5" * 64
PUBLIC_KEY_SHA = "6" * 64
SIGNATURE_SHA = "7" * 64
PREVIOUS_EPOCH = "8" * 64


class HumanAsymmetricCustodyP0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.challenge = build_human_approval_challenge(
            case_id="case-r6-001",
            case_sha256=CASE_SHA,
            packet_sha256=PACKET_SHA,
            twin_prediction_id=TWIN_SHA,
            options=("LONG", "SHORT", "WAIT"),
            human_subject_id="robert",
            session_id="session-r6",
            device_id="device-r6",
            custody_provider_id="custody-r6",
            nonce="nonce-r6-unique-001",
            issued_at="2026-08-20T03:00:00+07:00",
            expires_at="2026-08-20T03:10:00+07:00",
        )
        self.credential_registry = build_human_credential_registry_snapshot(
            registry_id="human-credentials-r6",
            authority_root_sha256=ROOT,
            entries=(
                {
                    "human_subject_id": "robert",
                    "device_id": "device-r6",
                    "custody_provider_id": "custody-r6",
                    "credential_id_sha256": CREDENTIAL_ID,
                    "public_key_sha256": PUBLIC_KEY_SHA,
                    "algorithm": "ED25519",
                    "key_epoch": 3,
                    "status": "ACTIVE",
                    "not_before": "2026-08-20T00:00:00+07:00",
                    "not_after": "2026-08-21T00:00:00+07:00",
                    "revoked_at": None,
                    "counter_supported": True,
                    "sign_count": 41,
                },
            ),
        )
        self.nonce_registry = build_nonce_epoch_registry_snapshot(
            registry_id="human-nonces-r6",
            authority_root_sha256=ROOT,
            epoch_number=12,
            epoch_started_at="2026-08-20T00:00:00+07:00",
            epoch_expires_at="2026-08-21T00:00:00+07:00",
            previous_epoch_sha256=PREVIOUS_EPOCH,
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
            "session_id": "session-r6",
            "device_id": "device-r6",
            "custody_provider_id": "custody-r6",
            "nonce": "nonce-r6-unique-001",
            "credential_id_sha256": CREDENTIAL_ID,
            "public_key_sha256": PUBLIC_KEY_SHA,
            "algorithm": "ED25519",
            "key_epoch": 3,
            "signature_sha256": SIGNATURE_SHA,
            "verifier_id": "webauthn-verifier-r6",
            "verifier_key_id": "verifier-key-r6-01",
            "origin": "https://control.example.invalid",
            "rp_id": "control.example.invalid",
            "actual_choice": "LONG",
            "responded_at": "2026-08-20T03:05:00+07:00",
            "signature_verified": True,
            "external_asymmetric_verifier_assertion": True,
            "local_signature_math_verified": False,
            "user_present": True,
            "user_verified": True,
            "physical_human_presence_proven": False,
            "counter_supported": True,
            "sign_count_before": 41,
            "sign_count_after": 42,
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

    def verify(self, assertion=None, credential_registry=None, nonce_registry=None, **overrides):
        return verify_asymmetric_human_approval(
            self.challenge,
            self.assertion if assertion is None else assertion,
            self.credential_registry if credential_registry is None else credential_registry,
            self.nonce_registry if nonce_registry is None else nonce_registry,
            expected_credential_registry_sha256=(self.credential_registry if credential_registry is None else credential_registry)["registry_sha256"],
            expected_nonce_registry_sha256=(self.nonce_registry if nonce_registry is None else nonce_registry)["registry_sha256"],
            expected_authority_root_sha256=ROOT,
            expected_human_subject_id="robert",
            expected_custody_provider_id="custody-r6",
            expected_verifier_id=overrides.pop("expected_verifier_id", "webauthn-verifier-r6"),
            expected_verifier_key_id=overrides.pop("expected_verifier_key_id", "verifier-key-r6-01"),
            expected_origin=overrides.pop("expected_origin", "https://control.example.invalid"),
            expected_rp_id=overrides.pop("expected_rp_id", "control.example.invalid"),
            expected_key_epoch=overrides.pop("expected_key_epoch", 3),
            verified_at=overrides.pop("verified_at", "2026-08-20T03:06:00+07:00"),
            **overrides,
        )

    @staticmethod
    def rehash(record):
        record["assertion_sha256"] = sha256_obj({k: v for k, v in record.items() if k != "assertion_sha256"})
        return record

    def test_valid_asymmetric_assertion_produces_no_write_candidates(self):
        receipt = self.verify()
        self.assertEqual(receipt["status"], "ASYMMETRIC_HUMAN_APPROVAL_VERIFIED_SHADOW_ONLY")
        self.assertTrue(receipt["signature_verified_by_external_asymmetric_verifier"])
        self.assertFalse(receipt["local_signature_math_verified"])
        self.assertFalse(receipt["physical_human_presence_proven"])
        self.assertTrue(receipt["nonce_unused_in_expected_cumulative_registry"])
        self.assertTrue(receipt["challenge_unused_in_expected_cumulative_registry"])
        self.assertEqual(receipt["next_credential_registry_candidate"]["entries"][0]["sign_count"], 42)
        self.assertIn(self.challenge["challenge_id"], receipt["next_nonce_registry_candidate"]["used_challenge_ids"])
        self.assertTrue(all(value is False for value in receipt["effects"].values()))
        self.assertEqual(receipt["execution_authority"], "NONE")
        self.assertFalse(receipt["can_execute"])

    def test_reused_nonce_is_rejected_even_with_new_challenge_digest(self):
        nonce_sha = __import__("hashlib").sha256(self.challenge["nonce"].encode("utf-8")).hexdigest()
        registry = build_nonce_epoch_registry_snapshot(
            registry_id="human-nonces-r6",
            authority_root_sha256=ROOT,
            epoch_number=12,
            epoch_started_at="2026-08-20T00:00:00+07:00",
            epoch_expires_at="2026-08-21T00:00:00+07:00",
            previous_epoch_sha256=PREVIOUS_EPOCH,
            used_nonce_sha256s=(nonce_sha,),
        )
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "nonce_replay_detected"):
            self.verify(nonce_registry=registry)

    def test_used_challenge_is_rejected(self):
        registry = build_nonce_epoch_registry_snapshot(
            registry_id="human-nonces-r6",
            authority_root_sha256=ROOT,
            epoch_number=12,
            epoch_started_at="2026-08-20T00:00:00+07:00",
            epoch_expires_at="2026-08-21T00:00:00+07:00",
            previous_epoch_sha256=PREVIOUS_EPOCH,
            used_challenge_ids=(self.challenge["challenge_id"],),
        )
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "challenge_replay_detected"):
            self.verify(nonce_registry=registry)

    def test_old_key_epoch_is_rejected(self):
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "key_epoch_mismatch"):
            self.verify(expected_key_epoch=4)

    def test_revoked_credential_is_rejected(self):
        registry = copy.deepcopy(self.credential_registry)
        entry = dict(registry["entries"][0])
        entry["status"] = "REVOKED"
        entry["revoked_at"] = "2026-08-20T02:00:00+07:00"
        registry["entries"] = (entry,)
        registry["registry_sha256"] = sha256_obj({k: v for k, v in registry.items() if k != "registry_sha256"})
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "credential_not_active"):
            self.verify(credential_registry=registry)

    def test_sign_counter_rollback_is_rejected(self):
        assertion = self.rehash({**self.assertion, "sign_count_after": 40})
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "sign_count_not_monotonic"):
            self.verify(assertion=assertion)

    def test_same_sign_counter_is_rejected(self):
        assertion = self.rehash({**self.assertion, "sign_count_after": 41})
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "sign_count_not_monotonic"):
            self.verify(assertion=assertion)

    def test_wrong_origin_or_rp_is_rejected(self):
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "origin_or_rp_id_mismatch"):
            self.verify(expected_origin="https://evil.example.invalid")

    def test_public_key_transplant_is_rejected(self):
        assertion = self.rehash({**self.assertion, "public_key_sha256": "9" * 64})
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "credential_binding_mismatch:public_key_sha256"):
            self.verify(assertion=assertion)

    def test_local_signature_math_overclaim_is_rejected(self):
        assertion = self.rehash({**self.assertion, "local_signature_math_verified": True})
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "local_signature_math_overclaim"):
            self.verify(assertion=assertion)

    def test_user_verification_is_required(self):
        assertion = self.rehash({**self.assertion, "user_verified": False})
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "authenticator_user_presence_or_verification_missing"):
            self.verify(assertion=assertion)

    def test_challenge_outside_nonce_epoch_is_rejected(self):
        registry = build_nonce_epoch_registry_snapshot(
            registry_id="human-nonces-r6",
            authority_root_sha256=ROOT,
            epoch_number=13,
            epoch_started_at="2026-08-20T04:00:00+07:00",
            epoch_expires_at="2026-08-21T00:00:00+07:00",
            previous_epoch_sha256=self.nonce_registry["registry_sha256"],
        )
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "challenge_outside_nonce_epoch"):
            self.verify(nonce_registry=registry)

    def test_effect_smuggling_is_rejected(self):
        assertion = copy.deepcopy(self.assertion)
        assertion["effects"]["human_gate_write"] = True
        assertion = self.rehash(assertion)
        with self.assertRaisesRegex(HumanAsymmetricCustodyError, "assertion_effect_boundary_breached"):
            self.verify(assertion=assertion)


if __name__ == "__main__":
    unittest.main()
