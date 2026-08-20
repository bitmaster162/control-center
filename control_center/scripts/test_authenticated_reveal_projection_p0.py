from __future__ import annotations

import copy
import unittest

from control_center.scripts.authenticated_reveal_projection_p0 import (
    AUTHENTICATED_REVEAL_SCHEMA,
    AuthenticatedRevealProjectionError,
    REQUIRED_SAFETY,
    build_authenticated_reveal_projection,
    sha256_obj,
)

EFFECTS = {
    "human_gate_write": False,
    "registry_write": False,
    "ledger_write": False,
    "return_index_write": False,
    "current_truth_apply": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}


def closure():
    body = {
        "schema": AUTHENTICATED_REVEAL_SCHEMA,
        "case_id": "case-r5-001",
        "case_sha256": "1" * 64,
        "reveal_sha256": "2" * 64,
        "subject_manifest_sha256": "3" * 64,
        "domain_history_closure_sha256": "4" * 64,
        "approval_verification_sha256": "5" * 64,
        "challenge_id": "6" * 64,
        "human_subject_id": "operator:owner",
        "session_id": "session:r5:001",
        "device_id": "device:r5:trusted",
        "custody_provider_id": "custody:test",
        "verifier_id": "verifier:test",
        "verifier_key_id": "key:test:v1",
        "actual_choice": "WAIT",
        "decided_at": "2026-08-20T03:05:00+07:00",
        "approved_reveal_intent_sha256": "7" * 64,
        "authentication_status": "TRUSTED_CUSTODY_ATTESTED_SHADOW_ONLY",
        "human_identity_scope": "CUSTODY_PROVIDER_SUBJECT_ASSERTION_ONLY",
        "cryptographic_property": "HMAC_SHA256_VERIFIER_KEY_POSSESSION",
        "physical_human_presence_proven": False,
        "single_use_registry_candidate_verified": True,
        "current_truth_promotion_allowed": False,
        "history_write_performed": False,
        "human_gate_write_performed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "effects": dict(EFFECTS),
        "safety": dict(REQUIRED_SAFETY),
        "generated_at": "2026-08-20T03:06:00+07:00",
    }
    body["authenticated_reveal_closure_sha256"] = sha256_obj(body)
    return body


def rehash(value):
    value["authenticated_reveal_closure_sha256"] = sha256_obj(
        {k: v for k, v in value.items() if k != "authenticated_reveal_closure_sha256"}
    )
    return value


class AuthenticatedRevealProjectionP0Tests(unittest.TestCase):
    def test_valid_authenticated_reveal_projects_without_authority(self):
        result = build_authenticated_reveal_projection(closure())
        self.assertEqual(result["projection_kind"], "NON_AUTHORITY_AUTHENTICATED_REVEAL_PROJECTION")
        self.assertEqual(result["custody_authentication"], "VERIFIED_SHADOW_ONLY")
        self.assertEqual(result["physical_human_presence"], "NOT_PROVEN")
        self.assertFalse(result["current_truth_promotion_allowed"])
        self.assertFalse(result["apply"])
        self.assertTrue(all(value is False for value in result["mutations"].values()))
        self.assertEqual(result["effect_candidates_created"], 0)
        self.assertEqual(result["executions_authorized"], 0)
        self.assertEqual(result["safety"]["execution_authority"], "NONE")

    def test_physical_presence_overclaim_is_rejected(self):
        item = closure()
        item["physical_human_presence_proven"] = True
        rehash(item)
        with self.assertRaisesRegex(AuthenticatedRevealProjectionError, "physical_presence_overclaim"):
            build_authenticated_reveal_projection(item)

    def test_current_truth_promotion_is_rejected(self):
        item = closure()
        item["current_truth_promotion_allowed"] = True
        rehash(item)
        with self.assertRaisesRegex(AuthenticatedRevealProjectionError, "current_truth_promotion_forbidden"):
            build_authenticated_reveal_projection(item)

    def test_human_gate_write_is_rejected(self):
        item = closure()
        item["human_gate_write_performed"] = True
        rehash(item)
        with self.assertRaisesRegex(AuthenticatedRevealProjectionError, "write_boundary_breached"):
            build_authenticated_reveal_projection(item)

    def test_effect_smuggling_is_rejected(self):
        item = closure()
        item["effects"]["executor_dispatch"] = True
        rehash(item)
        with self.assertRaisesRegex(AuthenticatedRevealProjectionError, "effect_boundary_breached"):
            build_authenticated_reveal_projection(item)

    def test_execution_authority_is_rejected(self):
        item = closure()
        item["execution_authority"] = "ALLOW"
        rehash(item)
        with self.assertRaisesRegex(AuthenticatedRevealProjectionError, "authority_breached"):
            build_authenticated_reveal_projection(item)

    def test_hash_tamper_is_rejected(self):
        item = closure()
        item["actual_choice"] = "LONG"
        with self.assertRaisesRegex(AuthenticatedRevealProjectionError, "hash_mismatch"):
            build_authenticated_reveal_projection(item)


if __name__ == "__main__":
    unittest.main()
