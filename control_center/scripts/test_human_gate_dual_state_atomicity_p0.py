from __future__ import annotations

import copy
import unittest

from control_center.scripts.human_gate_dual_state_atomicity_p0 import (
    DualStateAtomicityError,
    NO_EFFECTS,
    REQUIRED_SAFETY,
    build_dual_state_atomicity_verification,
    build_dual_state_commit_candidate,
    build_dual_state_readback_snapshot,
    build_lease_epoch_lineage,
    sha256_obj,
)
from control_center.scripts.dual_state_atomicity_projection_p0 import (
    DualStateProjectionError,
    build_dual_state_atomicity_projection,
)

ROOT = "1" * 64
PREV_LEASE_ID = "2" * 64
CURR_LEASE_ID = "3" * 64
PREV_LEASE_SHA_SEED = "4" * 64
RECOVERY_ANCHOR = "5" * 64
LEGACY_INDEX = "6" * 64
PAIRED_INDEX = "7" * 64
RECEIPT_REF = "8" * 64
COMMIT = "9" * 64
IDEM = "a" * 64
CASE_SHA = "b" * 64
CHALLENGE = "c" * 64
ATOMIC = "d" * 64
PRIOR_HG = "e" * 64
NEXT_HG = "f" * 64
NEXT_INDEX = "0" * 64
BACKEND_TX = "a1" * 32

