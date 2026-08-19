from __future__ import annotations

import copy
import unittest

from control_center.scripts.human_gate_writer_fencing_p0 import (
    HumanGateWriterFencingError,
    R7_EFFECTS,
    REQUIRED_SAFETY,
    build_commit_receipt_index_snapshot,
    build_crash_recovery_verification,
    build_durable_commit_receipt_candidate,
    build_fenced_commit_attempt,
    build_writer_lease_snapshot,
    sha256_obj,
)

ROOT = "1" * 64
ATOMIC_SHA_SEED = "2" * 64
PRIOR_STATE = "3" * 64
NEXT_STATE = "4" * 64
APPROVAL = "5" * 64
CHALLENGE = "6" * 64
COMMIT_ID = "7" * 64
IDEMPOTENCY = "8" * 64
LEASE_ID = "9" * 64
PREVIOUS_LEASE = "a" * 64
PREVIOUS_INDEX = "b" * 64
BACKEND_TXN = "c" * 64


def atomic_fixture():
    body = {
        "schema": "control_center.shadow_human_gate_atomic_consume_verification.v1",
        "prepare_sha256": ATOMIC_SHA_SEED,
        "compare_sha256": "d" * 64,
        "commit_candidate_sha256": "e" * 64,
        "approval_verification_sha256": APPROVAL,
        "case_id": "case-r8",
        "case_sha256": "f" * 64,
        "challenge_id": CHALLENGE,
        "nonce_sha256": "0" * 64,
        "prior_state_sha256": PRIOR_STATE,
        "next_state_candidate_sha256": NEXT_STATE,
        "cas_generation_from": 10,
        "cas_generation_to": 11,
        "toctou_guard_model": "COMPARE_AND_SWAP_PRECONDITION",
        "atomicity_status": "PROTOCOL_VERIFIED_NO_DURABLE_COMMIT",
        "single_use_status": "CANDIDATE_ONLY_NOT_DURABLY_ENFORCED",
        "commit_performed": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R7_EFFECTS),
    }
    body["atomic_consume_verification_sha256"] = sha256_obj(body)
    return body


def lease_fixture(*, lease_id=LEASE_ID, token=7, writer="writer-a", issued="2026-08-20T04:00:00+07:00", expires="2026-08-20T04:30:00+07:00"):
    return build_writer_lease_snapshot(
        lease_id=lease_id,
        authority_root_sha256=ROOT,
        writer_id=writer,
        lease_epoch=3 if token == 7 else 4,
        fencing_token=token,
        bound_state_sha256=PRIOR_STATE,
        bound_generation=10,
        issued_at=issued,
        expires_at=expires,
        previous_lease_sha256=PREVIOUS_LEASE,
    )


def index_fixture(*, commits=(), keys=(), generation=0):
    return build_commit_receipt_index_snapshot(
        index_id="human-gate-receipts-r8",
        authority_root_sha256=ROOT,
        generation=generation,
        commit_ids=commits,
        idempotency_key_sha256s=keys,
        previous_index_sha256=PREVIOUS_INDEX,
    )


