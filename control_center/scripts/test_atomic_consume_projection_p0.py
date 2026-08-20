from __future__ import annotations

import copy
import unittest

from control_center.scripts.atomic_consume_projection_p0 import (
    AtomicConsumeProjectionError,
    REQUIRED_SAFETY,
    SOURCE_EFFECTS,
    build_atomic_consume_projection,
    sha256_obj,
)


def source_fixture():
    body = {
        "schema": "bitevo.shadow_human_gate_consume_closure.v1",
        "case_id": "case-r7",
        "case_sha256": "1" * 64,
        "challenge_id": "2" * 64,
        "prior_human_gate_state_sha256": "3" * 64,
        "next_human_gate_state_candidate_sha256": "4" * 64,
        "cas_generation_from": 10,
        "cas_generation_to": 11,
        "toctou_guard_model": "COMPARE_AND_SWAP_PRECONDITION",
        "single_use_protocol": "BOUND_BUT_NOT_DURABLY_COMMITTED",
        "status": "HUMAN_GATE_CONSUME_BOUND_SHADOW_ONLY",
        "durable_commit_proven": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "decision": "HOLD",
        "action": "WAIT",
        "effects": dict(SOURCE_EFFECTS),
        "safety": dict(REQUIRED_SAFETY),
    }
    body["human_gate_consume_closure_sha256"] = sha256_obj(body)
    return body


class AtomicConsumeProjectionTests(unittest.TestCase):
    def test_projection_is_non_authority_and_no_write(self):
        source = source_fixture()
        projection = build_atomic_consume_projection(
            source, expected_source_sha256=source["human_gate_consume_closure_sha256"]
        )
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_ATOMIC_CONSUME_PROJECTION")
        self.assertEqual(projection["durable_commit"], "NOT_PERFORMED")
        self.assertFalse(projection["apply"])
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertEqual(projection["decision"], "HOLD")
        self.assertEqual(projection["action"], "WAIT")

    def test_wrong_external_digest_is_rejected(self):
        source = source_fixture()
        with self.assertRaisesRegex(AtomicConsumeProjectionError, "atomic_consume_external_digest_mismatch"):
            build_atomic_consume_projection(source, expected_source_sha256="0" * 64)

    def test_durable_commit_overclaim_is_rejected_even_if_rehashed(self):
        source = source_fixture()
        forged = copy.deepcopy(source)
        forged["durable_commit_proven"] = True
        forged["human_gate_consume_closure_sha256"] = sha256_obj(
            {k: v for k, v in forged.items() if k != "human_gate_consume_closure_sha256"}
        )
        with self.assertRaisesRegex(AtomicConsumeProjectionError, "atomic_consume_durable_commit_overclaim"):
            build_atomic_consume_projection(
                forged, expected_source_sha256=forged["human_gate_consume_closure_sha256"]
            )

    def test_hold_wait_cannot_be_widened(self):
        source = source_fixture()
        source["decision"] = "PASS_SHADOW"
        source["human_gate_consume_closure_sha256"] = sha256_obj(
            {k: v for k, v in source.items() if k != "human_gate_consume_closure_sha256"}
        )
        with self.assertRaisesRegex(AtomicConsumeProjectionError, "atomic_consume_decision_must_remain_hold_wait"):
            build_atomic_consume_projection(
                source, expected_source_sha256=source["human_gate_consume_closure_sha256"]
            )


if __name__ == "__main__":
    unittest.main()
