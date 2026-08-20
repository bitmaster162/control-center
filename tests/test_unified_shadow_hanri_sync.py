from __future__ import annotations

import copy
import unittest

from scripts.unified_shadow_hanri_sync import (
    EXPECTED_HANRI_BRANCH,
    EXPECTED_HANRI_HEAD,
    HanriShadowError,
    build_hanri_shadow_evidence_receipt,
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


def make_transaction(*, gate: str = "HOLD", action: str = "WAIT") -> dict:
    tx = {
        "schema": "bitevo.unified_shadow_transaction.v2",
        "frozen_at": "2026-08-20T00:25:00+07:00",
        "case_id": "trade-hanri-001",
        "trade_case_sha256": "a" * 64,
        "decision_packet_sha256": "b" * 64,
        "federation_sha256": "c" * 64,
        "route_sha256": "d" * 64,
        "control_plane_sha256": "e" * 64,
        "registered_node_count": 63,
        "system_recommendation": "LONG",
        "control_gate": gate,
        "control_plane_action": action,
        "hanri_freshness": "STALE" if gate == "HOLD" else "FRESH",
        "hanri_attention_required": gate == "HOLD",
        "twin_prediction_status": "UNIQUE",
        "divergence": False,
        "effect_boundary": {
            "executor_enabled": False,
            "current_truth_apply": False,
            "continuity_write": False,
            "runtime_registration": False,
            "external_model_call": False,
            "exchange_call": False,
            "signal": False,
            "order": False,
            "credential_mutation": False,
            "merge": False,
            "deploy": False,
        },
        "semantics": {
            "one_transaction_one_case": True,
            "prediction_is_not_permission": True,
        },
        "safety": dict(SAFETY),
    }
    tx["transaction_sha256"] = sha256_obj(tx)
    return tx


def make_archiveos(*, passed: bool = False) -> dict:
    return {
        "schema": "hanri.archiveos-freshness.qualification/v1",
        "surface": "archive-os",
        "observed_at": "2026-08-13T11:33:00Z",
        "status": "PASS" if passed else "BLOCKED_REVERIFY",
        "operational_status": "OPERATIONAL" if passed else "BLOCKED_REVERIFY",
        "freshness": "CURRENT" if passed else "STALE",
        "current_claim_allowed": passed,
        "promotion_eligible": passed,
        "proof_gap": [] if passed else ["fresh full archive-integrity receipt is missing"],
        "claim_ceiling": {
            "property": "ARCHIVEOS_CURRENT_IMMUTABLE_SOURCE_SET_INTEGRITY",
            "drive_mirror_is_authority": False,
            "archive_tooling_is_archive_engine": False,
            "cached_stat_guard_is_full_integrity": False,
            "runtime_deployment_claim": False,
            "universal_archive_completeness_claim": False,
        },
        "effects": {
            "writes": 0,
            "runtime_mutations": 0,
            "provider_mutations": 0,
            "external_messages": 0,
            "trading_effects": 0,
        },
        "invariants": {
            "can_trade": False,
            "capital_permission": "DENY",
            "self_application": False,
            "auto_dispatch": False,
            "auto_promotion": False,
        },
    }


class UnifiedShadowHanriSyncTests(unittest.TestCase):
    def build(self, transaction=None, archiveos=None, **kwargs):
        return build_hanri_shadow_evidence_receipt(
            make_transaction() if transaction is None else transaction,
            make_archiveos() if archiveos is None else archiveos,
            hanri_branch=kwargs.pop("hanri_branch", EXPECTED_HANRI_BRANCH),
            hanri_head=kwargs.pop("hanri_head", EXPECTED_HANRI_HEAD),
            generated_at=kwargs.pop("generated_at", "2026-08-20T00:26:00+07:00"),
        )

    def test_current_archiveos_block_forces_hanri_hold(self):
        receipt = self.build()
        self.assertEqual(receipt["schema"], "hanri.shadow-evidence-governor.receipt/v1")
        self.assertEqual(receipt["archiveos"]["status"], "BLOCKED_REVERIFY")
        self.assertEqual(receipt["governor"]["gate"], "HOLD")
        self.assertEqual(receipt["governor"]["action"], "WAIT")
        self.assertIn("ARCHIVEOS_BLOCKED_REVERIFY", receipt["governor"]["hold_reasons"])
        self.assertFalse(receipt["governor"]["promotion_eligible"])
        self.assertTrue(all(value is False for value in receipt["effects"].values()))
        self.assertEqual(receipt["safety"]["capital_permission"], "DENY")

    def test_archive_pass_cannot_override_upstream_control_hold(self):
        receipt = self.build(archiveos=make_archiveos(passed=True))
        self.assertEqual(receipt["archiveos"]["status"], "PASS")
        self.assertEqual(receipt["governor"]["gate"], "HOLD")
        self.assertEqual(receipt["governor"]["action"], "WAIT")
        self.assertIn("UPSTREAM_CONTROL_GATE_HOLD", receipt["governor"]["hold_reasons"])

    def test_all_fresh_can_pass_shadow_but_still_cannot_promote(self):
        tx = make_transaction(gate="PASS_SHADOW", action="LONG")
        receipt = self.build(transaction=tx, archiveos=make_archiveos(passed=True))
        self.assertEqual(receipt["governor"]["gate"], "PASS_SHADOW")
        self.assertEqual(receipt["governor"]["action"], "LONG")
        self.assertFalse(receipt["governor"]["promotion_eligible"])
        self.assertFalse(receipt["hanri_source"]["authority_root"])
        self.assertFalse(receipt["hanri_source"]["can_promote_self"])
        self.assertFalse(receipt["knowledge_memory"]["durable_memory_write"])
        self.assertFalse(receipt["knowledge_memory"]["current_truth_write"])

    def test_archive_tooling_cannot_be_upgraded_to_archive_engine(self):
        archive = make_archiveos()
        archive["claim_ceiling"]["archive_tooling_is_archive_engine"] = True
        with self.assertRaisesRegex(HanriShadowError, "archive_tooling_role_overclaim"):
            self.build(archiveos=archive)

    def test_transaction_tamper_is_rejected(self):
        tx = make_transaction()
        tx["system_recommendation"] = "WAIT"
        with self.assertRaisesRegex(HanriShadowError, "transaction_hash_mismatch"):
            self.build(transaction=tx)

    def test_wrong_hanri_head_is_rejected(self):
        with self.assertRaisesRegex(HanriShadowError, "hanri_head_mismatch"):
            self.build(hanri_head="0" * 40)

    def test_effectful_archive_qualification_is_rejected(self):
        archive = copy.deepcopy(make_archiveos())
        archive["effects"]["writes"] = 1
        with self.assertRaisesRegex(HanriShadowError, "archiveos_effect_ceiling_breached:writes"):
            self.build(archiveos=archive)


if __name__ == "__main__":
    unittest.main()
