from __future__ import annotations

import copy
import unittest

from control_center.scripts.writer_recovery_projection_p0 import (
    REQUIRED_FALSE_EFFECTS,
    REQUIRED_SAFETY,
    WriterRecoveryProjectionError,
    build_writer_recovery_projection,
    sha256_obj,
)


def closure_fixture():
    body = {
        "schema": "bitevo.shadow_writer_fencing_recovery_closure.v1",
        "case_id": "case-r8",
        "case_sha256": "1" * 64,
        "challenge_id": "2" * 64,
        "human_gate_consume_closure_sha256": "3" * 64,
        "recovery_verification_sha256": "4" * 64,
        "writer_lease_sha256": "5" * 64,
        "receipt_candidate_sha256": "6" * 64,
        "current_receipt_index_sha256": "7" * 64,
        "fencing_model": "MONOTONIC_FENCING_TOKEN_PLUS_LEASE_DIGEST",
        "crash_recovery_protocol": "READBACK_PLUS_RECEIPT_INDEX_DEDUP",
        "recovery_status": "WRITE_OBSERVED_RECEIPT_ABSENT_HOLD",
        "recovery_action": "HOLD_AND_RECONCILE_EXTERNAL_BACKEND",
        "status": "WRITER_FENCING_RECOVERY_BOUND_SHADOW_ONLY",
        "live_writer_backend_proven": False,
        "durable_commit_proven": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "decision": "HOLD",
        "action": "WAIT",
        "effects": {key: False for key in REQUIRED_FALSE_EFFECTS},
        "safety": dict(REQUIRED_SAFETY),
        "generated_at": "2026-08-20T04:20:00+07:00",
    }
    body["writer_fencing_recovery_closure_sha256"] = sha256_obj(body)
    return body


class WriterRecoveryProjectionTests(unittest.TestCase):
    def test_valid_closure_projects_non_authority_hold_wait(self):
        projection = build_writer_recovery_projection(closure_fixture())
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_WRITER_RECOVERY_PROJECTION")
        self.assertEqual(projection["decision"], "HOLD")
        self.assertEqual(projection["action"], "WAIT")
        self.assertEqual(projection["durability"], "NOT_PROVEN")
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertFalse(projection["apply"])

    def test_durability_overclaim_is_rejected_even_if_rehashed(self):
        forged = copy.deepcopy(closure_fixture())
        forged["durable_commit_proven"] = True
        forged["writer_fencing_recovery_closure_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "writer_fencing_recovery_closure_sha256"})
        with self.assertRaisesRegex(WriterRecoveryProjectionError, "writer_recovery_durability_overclaim"):
            build_writer_recovery_projection(forged)

    def test_hold_to_pass_widening_is_rejected(self):
        forged = copy.deepcopy(closure_fixture())
        forged["decision"] = "PASS_SHADOW"
        forged["action"] = "LONG"
        forged["writer_fencing_recovery_closure_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "writer_fencing_recovery_closure_sha256"})
        with self.assertRaisesRegex(WriterRecoveryProjectionError, "writer_recovery_gate_widening_forbidden"):
            build_writer_recovery_projection(forged)


if __name__ == "__main__":
    unittest.main()
