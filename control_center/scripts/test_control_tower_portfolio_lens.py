from __future__ import annotations

import json
import unittest

from control_tower_portfolio_lens import (
    build_portfolio_lens,
    classify_observation,
)


def fixture():
    return {
        "schema": "ruap.snapshot/v1",
        "generated_at": "2026-09-01T17:40:00+07:00",
        "authority_ceiling": "OBSERVE_ONLY",
        "sources": [
            {
                "id": "s1",
                "provider": "github",
                "locator": "owner/repo@main",
                "observed_at": "2026-09-01T17:39:00+07:00",
            },
            {
                "id": "s2",
                "provider": "vercel",
                "locator": "deployment-1",
                "observed_at": "2026-09-01T17:39:30+07:00",
            },
        ],
        "observations": [
            {
                "subject": "alpha.main",
                "claim": "source exact",
                "class": "PROVIDER_READBACK",
                "source_id": "s1",
                "status": "CURRENT_SOURCE",
                "freshness_required_before_effect": True,
            },
            {
                "subject": "beta.preview",
                "claim": "preview rate limited",
                "class": "PROVIDER_READBACK",
                "source_id": "s2",
                "status": "BLOCKED_EXTERNAL",
                "freshness_required_before_effect": True,
            },
        ],
    }


class PortfolioLensTests(unittest.TestCase):
    def test_provider_current_is_current(self):
        self.assertEqual(
            classify_observation({"class": "PROVIDER_READBACK", "status": "CURRENT_SOURCE"}),
            "CURRENT",
        )

    def test_review_ready_is_partial(self):
        self.assertEqual(
            classify_observation({"class": "PROVIDER_READBACK", "status": "REVIEW_READY_NOT_MERGED"}),
            "PARTIAL",
        )

    def test_hold_is_hold(self):
        self.assertEqual(
            classify_observation({"class": "HANDOFF", "status": "HOLD"}),
            "HOLD",
        )

    def test_blocked_is_blocked(self):
        self.assertEqual(
            classify_observation({"class": "PROVIDER_READBACK", "status": "BLOCKED_EXTERNAL"}),
            "BLOCKED",
        )

    def test_handoff_without_status_is_partial(self):
        self.assertEqual(
            classify_observation({"class": "HANDOFF"}),
            "PARTIAL",
        )

    def test_lens_never_infers_runtime_or_effect(self):
        result = build_portfolio_lens(fixture(), generated_at="2026-09-01T17:40:01+07:00")
        for row in result["entities"]:
            self.assertEqual(row["planes"]["deployment"], "UNKNOWN")
            self.assertEqual(row["planes"]["runtime"], "UNKNOWN")
            self.assertEqual(row["planes"]["effect"], "DENY")
            self.assertEqual(row["planes"]["semantic_authority"], "CONTROL_CENTER_ONLY")

    def test_counts_are_deterministic(self):
        result = build_portfolio_lens(fixture(), generated_at="2026-09-01T17:40:01+07:00")
        self.assertEqual(result["summary"]["counts"]["CURRENT"], 1)
        self.assertEqual(result["summary"]["counts"]["BLOCKED"], 1)
        self.assertEqual(result["summary"]["entity_count"], 2)

    def test_projection_is_deterministic_for_same_input_and_time(self):
        one = build_portfolio_lens(fixture(), generated_at="2026-09-01T17:40:01+07:00")
        two = build_portfolio_lens(fixture(), generated_at="2026-09-01T17:40:01+07:00")
        self.assertEqual(one, two)

    def test_rejects_non_observe_only_snapshot(self):
        value = fixture()
        value["authority_ceiling"] = "EXECUTE"
        with self.assertRaisesRegex(ValueError, "AUTHORITY_CEILING"):
            build_portfolio_lens(value, generated_at="2026-09-01T17:40:01+07:00")

    def test_rejects_unknown_source_reference(self):
        value = fixture()
        value["observations"][0]["source_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "OBSERVATION_SOURCE"):
            build_portfolio_lens(value, generated_at="2026-09-01T17:40:01+07:00")

    def test_rejects_missing_source_identity_fields(self):
        cases = (
            ("provider", "SOURCE_PROVIDER"),
            ("locator", "SOURCE_LOCATOR"),
            ("observed_at", "SOURCE_OBSERVED_AT"),
        )
        for field, error in cases:
            with self.subTest(field=field):
                value = fixture()
                del value["sources"][0][field]
                with self.assertRaisesRegex(ValueError, error):
                    build_portfolio_lens(value, generated_at="2026-09-01T17:40:01+07:00")

    def test_rejects_whitespace_source_identity_fields(self):
        cases = (
            ("id", "SOURCE_IDENTITY"),
            ("provider", "SOURCE_PROVIDER"),
            ("locator", "SOURCE_LOCATOR"),
            ("observed_at", "SOURCE_OBSERVED_AT"),
        )
        for field, error in cases:
            with self.subTest(field=field):
                value = fixture()
                value["sources"][0][field] = "   "
                with self.assertRaisesRegex(ValueError, error):
                    build_portfolio_lens(value, generated_at="2026-09-01T17:40:01+07:00")

    def test_rejects_unsupported_observation_class(self):
        value = fixture()
        value["observations"][0]["class"] = "EXECUTION_AUTHORITY"
        with self.assertRaisesRegex(ValueError, "OBSERVATION_CLASS_UNSUPPORTED"):
            build_portfolio_lens(value, generated_at="2026-09-01T17:40:01+07:00")

    def test_rejects_empty_derived_entity(self):
        for subject in (" .x", ".x", " . "):
            with self.subTest(subject=subject):
                value = fixture()
                value["observations"][0]["subject"] = subject
                with self.assertRaisesRegex(ValueError, "OBSERVATION_ENTITY"):
                    build_portfolio_lens(value, generated_at="2026-09-01T17:40:01+07:00")

    def test_projection_declares_hard_denies(self):
        result = build_portfolio_lens(fixture(), generated_at="2026-09-01T17:40:01+07:00")
        inv = result["invariants"]
        self.assertFalse(inv["can_trade"])
        self.assertEqual(inv["capital_permission"], "DENY")
        self.assertEqual(inv["deploy_permission"], "DENY")
        self.assertTrue(inv["control_center_remains_semantic_authority"])

    def test_ruap_snapshot_identity_uses_canonical_trailing_lf(self):
        from control_tower_portfolio_lens import canonical_json, sha256_ruap_snapshot
        import hashlib
        value = fixture()
        expected = hashlib.sha256(canonical_json(value) + b"\n").hexdigest()
        self.assertEqual(sha256_ruap_snapshot(value), expected)


if __name__ == "__main__":
    unittest.main()
