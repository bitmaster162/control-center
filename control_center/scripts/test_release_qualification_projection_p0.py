from __future__ import annotations

import copy
import unittest

from control_center.scripts.release_qualification_projection_p0 import (
    P0ReleaseQualificationProjectionError,
    build_p0_release_qualification_projection,
    sha256_obj,
)

def receipt_fixture():
    body = {
        "schema": "bitevo.p0_release_qualification_receipt.v1",
        "manifest_sha256": "1" * 64,
        "snapshot_at": "2026-08-20T05:59:00+07:00",
        "generated_at": "2026-08-20T05:59:30+07:00",
        "qualified_input_parent_sha": "2" * 40,
        "surface_ids": ("a", "b"),
        "surface_count": 2,
        "schema_contract_count": 39,
        "verified_generations": ("R1", "R9"),
        "ci_blocked_surfaces": ("a",),
        "ci_blocked_surface_count": 1,
        "known_conditions": ("CI_PREJOB_BLOCKED_ON_MULTIPLE_SURFACES",),
        "global_invariants_verified": True,
        "schema_compatibility_verified": True,
        "cross_repo_snapshot_bound": True,
        "p0_architecture_closed_for_candidate_review": True,
        "production_qualified": False,
        "release_ready": False,
        "merge_ready": False,
        "deploy_ready": False,
        "runtime_ready": False,
        "current_truth_promotion_allowed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "execution_authority": "NONE",
        "can_execute": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "decision": "HOLD",
        "action": "WAIT",
        "status": "P0_RELEASE_CANDIDATE_QUALIFIED_WITH_CONDITIONS",
    }
    body["release_qualification_sha256"] = sha256_obj(body)
    return body

def rehash(value):
    value["release_qualification_sha256"] = sha256_obj(
        {k: v for k, v in value.items() if k != "release_qualification_sha256"}
    )
    return value

class P0ReleaseQualificationProjectionTests(unittest.TestCase):
    def test_projection_is_non_authority_hold_wait(self):
        receipt = receipt_fixture()
        projection = build_p0_release_qualification_projection(
            receipt,
            expected_qualification_sha256=receipt["release_qualification_sha256"],
        )
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_P0_RELEASE_QUALIFICATION_PROJECTION")
        self.assertEqual(projection["candidate_status"], "QUALIFIED_WITH_CONDITIONS")
        self.assertEqual(projection["decision"], "HOLD")
        self.assertEqual(projection["action"], "WAIT")
        self.assertFalse(projection["production_qualified"])
        self.assertFalse(projection["release_ready"])
        self.assertFalse(projection["merge_ready"])
        self.assertFalse(projection["deploy_ready"])
        self.assertFalse(projection["runtime_ready"])
        self.assertEqual(projection["effect_candidates_created"], 0)
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertTrue(all(v is False for v in projection["effects"].values()))

    def test_rehashed_receipt_cannot_replace_retained_digest(self):
        receipt = receipt_fixture()
        expected = receipt["release_qualification_sha256"]
        forged = copy.deepcopy(receipt)
        forged["known_conditions"] = ("forged",)
        rehash(forged)
        with self.assertRaisesRegex(P0ReleaseQualificationProjectionError, "qualification_external_digest_mismatch"):
            build_p0_release_qualification_projection(forged, expected_qualification_sha256=expected)

    def test_release_ready_laundering_fails(self):
        receipt = receipt_fixture()
        forged = copy.deepcopy(receipt)
        forged["release_ready"] = True
        rehash(forged)
        with self.assertRaisesRegex(P0ReleaseQualificationProjectionError, "qualification_false_guard_breached:release_ready"):
            build_p0_release_qualification_projection(
                forged,
                expected_qualification_sha256=forged["release_qualification_sha256"],
            )

    def test_hold_to_pass_laundering_fails(self):
        receipt = receipt_fixture()
        forged = copy.deepcopy(receipt)
        forged["decision"] = "PASS"
        rehash(forged)
        with self.assertRaisesRegex(P0ReleaseQualificationProjectionError, "qualification_gate_widening_forbidden"):
            build_p0_release_qualification_projection(
                forged,
                expected_qualification_sha256=forged["release_qualification_sha256"],
            )

if __name__ == "__main__":
    unittest.main()