def lease_fixture(*, current: bool, lease_id: str | None = None, epoch: int | None = None, token: int | None = None, writer: str = "writer-a", previous_sha: str | None = None):
    body = {
        "schema": "control_center.shadow_human_gate_writer_lease_snapshot.v1",
        "lease_id": lease_id or (CURR_LEASE_ID if current else PREV_LEASE_ID),
        "authority_root_sha256": ROOT,
        "writer_id": writer,
        "lease_epoch": epoch if epoch is not None else (4 if current else 3),
        "fencing_token": token if token is not None else (8 if current else 7),
        "bound_state_sha256": PRIOR_HG,
        "bound_generation": 10,
        "issued_at": "2026-08-20T05:10:00+07:00" if current else "2026-08-20T04:40:00+07:00",
        "expires_at": "2026-08-20T05:40:00+07:00" if current else "2026-08-20T05:20:00+07:00",
        "previous_lease_sha256": previous_sha or PREV_LEASE_SHA_SEED,
        "lease_status": "ACTIVE_SHADOW_LEASE_SNAPSHOT",
        "single_active_writer_claim": True,
        "live_lease_backend_proven": False,
        "lease_write_performed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["lease_sha256"] = sha256_obj(body)
    return body

def lineage_fixture():
    previous = lease_fixture(current=False)
    current = lease_fixture(current=True, previous_sha=previous["lease_sha256"])
    lineage = build_lease_epoch_lineage(
        previous, current,
        expected_previous_lease_sha256=previous["lease_sha256"],
        expected_current_lease_sha256=current["lease_sha256"],
        expected_authority_root_sha256=ROOT,
        transition_kind="RENEW",
    )
    return previous, current, lineage

def recovery_fixture(current_lease_sha: str):
    body = {
        "schema": "control_center.shadow_human_gate_crash_recovery_verification.v2",
        "legacy_recovery_verification_sha256": "11" * 32,
        "paired_receipt_index_sha256": PAIRED_INDEX,
        "authority_anchor_sha256": RECOVERY_ANCHOR,
        "authority_root_sha256": ROOT,
        "current_writer_lease_sha256": current_lease_sha,
        "legacy_current_receipt_index_sha256": LEGACY_INDEX,
        "case_id": "case-r9",
        "case_sha256": CASE_SHA,
        "challenge_id": CHALLENGE,
        "approval_verification_sha256": "12" * 32,
        "atomic_consume_verification_sha256": ATOMIC,
        "receipt_candidate_sha256": RECEIPT_REF,
        "commit_id": COMMIT,
        "idempotency_key_sha256": IDEM,
        "receipt_indexed": True,
        "recovery_status": "RECEIPT_INDEXED_DEDUP_NO_RETRY",
        "recovery_action": "DEDUP_AND_ACK_ONLY",
        "paired_receipt_identity_verified": True,
        "authority_root_anchor_consumed": True,
        "cross_plane_anchor_scope": "CONTROL_CENTER_WRITER_LEASE_RECEIPT_INDEX",
        "protocol_status": "FENCING_AND_CRASH_RECOVERY_HARDENED_SHADOW_ONLY",
        "live_writer_backend_proven": False,
        "durable_commit_proven": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["recovery_verification_sha256"] = sha256_obj(body)
    return body

def candidate_fixture():
    _, current, lineage = lineage_fixture()
    recovery = recovery_fixture(current["lease_sha256"])
    candidate = build_dual_state_commit_candidate(
        recovery, lineage,
        expected_recovery_v2_sha256=recovery["recovery_verification_sha256"],
        expected_lease_lineage_sha256=lineage["lease_lineage_sha256"],
        expected_authority_root_sha256=ROOT,
        prior_human_gate_state_sha256=PRIOR_HG,
        next_human_gate_state_sha256=NEXT_HG,
        prior_paired_receipt_index_sha256=PAIRED_INDEX,
        next_paired_receipt_index_sha256=NEXT_INDEX,
        prior_human_gate_generation=10,
        next_human_gate_generation=11,
        prior_receipt_index_generation=2,
        next_receipt_index_generation=3,
        backend_transaction_id_sha256=BACKEND_TX,
    )
    return recovery, lineage, candidate

class R9DualStateAtomicityTests(unittest.TestCase):
    def test_lease_lineage_requires_exact_epoch_and_strict_token(self):
        previous = lease_fixture(current=False)
        bad = lease_fixture(current=True, epoch=5, previous_sha=previous["lease_sha256"])
        with self.assertRaisesRegex(DualStateAtomicityError, "lease_epoch_not_monotonic_plus_one"):
            build_lease_epoch_lineage(previous, bad, expected_previous_lease_sha256=previous["lease_sha256"], expected_current_lease_sha256=bad["lease_sha256"], expected_authority_root_sha256=ROOT, transition_kind="RENEW")
        bad2 = lease_fixture(current=True, token=7, previous_sha=previous["lease_sha256"])
        with self.assertRaisesRegex(DualStateAtomicityError, "fencing_token_not_strictly_monotonic"):
            build_lease_epoch_lineage(previous, bad2, expected_previous_lease_sha256=previous["lease_sha256"], expected_current_lease_sha256=bad2["lease_sha256"], expected_authority_root_sha256=ROOT, transition_kind="RENEW")

    def test_lease_aba_same_id_is_rejected(self):
        previous = lease_fixture(current=False)
        bad = lease_fixture(current=True, lease_id=previous["lease_id"], previous_sha=previous["lease_sha256"])
        with self.assertRaisesRegex(DualStateAtomicityError, "lease_aba_same_lease_id_forbidden"):
            build_lease_epoch_lineage(previous, bad, expected_previous_lease_sha256=previous["lease_sha256"], expected_current_lease_sha256=bad["lease_sha256"], expected_authority_root_sha256=ROOT, transition_kind="RENEW")

    def test_dual_state_after_commit_requires_both_records_advance(self):
        _, _, candidate = candidate_fixture()
        readback = build_dual_state_readback_snapshot(authority_root_sha256=ROOT, human_gate_state_sha256=NEXT_HG, paired_receipt_index_sha256=NEXT_INDEX, human_gate_generation=11, receipt_index_generation=3, observed_at="2026-08-20T05:30:00+07:00")
        result = build_dual_state_atomicity_verification(candidate, readback, expected_dual_commit_candidate_sha256=candidate["dual_commit_candidate_sha256"], expected_readback_sha256=readback["readback_sha256"], expected_authority_root_sha256=ROOT, crash_point="AFTER_ATOMIC_DUAL_WRITE_BEFORE_ACK")
        self.assertEqual(result["protocol_status"], "DUAL_STATE_ATOMICITY_VERIFIED_SHADOW_ONLY")
        self.assertEqual(result["observed_pair_state"], "POST_COMMIT_PAIR_OBSERVED_SHADOW_ONLY")
        self.assertTrue(result["split_state_rejected"])
        self.assertFalse(result["durable_commit_proven"])

    def test_split_state_is_rejected(self):
        _, _, candidate = candidate_fixture()
        split = build_dual_state_readback_snapshot(authority_root_sha256=ROOT, human_gate_state_sha256=NEXT_HG, paired_receipt_index_sha256=PAIRED_INDEX, human_gate_generation=11, receipt_index_generation=2, observed_at="2026-08-20T05:30:00+07:00")
        with self.assertRaisesRegex(DualStateAtomicityError, "dual_state_split_or_unknown_readback_detected"):
            build_dual_state_atomicity_verification(candidate, split, expected_dual_commit_candidate_sha256=candidate["dual_commit_candidate_sha256"], expected_readback_sha256=split["readback_sha256"], expected_authority_root_sha256=ROOT, crash_point="AFTER_ATOMIC_DUAL_WRITE_BEFORE_ACK")

    def test_before_write_requires_prior_pair(self):
        _, _, candidate = candidate_fixture()
        readback = build_dual_state_readback_snapshot(authority_root_sha256=ROOT, human_gate_state_sha256=PRIOR_HG, paired_receipt_index_sha256=PAIRED_INDEX, human_gate_generation=10, receipt_index_generation=2, observed_at="2026-08-20T05:20:00+07:00")
        result = build_dual_state_atomicity_verification(candidate, readback, expected_dual_commit_candidate_sha256=candidate["dual_commit_candidate_sha256"], expected_readback_sha256=readback["readback_sha256"], expected_authority_root_sha256=ROOT, crash_point="BEFORE_ATOMIC_DUAL_WRITE")
        self.assertEqual(result["observed_pair_state"], "PRE_COMMIT_PAIR_OBSERVED")
        self.assertEqual(result["recovery_action"], "FRESH_COMPARE_REQUIRED_BEFORE_NEW_CANDIDATE")

    def test_wrong_retained_candidate_digest_rejected(self):
        _, _, candidate = candidate_fixture()
        readback = build_dual_state_readback_snapshot(authority_root_sha256=ROOT, human_gate_state_sha256=PRIOR_HG, paired_receipt_index_sha256=PAIRED_INDEX, human_gate_generation=10, receipt_index_generation=2, observed_at="2026-08-20T05:20:00+07:00")
        with self.assertRaisesRegex(DualStateAtomicityError, "dual_commit_external_digest_mismatch"):
            build_dual_state_atomicity_verification(candidate, readback, expected_dual_commit_candidate_sha256="ab" * 32, expected_readback_sha256=readback["readback_sha256"], expected_authority_root_sha256=ROOT, crash_point="BEFORE_ATOMIC_DUAL_WRITE")

    def test_projection_cannot_upgrade_durability_or_gate(self):
        _, _, candidate = candidate_fixture()
        readback = build_dual_state_readback_snapshot(authority_root_sha256=ROOT, human_gate_state_sha256=NEXT_HG, paired_receipt_index_sha256=NEXT_INDEX, human_gate_generation=11, receipt_index_generation=3, observed_at="2026-08-20T05:30:00+07:00")
        result = build_dual_state_atomicity_verification(candidate, readback, expected_dual_commit_candidate_sha256=candidate["dual_commit_candidate_sha256"], expected_readback_sha256=readback["readback_sha256"], expected_authority_root_sha256=ROOT, crash_point="AFTER_ATOMIC_DUAL_WRITE_BEFORE_ACK")
        projection = build_dual_state_atomicity_projection(result, expected_atomicity_verification_sha256=result["atomicity_verification_sha256"])
        self.assertEqual(projection["decision"], "HOLD")
        self.assertEqual(projection["action"], "WAIT")
        self.assertEqual(projection["durable_backend"], "NOT_PROVEN")
        self.assertEqual(projection["executions_authorized"], 0)
        forged = copy.deepcopy(result)
        forged["durable_commit_proven"] = True
        forged["atomicity_verification_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "atomicity_verification_sha256"})
        with self.assertRaisesRegex(DualStateProjectionError, "durable_write_overclaim"):
            build_dual_state_atomicity_projection(forged, expected_atomicity_verification_sha256=forged["atomicity_verification_sha256"])

if __name__ == "__main__":
    unittest.main()
