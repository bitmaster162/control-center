from __future__ import annotations

import copy
import unittest

from control_center.scripts.release_qualification_projection_p0_r1_1 import (
    P0ReleaseQualificationProjectionR11Error,
    build_p0_release_qualification_projection_r1_1,
    sha256_obj,
)


def receipt_fixture():
    body = {
        "schema": "bitevo.p0_release_qualification_receipt.v1_1",
        "manifest_sha256": "1" * 64,
        "snapshot_at": "2026-08-20T07:05:00+07:00",
        "generated_at": "2026-08-20T07:06:00+07:00",
        "qualified_input_parent_sha": "80d7e24c983529e837daaae49338cf71f9007425",
        "independent_live_snapshot_sha256": "42d9564b3a8f2f2c00e9ae21d4128fbe09be34c44a9a41848ca8da8a8d7075f1",
        "independent_live_snapshot_commit_sha": "f0fc766de0221076ba7165eb23a03ee993a4ccc1",
        "surface_ids": (
            "control_center_authority", "control_center_p0", "hanri_p0", "tradingos_p0_input",
            "sct_p0", "continuityos_history_p0", "triaxis_p0", "visionassist_p0", "return_broker_p0",
        ),
        "surface_count": 9,
        "schema_contract_count": 39,
        "verified_generations": ("R1", "R2", "R3", "R4", "R5", "R6.1", "R7", "R8", "R8.1", "R9"),
        "ci_blocked_surfaces": (
            "control_center_authority", "control_center_p0", "hanri_p0", "tradingos_p0_input",
            "triaxis_p0", "visionassist_p0", "return_broker_p0",
        ),
        "ci_blocked_surface_count": 7,
        "ci_green_surfaces": ("sct_p0", "continuityos_history_p0"),
        "ci_green_surface_count": 2,
        "known_conditions": (
            "CONTROL_CENTER_PROVIDER_CAPTURE_STALE",
            "ARCHIVEOS_BLOCKED_REVERIFY_STALE",
            "CI_PREJOB_BLOCKED_ON_SEVEN_SURFACES",
            "INDEPENDENT_LIVE_CROSSREPO_SNAPSHOT_BOUND",
        ),
        "global_invariants_verified": True,
        "schema_compatibility_verified": True,
        "manifest_snapshot_hash_bound": True,
        "independent_live_review_reference_bound": True,
        "cross_repo_state_live_read_performed_by_qualifier": False,
        "p0_architecture_closed_for_candidate_review": True,
        "final_independent_review_required": True,
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
        "status": "P0_RELEASE_CANDIDATE_R1_1_QUALIFIED_FOR_INDEPENDENT_FINAL_REVIEW_WITH_CONDITIONS",
    }
    body["release_qualification_sha256"] = sha256_obj(body)
    return body


def rehash(value):
    value["release_qualification_sha256"] = sha256_obj(
        {k: v for k, v in value.items() if k != "release_qualification_sha256"}
    )
    return value


class P0ReleaseQualificationProjectionR11Tests(unittest.TestCase):
    def build(self, receipt=None):
        receipt = receipt or receipt_fixture()
        return build_p0_release_qualification_projection_r1_1(
            receipt,
            expected_qualification_sha256=receipt["release_qualification_sha256"],
            expected_live_snapshot_sha256=receipt["independent_live_snapshot_sha256"],
        )

    def test_projection_is_non_authority_hold_wait(self):
        projection = self.build()
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_P0_RELEASE_QUALIFICATION_R1_1_PROJECTION")
        self.assertTrue(projection["final_independent_review_required"])
        self.assertFalse(projection["qualifier_live_read_claim"])
        self.assertEqual(projection["decision"], "HOLD")
        self.assertEqual(projection["action"], "WAIT")
        self.assertEqual(projection["effect_candidates_created"], 0)
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertTrue(all(v is False for v in projection["effects"].values()))

    def test_external_receipt_digest_is_required(self):
        receipt = receipt_fixture()
        with self.assertRaises(P0ReleaseQualificationProjectionR11Error):
            build_p0_release_qualification_projection_r1_1(
                receipt,
                expected_qualification_sha256="0" * 64,
                expected_live_snapshot_sha256=receipt["independent_live_snapshot_sha256"],
            )

    def test_external_live_snapshot_digest_is_required(self):
        receipt = receipt_fixture()
        with self.assertRaises(P0ReleaseQualificationProjectionR11Error):
            build_p0_release_qualification_projection_r1_1(
                receipt,
                expected_qualification_sha256=receipt["release_qualification_sha256"],
                expected_live_snapshot_sha256="0" * 64,
            )

    def test_qualifier_cannot_claim_its_own_live_read(self):
        receipt = rehash(copy.deepcopy(receipt_fixture()))
        receipt["cross_repo_state_live_read_performed_by_qualifier"] = True
        receipt = rehash(receipt)
        with self.assertRaises(P0ReleaseQualificationProjectionR11Error):
            self.build(receipt)

    def test_control_center_authority_blocker_is_required(self):
        receipt = copy.deepcopy(receipt_fixture())
        receipt["ci_blocked_surfaces"] = tuple(x for x in receipt["ci_blocked_surfaces"] if x != "control_center_authority") + ("sct_p0",)
        receipt = rehash(receipt)
        with self.assertRaises(P0ReleaseQualificationProjectionR11Error):
            self.build(receipt)

    def test_hold_cannot_be_laundered_to_pass(self):
        receipt = copy.deepcopy(receipt_fixture())
        receipt["decision"] = "PASS"
        receipt = rehash(receipt)
        with self.assertRaises(P0ReleaseQualificationProjectionR11Error):
            self.build(receipt)

    def test_final_independent_review_cannot_be_disabled(self):
        receipt = copy.deepcopy(receipt_fixture())
        receipt["final_independent_review_required"] = False
        receipt = rehash(receipt)
        with self.assertRaises(P0ReleaseQualificationProjectionR11Error):
            self.build(receipt)


if __name__ == "__main__":
    unittest.main()
