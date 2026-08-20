from __future__ import annotations

import copy
import unittest

from control_center.scripts.human_approval_custody_p0 import (
    ATTESTATION_SCHEMA,
    NO_EFFECTS,
    REQUIRED_SAFETY,
    HumanApprovalCustodyError,
    build_human_approval_challenge,
    build_human_approval_registry_snapshot,
    compute_custody_attestation_mac,
    sha256_obj,
    verify_human_custody_approval,
)

SECRET = b"fixture-only-external-custody-secret"
ROOT = "1" * 64
CASE_SHA = "2" * 64
PACKET_SHA = "3" * 64
TWIN_SHA = "4" * 64


def challenge():
    return build_human_approval_challenge(
        case_id="case-r5-001",
        case_sha256=CASE_SHA,
        packet_sha256=PACKET_SHA,
        twin_prediction_id=TWIN_SHA,
        options=("LONG", "SHORT", "WAIT"),
        human_subject_id="operator:owner",
        session_id="session:r5:001",
        device_id="device:r5:trusted",
        custody_provider_id="custody:test",
        nonce="nonce-r5-001",
        issued_at="2026-08-20T03:00:00+07:00",
        expires_at="2026-08-20T03:10:00+07:00",
    )


def registry(entries=()):
    return build_human_approval_registry_snapshot(
        registry_id="human-approval-registry:r5",
        authority_root_sha256=ROOT,
        entries=entries,
    )


def attestation(ch, *, choice="WAIT", responded_at="2026-08-20T03:05:00+07:00", **overrides):
    body = {
        "schema": ATTESTATION_SCHEMA,
        "challenge_id": ch["challenge_id"],
        "challenge_sha256": ch["challenge_sha256"],
        "nonce": ch["nonce"],
        "human_subject_id": ch["human_subject_id"],
        "session_id": ch["session_id"],
        "device_id": ch["device_id"],
        "custody_provider_id": ch["custody_provider_id"],
        "verifier_id": "verifier:test",
        "verifier_key_id": "key:test:v1",
        "actual_choice": choice,
        "responded_at": responded_at,
        "proof_type": "HMAC_SHA256_EXTERNAL_CUSTODY_V1",
        "physical_human_presence_proven": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body.update(overrides)
    body["attestation_mac"] = compute_custody_attestation_mac(body, SECRET)
    body["attestation_sha256"] = sha256_obj(body)
    return body


def verify(ch, att, reg, *, secret=SECRET):
    return verify_human_custody_approval(
        ch,
        att,
        reg,
        expected_registry_sha256=reg["registry_sha256"],
        expected_authority_root_sha256=ROOT,
        expected_human_subject_id="operator:owner",
        expected_verifier_id="verifier:test",
        expected_verifier_key_id="key:test:v1",
        verifier_secret=secret,
        verified_at="2026-08-20T03:06:00+07:00",
    )


class HumanApprovalCustodyP0Tests(unittest.TestCase):
    def test_valid_custody_approval_is_reveal_only_and_no_effect(self):
        ch = challenge()
        reg = registry()
        receipt = verify(ch, attestation(ch), reg)
        self.assertEqual(receipt["status"], "HUMAN_CUSTODY_APPROVAL_VERIFIED_SHADOW_ONLY")
        self.assertEqual(receipt["approval_scope"], "HUMAN_REVEAL_ONLY")
        self.assertEqual(receipt["single_use_status"], "ADMITTABLE_UNUSED_CHALLENGE_SHADOW_ONLY")
        self.assertTrue(receipt["custody_mac_verified"])
        self.assertTrue(receipt["challenge_window_verified"])
        self.assertTrue(receipt["challenge_unused_in_expected_registry"])
        self.assertFalse(receipt["physical_human_presence_proven"])
        self.assertFalse(receipt["registry_write_performed"])
        self.assertFalse(receipt["apply_allowed"])
        self.assertEqual(receipt["execution_authority"], "NONE")
        self.assertTrue(all(value is False for value in receipt["effects"].values()))
        self.assertEqual(receipt["next_registry_candidate"]["entry_count"], 1)
        self.assertFalse(receipt["next_registry_candidate"]["write_allowed"])

    def test_wrong_verifier_key_fails_mac(self):
        ch = challenge()
        reg = registry()
        with self.assertRaisesRegex(HumanApprovalCustodyError, "attestation_mac_invalid"):
            verify(ch, attestation(ch), reg, secret=b"wrong-secret")

    def test_expired_response_is_rejected_even_with_valid_mac(self):
        ch = challenge()
        reg = registry()
        expired = attestation(ch, responded_at="2026-08-20T03:11:00+07:00")
        with self.assertRaisesRegex(HumanApprovalCustodyError, "attestation_response_outside_challenge_window"):
            verify(ch, expired, reg)

    def test_session_transplant_is_rejected_even_after_rehash_and_resign(self):
        ch = challenge()
        reg = registry()
        transplanted = attestation(ch, session_id="session:attacker")
        with self.assertRaisesRegex(HumanApprovalCustodyError, "session_custody_mismatch"):
            verify(ch, transplanted, reg)

    def test_device_transplant_is_rejected(self):
        ch = challenge()
        reg = registry()
        transplanted = attestation(ch, device_id="device:other")
        with self.assertRaisesRegex(HumanApprovalCustodyError, "device_custody_mismatch"):
            verify(ch, transplanted, reg)

    def test_used_challenge_replay_is_rejected_against_external_registry(self):
        ch = challenge()
        first_registry = registry()
        first = verify(ch, attestation(ch), first_registry)
        used_registry = first["next_registry_candidate"]
        with self.assertRaisesRegex(HumanApprovalCustodyError, "challenge_replay_detected"):
            verify(ch, attestation(ch), used_registry)

    def test_physical_presence_cannot_be_claimed_by_hmac_attestation(self):
        ch = challenge()
        reg = registry()
        overclaim = attestation(ch, physical_human_presence_proven=True)
        with self.assertRaisesRegex(HumanApprovalCustodyError, "physical_presence_overclaim"):
            verify(ch, overclaim, reg)

    def test_choice_outside_frozen_options_is_rejected(self):
        ch = challenge()
        reg = registry()
        wrong = attestation(ch, choice="EXIT")
        with self.assertRaisesRegex(HumanApprovalCustodyError, "attestation_choice_outside_options"):
            verify(ch, wrong, reg)

    def test_tampered_challenge_packet_binding_is_detected(self):
        ch = challenge()
        reg = registry()
        forged = copy.deepcopy(ch)
        forged["packet_sha256"] = "9" * 64
        forged["challenge_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "challenge_sha256"})
        with self.assertRaisesRegex(HumanApprovalCustodyError, "challenge_id_binding_mismatch"):
            verify(forged, attestation(forged), reg)


if __name__ == "__main__":
    unittest.main()
