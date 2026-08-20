from __future__ import annotations

import copy
import unittest

from control_center.scripts.human_gate_writer_fencing_p0_v2 import (
    HumanGateWriterFencingV2Error,
    R8_EFFECTS,
    REQUIRED_SAFETY,
    build_crash_recovery_verification_v2,
    build_paired_commit_receipt_index_snapshot,
    build_writer_authority_root_anchor,
    sha256_obj,
)

ROOT = "1" * 64
LEASE_SHA_SEED = "2" * 64
LEGACY_INDEX_PREV = "3" * 64
COMMIT_A = "4" * 64
COMMIT_B = "5" * 64
IDEM_A = "6" * 64
IDEM_B = "7" * 64
RECEIPT_A = "8" * 64
RECEIPT_B = "9" * 64
CASE_SHA = "a" * 64
CHALLENGE = "b" * 64
APPROVAL = "c" * 64
ATOMIC = "d" * 64


def lease_fixture(root=ROOT):
    body = {
        "schema": "control_center.shadow_human_gate_writer_lease_snapshot.v1",
        "lease_id": LEASE_SHA_SEED,
        "authority_root_sha256": root,
        "writer_id": "writer-r8-1",
        "lease_epoch": 4,
        "fencing_token": 8,
        "bound_state_sha256": "e" * 64,
        "bound_generation": 11,
        "issued_at": "2026-08-20T04:30:00+07:00",
        "expires_at": "2026-08-20T05:30:00+07:00",
        "previous_lease_sha256": "f" * 64,
        "lease_status": "ACTIVE_SHADOW_LEASE_SNAPSHOT",
        "single_active_writer_claim": True,
        "live_lease_backend_proven": False,
        "lease_write_performed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["lease_sha256"] = sha256_obj(body)
    return body


def legacy_index_fixture(commits=(COMMIT_A,), keys=(IDEM_A,), root=ROOT):
    body = {
        "schema": "control_center.shadow_human_gate_commit_receipt_index_snapshot.v1",
        "index_id": "receipts-r8-1",
        "authority_root_sha256": root,
        "generation": 1,
        "commit_ids": tuple(commits),
        "idempotency_key_sha256s": tuple(keys),
        "entry_count": len(tuple(commits)),
        "previous_index_sha256": LEGACY_INDEX_PREV,
        "write_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["index_sha256"] = sha256_obj(body)
    return body


def legacy_recovery_fixture(lease, index, *, receipt_indexed=True, receipt_ref=RECEIPT_A):
    body = {
        "schema": "control_center.shadow_human_gate_crash_recovery_verification.v1",
        "attempt_sha256": "0" * 64,
        "receipt_candidate_sha256": receipt_ref,
        "current_writer_lease_sha256": lease["lease_sha256"],
        "current_receipt_index_sha256": index["index_sha256"],
        "case_id": "case-r8-1",
        "case_sha256": CASE_SHA,
        "challenge_id": CHALLENGE,
        "approval_verification_sha256": APPROVAL,
        "atomic_consume_verification_sha256": ATOMIC,
        "commit_id": COMMIT_A,
        "idempotency_key_sha256": IDEM_A,
        "attempt_writer_lease_sha256": lease["lease_sha256"],
        "attempt_fencing_token": 8,
        "current_fencing_token": 8,
        "stale_writer_fenced": False,
        "split_brain_same_token_rejected": True,
        "crash_point": "AFTER_RECEIPT_BEFORE_ACK" if receipt_indexed else "BEFORE_WRITE",
        "readback_state_sha256": "e" * 64,
        "readback_generation": 11 if receipt_indexed else 10,
        "receipt_indexed": receipt_indexed,
        "current_lease_live": True,
        "recovery_status": "RECEIPT_INDEXED_DEDUP_NO_RETRY" if receipt_indexed else "NO_WRITE_OBSERVED_RETRY_REQUIRES_FRESH_CAS",
        "recovery_action": "DEDUP_AND_ACK_ONLY" if receipt_indexed else "RECOMPARE_BEFORE_ANY_RETRY",
        "retry_allowed": False if receipt_indexed else True,
        "blind_retry_allowed": False,
        "fencing_model": "MONOTONIC_FENCING_TOKEN_PLUS_LEASE_DIGEST",
        "crash_recovery_protocol": "READBACK_PLUS_RECEIPT_INDEX_DEDUP",
        "protocol_status": "FENCING_AND_CRASH_RECOVERY_VERIFIED_SHADOW_ONLY",
        "live_writer_backend_proven": False,
        "durable_commit_proven": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "observed_at": "2026-08-20T04:45:00+07:00",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["recovery_verification_sha256"] = sha256_obj(body)
    return body


class HumanGateWriterFencingV2Tests(unittest.TestCase):
    def build_chain(self):
        lease = lease_fixture()
        legacy = legacy_index_fixture()
        paired = build_paired_commit_receipt_index_snapshot(
            legacy,
            ({"commit_id": COMMIT_A, "idempotency_key_sha256": IDEM_A, "receipt_reference_sha256": RECEIPT_A},),
            expected_legacy_index_sha256=legacy["index_sha256"],
            expected_authority_root_sha256=ROOT,
        )
        anchor = build_writer_authority_root_anchor(
            lease,
            legacy,
            paired,
            expected_writer_lease_sha256=lease["lease_sha256"],
            expected_legacy_receipt_index_sha256=legacy["index_sha256"],
            expected_paired_receipt_index_sha256=paired["index_sha256"],
            expected_authority_root_sha256=ROOT,
            retained_at="2026-08-20T04:46:00+07:00",
        )
        recovery = legacy_recovery_fixture(lease, legacy)
        v2 = build_crash_recovery_verification_v2(
            recovery,
            paired,
            anchor,
            expected_legacy_recovery_sha256=recovery["recovery_verification_sha256"],
            expected_paired_receipt_index_sha256=paired["index_sha256"],
            expected_authority_anchor_sha256=anchor["authority_anchor_sha256"],
            expected_authority_root_sha256=ROOT,
        )
        return lease, legacy, paired, anchor, recovery, v2

    def test_happy_path_binds_pair_and_authority_root(self):
        *_, v2 = self.build_chain()
        self.assertTrue(v2["paired_receipt_identity_verified"])
        self.assertTrue(v2["authority_root_anchor_consumed"])
        self.assertEqual(v2["protocol_status"], "FENCING_AND_CRASH_RECOVERY_HARDENED_SHADOW_ONLY")
        self.assertFalse(v2["durable_commit_proven"])
        self.assertEqual(v2["execution_authority"], "NONE")

    def test_swapped_parallel_pairing_is_rejected(self):
        legacy = legacy_index_fixture(commits=(COMMIT_A, COMMIT_B), keys=(IDEM_A, IDEM_B))
        with self.assertRaisesRegex(HumanGateWriterFencingV2Error, "paired_index_legacy_pair_position_mismatch"):
            build_paired_commit_receipt_index_snapshot(
                legacy,
                (
                    {"commit_id": COMMIT_A, "idempotency_key_sha256": IDEM_B, "receipt_reference_sha256": RECEIPT_A},
                    {"commit_id": COMMIT_B, "idempotency_key_sha256": IDEM_A, "receipt_reference_sha256": RECEIPT_B},
                ),
                expected_legacy_index_sha256=legacy["index_sha256"],
                expected_authority_root_sha256=ROOT,
            )

    def test_wrong_receipt_reference_for_indexed_commit_is_rejected(self):
        lease, legacy, paired, anchor, recovery, _ = self.build_chain()
        bad = copy.deepcopy(paired)
        bad["entries"] = (
            {"commit_id": COMMIT_A, "idempotency_key_sha256": IDEM_A, "receipt_reference_sha256": RECEIPT_B},
        )
        bad["index_sha256"] = sha256_obj({k: v for k, v in bad.items() if k != "index_sha256"})
        bad_anchor = build_writer_authority_root_anchor(
            lease, legacy, bad,
            expected_writer_lease_sha256=lease["lease_sha256"],
            expected_legacy_receipt_index_sha256=legacy["index_sha256"],
            expected_paired_receipt_index_sha256=bad["index_sha256"],
            expected_authority_root_sha256=ROOT,
            retained_at="2026-08-20T04:46:00+07:00",
        )
        with self.assertRaisesRegex(HumanGateWriterFencingV2Error, "recovery_v2_receipt_reference_mismatch"):
            build_crash_recovery_verification_v2(
                recovery, bad, bad_anchor,
                expected_legacy_recovery_sha256=recovery["recovery_verification_sha256"],
                expected_paired_receipt_index_sha256=bad["index_sha256"],
                expected_authority_anchor_sha256=bad_anchor["authority_anchor_sha256"],
                expected_authority_root_sha256=ROOT,
            )

    def test_wrong_retained_anchor_digest_is_rejected(self):
        _, _, paired, anchor, recovery, _ = self.build_chain()
        with self.assertRaisesRegex(HumanGateWriterFencingV2Error, "authority_anchor_external_digest_mismatch"):
            build_crash_recovery_verification_v2(
                recovery, paired, anchor,
                expected_legacy_recovery_sha256=recovery["recovery_verification_sha256"],
                expected_paired_receipt_index_sha256=paired["index_sha256"],
                expected_authority_anchor_sha256="0" * 64,
                expected_authority_root_sha256=ROOT,
            )

    def test_rehashed_authority_root_substitution_is_rejected(self):
        _, _, paired, anchor, recovery, _ = self.build_chain()
        forged = copy.deepcopy(anchor)
        forged["authority_root_sha256"] = "0" * 64
        forged["authority_anchor_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "authority_anchor_sha256"})
        with self.assertRaisesRegex(HumanGateWriterFencingV2Error, "authority_anchor_root_mismatch"):
            build_crash_recovery_verification_v2(
                recovery, paired, forged,
                expected_legacy_recovery_sha256=recovery["recovery_verification_sha256"],
                expected_paired_receipt_index_sha256=paired["index_sha256"],
                expected_authority_anchor_sha256=forged["authority_anchor_sha256"],
                expected_authority_root_sha256=ROOT,
            )

    def test_durable_commit_overclaim_in_legacy_recovery_is_rejected(self):
        _, _, paired, anchor, recovery, _ = self.build_chain()
        forged = copy.deepcopy(recovery)
        forged["durable_commit_proven"] = True
        forged["recovery_verification_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "recovery_verification_sha256"})
        with self.assertRaisesRegex(HumanGateWriterFencingV2Error, "legacy_recovery_durability_overclaim"):
            build_crash_recovery_verification_v2(
                forged, paired, anchor,
                expected_legacy_recovery_sha256=forged["recovery_verification_sha256"],
                expected_paired_receipt_index_sha256=paired["index_sha256"],
                expected_authority_anchor_sha256=anchor["authority_anchor_sha256"],
                expected_authority_root_sha256=ROOT,
            )


if __name__ == "__main__":
    unittest.main()