class HumanGateWriterFencingTests(unittest.TestCase):
    def build_attempt(self, *, lease=None, index=None, attempted_at="2026-08-20T04:10:00+07:00"):
        atomic = atomic_fixture()
        lease = lease_fixture() if lease is None else lease
        index = index_fixture() if index is None else index
        attempt = build_fenced_commit_attempt(
            atomic,
            lease,
            index,
            expected_atomic_consume_sha256=atomic["atomic_consume_verification_sha256"],
            expected_writer_lease_sha256=lease["lease_sha256"],
            expected_receipt_index_sha256=index["index_sha256"],
            commit_id=COMMIT_ID,
            idempotency_key_sha256=IDEMPOTENCY,
            attempted_at=attempted_at,
        )
        receipt = build_durable_commit_receipt_candidate(
            attempt,
            expected_attempt_sha256=attempt["attempt_sha256"],
            backend_id="human-gate-store-r8",
            backend_transaction_id_sha256=BACKEND_TXN,
            accepted_at="2026-08-20T04:11:00+07:00",
        )
        return atomic, lease, index, attempt, receipt

    def test_before_write_recovery_is_protocol_only_and_no_write(self):
        _, lease, index, attempt, receipt = self.build_attempt()
        recovery = build_crash_recovery_verification(
            attempt,
            receipt,
            lease,
            index,
            expected_attempt_sha256=attempt["attempt_sha256"],
            expected_receipt_candidate_sha256=receipt["receipt_candidate_sha256"],
            expected_current_writer_lease_sha256=lease["lease_sha256"],
            expected_current_receipt_index_sha256=index["index_sha256"],
            crash_point="BEFORE_WRITE",
            readback_state_sha256=PRIOR_STATE,
            readback_generation=10,
            observed_at="2026-08-20T04:12:00+07:00",
        )
        self.assertEqual(recovery["protocol_status"], "FENCING_AND_CRASH_RECOVERY_VERIFIED_SHADOW_ONLY")
        self.assertEqual(recovery["recovery_status"], "NO_WRITE_OBSERVED_RETRY_REQUIRES_FRESH_CAS")
        self.assertTrue(recovery["retry_allowed"])
        self.assertFalse(recovery["blind_retry_allowed"])
        self.assertFalse(recovery["durable_commit_proven"])
        self.assertFalse(recovery["human_gate_write_performed"])
        self.assertEqual(recovery["execution_authority"], "NONE")

    def test_attempt_after_lease_expiry_is_rejected(self):
        lease = lease_fixture(expires="2026-08-20T04:09:00+07:00")
        with self.assertRaisesRegex(HumanGateWriterFencingError, "writer_lease_expired_or_not_started_at_attempt"):
            self.build_attempt(lease=lease)

    def test_old_writer_is_fenced_after_new_token_appears(self):
        _, _, index, attempt, receipt = self.build_attempt()
        new_lease = lease_fixture(lease_id="d" * 64, token=8, writer="writer-b")
        recovery = build_crash_recovery_verification(
            attempt,
            receipt,
            new_lease,
            index,
            expected_attempt_sha256=attempt["attempt_sha256"],
            expected_receipt_candidate_sha256=receipt["receipt_candidate_sha256"],
            expected_current_writer_lease_sha256=new_lease["lease_sha256"],
            expected_current_receipt_index_sha256=index["index_sha256"],
            crash_point="BEFORE_WRITE",
            readback_state_sha256=PRIOR_STATE,
            readback_generation=10,
            observed_at="2026-08-20T04:12:00+07:00",
        )
        self.assertTrue(recovery["stale_writer_fenced"])
        self.assertEqual(recovery["recovery_status"], "STALE_WRITER_FENCED_REACQUIRE_REQUIRED")
        self.assertFalse(recovery["retry_allowed"])

    def test_split_brain_same_fencing_token_is_rejected(self):
        _, _, index, attempt, receipt = self.build_attempt()
        conflicting = lease_fixture(lease_id="d" * 64, token=7, writer="writer-b")
        with self.assertRaisesRegex(HumanGateWriterFencingError, "split_brain_same_fencing_token_detected"):
            build_crash_recovery_verification(
                attempt,
                receipt,
                conflicting,
                index,
                expected_attempt_sha256=attempt["attempt_sha256"],
                expected_receipt_candidate_sha256=receipt["receipt_candidate_sha256"],
                expected_current_writer_lease_sha256=conflicting["lease_sha256"],
                expected_current_receipt_index_sha256=index["index_sha256"],
                crash_point="BEFORE_WRITE",
                readback_state_sha256=PRIOR_STATE,
                readback_generation=10,
                observed_at="2026-08-20T04:12:00+07:00",
            )

    def test_write_observed_without_receipt_must_hold_and_never_blind_retry(self):
        _, lease, index, attempt, receipt = self.build_attempt()
        recovery = build_crash_recovery_verification(
            attempt,
            receipt,
            lease,
            index,
            expected_attempt_sha256=attempt["attempt_sha256"],
            expected_receipt_candidate_sha256=receipt["receipt_candidate_sha256"],
            expected_current_writer_lease_sha256=lease["lease_sha256"],
            expected_current_receipt_index_sha256=index["index_sha256"],
            crash_point="AFTER_WRITE_BEFORE_RECEIPT",
            readback_state_sha256=NEXT_STATE,
            readback_generation=11,
            observed_at="2026-08-20T04:12:00+07:00",
        )
        self.assertEqual(recovery["recovery_status"], "WRITE_OBSERVED_RECEIPT_ABSENT_HOLD")
        self.assertEqual(recovery["recovery_action"], "HOLD_AND_RECONCILE_EXTERNAL_BACKEND")
        self.assertFalse(recovery["retry_allowed"])

    def test_receipt_indexed_after_ack_crash_is_dedup_only(self):
        _, lease, _, attempt, receipt = self.build_attempt()
        current_index = index_fixture(commits=(COMMIT_ID,), keys=(IDEMPOTENCY,), generation=1)
        recovery = build_crash_recovery_verification(
            attempt,
            receipt,
            lease,
            current_index,
            expected_attempt_sha256=attempt["attempt_sha256"],
            expected_receipt_candidate_sha256=receipt["receipt_candidate_sha256"],
            expected_current_writer_lease_sha256=lease["lease_sha256"],
            expected_current_receipt_index_sha256=current_index["index_sha256"],
            crash_point="AFTER_RECEIPT_BEFORE_ACK",
            readback_state_sha256=NEXT_STATE,
            readback_generation=11,
            observed_at="2026-08-20T04:12:00+07:00",
        )
        self.assertTrue(recovery["receipt_indexed"])
        self.assertEqual(recovery["recovery_status"], "RECEIPT_INDEXED_DEDUP_NO_RETRY")
        self.assertEqual(recovery["recovery_action"], "DEDUP_AND_ACK_ONLY")
        self.assertFalse(recovery["retry_allowed"])

    def test_duplicate_commit_identity_is_rejected_before_attempt(self):
        index = index_fixture(commits=(COMMIT_ID,), keys=(IDEMPOTENCY,), generation=1)
        with self.assertRaisesRegex(HumanGateWriterFencingError, "commit_id_replay_detected"):
            self.build_attempt(index=index)

    def test_receipt_candidate_cannot_claim_durable_write_even_after_rehash(self):
        _, lease, index, attempt, receipt = self.build_attempt()
        forged = copy.deepcopy(receipt)
        forged["receipt_issued"] = True
        forged["write_performed"] = True
        forged["durable_commit_proven"] = True
        forged["live_backend_observed"] = True
        forged["receipt_candidate_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "receipt_candidate_sha256"})
        with self.assertRaisesRegex(HumanGateWriterFencingError, "receipt_candidate_issuance_or_write_overclaim|receipt_candidate_durability_overclaim"):
            build_crash_recovery_verification(
                attempt,
                forged,
                lease,
                index,
                expected_attempt_sha256=attempt["attempt_sha256"],
                expected_receipt_candidate_sha256=forged["receipt_candidate_sha256"],
                expected_current_writer_lease_sha256=lease["lease_sha256"],
                expected_current_receipt_index_sha256=index["index_sha256"],
                crash_point="BEFORE_WRITE",
                readback_state_sha256=PRIOR_STATE,
                readback_generation=10,
                observed_at="2026-08-20T04:12:00+07:00",
            )


if __name__ == "__main__":
    unittest.main()
