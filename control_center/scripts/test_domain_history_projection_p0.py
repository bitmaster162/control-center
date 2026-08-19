from __future__ import annotations

import copy
import unittest

from control_center.scripts.domain_history_projection_p0 import (
    DomainHistoryProjectionError,
    build_domain_history_projection,
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

EFFECTS = {
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


def make_domain_history():
    body = {
        "schema": "bitevo.shadow_domain_history_closure.v1",
        "case_id": "case-r4-001",
        "case_sha256": "a" * 64,
        "case_binding_sha256": "b" * 64,
        "admission_candidate_sha256": "c" * 64,
        "history_verification_sha256": "d" * 64,
        "subject_manifest_sha256": "e" * 64,
        "domain_history_verification_sha256": "f" * 64,
        "case_qualified_replay_input_sha256": "1" * 64,
        "subject_binding_complete": True,
        "admission_binding_complete": True,
        "status": "DOMAIN_HISTORY_CLOSED_SHADOW_ONLY",
        "history_write_performed": False,
        "semantic_acceptance": "NOT_PERFORMED",
        "effects": dict(EFFECTS),
        "execution_authority": "NONE",
        "safety": dict(SAFETY),
        "generated_at": "2026-08-20T03:00:00+07:00",
    }
    body["domain_history_closure_sha256"] = sha256_obj(body)
    return body


class DomainHistoryProjectionP0Tests(unittest.TestCase):
    def test_valid_domain_history_projects_without_authority(self):
        projection = build_domain_history_projection(make_domain_history())
        self.assertEqual(projection["projection_kind"], "NON_AUTHORITY_DOMAIN_HISTORY_PROJECTION")
        self.assertEqual(projection["domain_subject_integrity"], "VERIFIED_SHADOW_ONLY")
        self.assertEqual(projection["admission_integrity"], "VERIFIED_SHADOW_ONLY")
        self.assertFalse(projection["current_truth_promotion_allowed"])
        self.assertFalse(projection["apply"])
        self.assertTrue(all(value is False for value in projection["mutations"].values()))
        self.assertEqual(projection["effect_candidates_created"], 0)
        self.assertEqual(projection["executions_authorized"], 0)
        self.assertFalse(projection["safety"]["can_trade"])
        self.assertEqual(projection["safety"]["capital_permission"], "DENY")

    def test_rehashed_incomplete_subject_binding_is_rejected(self):
        receipt = make_domain_history()
        receipt["subject_binding_complete"] = False
        receipt["domain_history_closure_sha256"] = sha256_obj({k: v for k, v in receipt.items() if k != "domain_history_closure_sha256"})
        with self.assertRaisesRegex(DomainHistoryProjectionError, "domain_subject_binding_incomplete"):
            build_domain_history_projection(receipt)

    def test_rehashed_admission_gap_is_rejected(self):
        receipt = make_domain_history()
        receipt["admission_binding_complete"] = False
        receipt["domain_history_closure_sha256"] = sha256_obj({k: v for k, v in receipt.items() if k != "domain_history_closure_sha256"})
        with self.assertRaisesRegex(DomainHistoryProjectionError, "domain_admission_binding_incomplete"):
            build_domain_history_projection(receipt)

    def test_rehashed_current_truth_effect_is_rejected(self):
        receipt = make_domain_history()
        receipt["effects"]["current_truth_apply"] = True
        receipt["domain_history_closure_sha256"] = sha256_obj({k: v for k, v in receipt.items() if k != "domain_history_closure_sha256"})
        with self.assertRaisesRegex(DomainHistoryProjectionError, "domain_history_effect_boundary_breached:current_truth_apply"):
            build_domain_history_projection(receipt)

    def test_semantic_acceptance_overclaim_is_rejected(self):
        receipt = make_domain_history()
        receipt["semantic_acceptance"] = "PASS"
        receipt["domain_history_closure_sha256"] = sha256_obj({k: v for k, v in receipt.items() if k != "domain_history_closure_sha256"})
        with self.assertRaisesRegex(DomainHistoryProjectionError, "domain_history_semantic_acceptance_overclaim"):
            build_domain_history_projection(receipt)

    def test_tamper_without_rehash_is_rejected(self):
        receipt = make_domain_history()
        receipt["case_id"] = "tampered"
        with self.assertRaisesRegex(DomainHistoryProjectionError, "domain_history_hash_mismatch"):
            build_domain_history_projection(receipt)


if __name__ == "__main__":
    unittest.main()
