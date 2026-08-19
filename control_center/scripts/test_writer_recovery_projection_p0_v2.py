from __future__ import annotations

import copy
import unittest

from control_center.scripts.writer_recovery_projection_p0_v2 import (
    CLOSURE_EFFECTS,
    CONTROL_EFFECTS,
    REQUIRED_SAFETY,
    WriterRecoveryProjectionV2Error,
    build_writer_recovery_projection_v2,
    sha256_obj,
)

ROOT = "1" * 64


def anchor_fixture():
    body = {
        "schema": "control_center.shadow_human_gate_writer_authority_anchor.v1",
        "authority_root_sha256": ROOT,
        "writer_lease_sha256": "3" * 64,
        "legacy_receipt_index_sha256": "4" * 64,
        "paired_receipt_index_sha256": "5" * 64,
        "anchor_scope": "WRITER_LEASE_AND_RECEIPT_INDEX_ONLY",
        "retained_reference_required": True,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "retained_at": "2026-08-20T04:55:00+07:00",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(CONTROL_EFFECTS),
    }
    body["authority_anchor_sha256"] = sha256_obj(body)
    return body


def closure_fixture(anchor):
    body = {
        "schema": "bitevo.shadow_writer_fencing_recovery_closure.v2",
        "prior_writer_fencing_recovery_closure_sha256": "6" * 64,
        "recovery_verification_v2_sha256": "7" * 64,
        "authority_anchor_sha256": anchor["authority_anchor_sha256"],
        "authority_root_sha256": ROOT,
        "case_id": "case-r8-1",
        "case_sha256": "8" * 64,
        "challenge_id": "9" * 64,
        "writer_lease_sha256": "3" * 64,
        "legacy_receipt_index_sha256": "4" * 64,
        "paired_receipt_index_sha256": "5" * 64,
        "receipt_candidate_sha256": "a" * 64,
        "recovery_status": "RECEIPT_INDEXED_DEDUP_NO_RETRY",
        "recovery_action": "DEDUP_AND_ACK_ONLY",
        "paired_receipt_identity_verified": True,
        "authority_root_anchor_consumed": True,
        "cross_plane_anchor_verified": True,
        "status": "WRITER_FENCING_RECOVERY_HARDENED_SHADOW_ONLY",
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
        "effects": dict(CLOSURE_EFFECTS),
        "safety": dict(REQUIRED_SAFETY),
        "generated_at": "2026-08-20T04:56:00+07:00",
    }
    body["writer_fencing_recovery_closure_sha256"] = sha256_obj(body)
    return body


class WriterRecoveryProjectionV2Tests(unittest.TestCase):
    def build_chain(self):
        anchor = anchor_fixture()
        closure = closure_fixture(anchor)
        projection = build_writer_recovery_projection_v2(
            closure,
            anchor,
            expected_r8_1_closure_sha256=closure["writer_fencing_recovery_closure_sha256"],
            expected_authority_anchor_sha256=anchor["authority_anchor_sha256"],
            expected_authority_root_sha256=ROOT,
            projected_at="2026-08-20T04:57:00+07:00",
        )
        return anchor, closure, projection

    def test_projection_is_non_authority_hold_wait(self):
        _, _, projection = self.build_chain()
        self.assertEqual(projection["projection_role"], "NON_AUTHORITY_WRITER_RECOVERY_PROJECTION_V2")
        self.assertEqual(projection["decision"], "HOLD")
        self.assertEqual(projection["action"], "WAIT")
        self.assertFalse(projection["apply"])
        self.assertEqual(projection["executions_authorized"], 0)

    def test_gate_widening_is_rejected_even_if_rehashed(self):
        anchor, closure, _ = self.build_chain()
        forged = copy.deepcopy(closure)
        forged["decision"] = "PASS"
        forged["action"] = "LONG"
        forged["writer_fencing_recovery_closure_sha256"] = sha256_obj(
            {k: v for k, v in forged.items() if k != "writer_fencing_recovery_closure_sha256"}
        )
        with self.assertRaisesRegex(WriterRecoveryProjectionV2Error, "closure_gate_widening_forbidden"):
            build_writer_recovery_projection_v2(
                forged, anchor,
                expected_r8_1_closure_sha256=forged["writer_fencing_recovery_closure_sha256"],
                expected_authority_anchor_sha256=anchor["authority_anchor_sha256"],
                expected_authority_root_sha256=ROOT,
                projected_at="2026-08-20T04:57:00+07:00",
            )

    def test_wrong_retained_root_is_rejected(self):
        anchor, closure, _ = self.build_chain()
        with self.assertRaisesRegex(WriterRecoveryProjectionV2Error, "anchor_root_mismatch"):
            build_writer_recovery_projection_v2(
                closure, anchor,
                expected_r8_1_closure_sha256=closure["writer_fencing_recovery_closure_sha256"],
                expected_authority_anchor_sha256=anchor["authority_anchor_sha256"],
                expected_authority_root_sha256="0" * 64,
                projected_at="2026-08-20T04:57:00+07:00",
            )


if __name__ == "__main__":
    unittest.main()
