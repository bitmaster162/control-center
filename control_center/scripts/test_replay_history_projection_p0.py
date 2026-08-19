from __future__ import annotations

import copy
import unittest

from control_center.scripts.replay_history_projection_p0 import (
    ReplayHistoryProjectionError,
    build_replay_history_projection,
    sha256_obj,
)

SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}


def history():
    body = {
        "schema": "bitevo.shadow_history_replay_verification.v1",
        "case_id": "case-r3-001",
        "case_sha256": "1" * 64,
        "case_binding_sha256": "2" * 64,
        "admission_candidate_sha256": "3" * 64,
        "append_candidate_sha256s": tuple(chr(97 + i) * 64 for i in range(6)),
        "final_ledger_sha256": "4" * 64,
        "final_head_event_sha256": "5" * 64,
        "return_dedup_candidate_sha256": "6" * 64,
        "event_types": ("CASE_QUALIFIED", "TWIN_COMMITTED", "DECISION_PACKET", "HUMAN_REVEAL", "OUTCOME_RECEIPT", "RETURN_INTAKE"),
        "human_reveal_count": 1,
        "return_intake_count": 1,
        "status": "HISTORY_CHAIN_VERIFIED_SHADOW_ONLY",
        "history_write_performed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "effects": {
            "registry_write": False,
            "ledger_write": False,
            "return_index_write": False,
            "current_truth_apply": False,
            "runtime_activation": False,
            "executor_dispatch": False,
            "signal": False,
            "order": False,
            "capital_effect": False,
        },
        "execution_authority": "NONE",
        "safety": dict(SAFETY),
        "generated_at": "2026-08-20T02:40:00+07:00",
    }
    body["history_verification_sha256"] = sha256_obj(body)
    return body


class ReplayHistoryProjectionP0Tests(unittest.TestCase):
    def test_valid_history_projects_without_authority_or_mutation(self):
        projection = build_replay_history_projection(history())
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_HISTORY_REPLAY_PROJECTION")
        self.assertEqual(projection["history_integrity"], "VERIFIED_SHADOW_ONLY")
        self.assertTrue(projection["one_case_one_reveal"])
        self.assertTrue(projection["one_return_intake"])
        self.assertFalse(projection["current_truth_promotion_allowed"])
        self.assertFalse(projection["apply"])
        self.assertTrue(all(value is False for value in projection["mutations"].values()))
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertEqual(projection["safety"]["capital_permission"], "DENY")

    def test_tampered_history_hash_is_rejected(self):
        value = history()
        value["final_head_event_sha256"] = "f" * 64
        with self.assertRaisesRegex(ReplayHistoryProjectionError, "history_hash_mismatch"):
            build_replay_history_projection(value)

    def test_rehashed_second_reveal_overclaim_is_rejected(self):
        value = history()
        value["human_reveal_count"] = 2
        value["history_verification_sha256"] = sha256_obj({k: v for k, v in value.items() if k != "history_verification_sha256"})
        with self.assertRaisesRegex(ReplayHistoryProjectionError, "history_reveal_count_invalid"):
            build_replay_history_projection(value)

    def test_rehashed_return_count_overclaim_is_rejected(self):
        value = history()
        value["return_intake_count"] = 2
        value["history_verification_sha256"] = sha256_obj({k: v for k, v in value.items() if k != "history_verification_sha256"})
        with self.assertRaisesRegex(ReplayHistoryProjectionError, "history_return_count_invalid"):
            build_replay_history_projection(value)

    def test_rehashed_current_truth_effect_is_rejected(self):
        value = history()
        value["effects"]["current_truth_apply"] = True
        value["history_verification_sha256"] = sha256_obj({k: v for k, v in value.items() if k != "history_verification_sha256"})
        with self.assertRaisesRegex(ReplayHistoryProjectionError, "history_effect_boundary_breached:current_truth_apply"):
            build_replay_history_projection(value)

    def test_rehashed_semantic_acceptance_is_rejected(self):
        value = history()
        value["semantic_acceptance"] = "PASS"
        value["history_verification_sha256"] = sha256_obj({k: v for k, v in value.items() if k != "history_verification_sha256"})
        with self.assertRaisesRegex(ReplayHistoryProjectionError, "history_semantic_acceptance_overclaim"):
            build_replay_history_projection(value)

    def test_projection_is_deterministic(self):
        first = build_replay_history_projection(history())
        second = build_replay_history_projection(history())
        self.assertEqual(first, second)
        self.assertEqual(first["projection_sha256"], second["projection_sha256"])


if __name__ == "__main__":
    unittest.main()
