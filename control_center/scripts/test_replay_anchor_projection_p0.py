import copy
import unittest

from control_center.scripts.replay_anchor_projection_p0 import (
    AUTHORITY_ID,
    MUTATIONS,
    R64_AUTHORITY,
    ReplayAnchorProjectionError,
    authority_root_sha256,
    build_replay_anchor_projection,
    derive_case_binding_sha256,
    sha256_obj,
    validate_replay_anchor_projection,
)


class ReplayAnchorProjectionP0Tests(unittest.TestCase):
    def build(self, **overrides):
        kwargs = {
            "case_id": "trade-r2-001",
            "case_sha256": "a" * 64,
            "evidence_bundle_sha256": "b" * 64,
            "frozen_at": "2026-08-19T15:00:00Z",
        }
        kwargs.update(overrides)
        return build_replay_anchor_projection(**kwargs)

    def test_deterministic_projection_is_non_authority_and_no_effect(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "control_center.shadow_replay_anchor_projection.v1")
        self.assertEqual(first["projection_kind"], "NON_AUTHORITY_REPLAY_ANCHOR_PROJECTION")
        self.assertEqual(first["authority_id"], AUTHORITY_ID)
        self.assertEqual(first["authority_root_basis"], R64_AUTHORITY)
        self.assertEqual(first["authority_root_sha256"], authority_root_sha256())
        self.assertFalse(first["apply"])
        self.assertEqual(first["mutations"], MUTATIONS)
        self.assertTrue(all(value is False for value in first["mutations"].values()))
        self.assertEqual(first["effect_candidates_created"], 0)
        self.assertEqual(first["executions_authorized"], 0)
        self.assertEqual(first["safety"]["execution_authority"], "NONE")
        self.assertFalse(first["safety"]["can_trade"])
        self.assertEqual(first["safety"]["capital_permission"], "DENY")
        self.assertEqual(validate_replay_anchor_projection(first), [])

    def test_case_binding_matches_independent_formula(self):
        projection = self.build()
        expected = derive_case_binding_sha256(
            authority_id=AUTHORITY_ID,
            authority_root_sha256=authority_root_sha256(),
            case_id="trade-r2-001",
            case_sha256="a" * 64,
            evidence_bundle_sha256="b" * 64,
        )
        self.assertEqual(projection["case_binding_sha256"], expected)
        self.assertEqual(
            projection["expected_replay_reference"],
            {
                "expected_authority_id": AUTHORITY_ID,
                "expected_root_sha256": authority_root_sha256(),
                "expected_case_binding_sha256": expected,
            },
        )

    def test_case_frozen_before_r64_root_capture_is_rejected(self):
        with self.assertRaisesRegex(ReplayAnchorProjectionError, "case_freeze_precedes_r64_root_capture"):
            self.build(frozen_at="2026-08-12T04:58:59+07:00")

    def test_bad_hash_input_is_rejected(self):
        with self.assertRaisesRegex(ReplayAnchorProjectionError, "case_sha256_must_be_sha256"):
            self.build(case_sha256="not-a-hash")

    def test_case_or_evidence_change_changes_binding(self):
        base = self.build()
        case_changed = self.build(case_sha256="c" * 64)
        evidence_changed = self.build(evidence_bundle_sha256="d" * 64)
        self.assertNotEqual(base["case_binding_sha256"], case_changed["case_binding_sha256"])
        self.assertNotEqual(base["case_binding_sha256"], evidence_changed["case_binding_sha256"])

    def test_rehashed_apply_or_freshness_overclaim_is_still_rejected(self):
        for mutate, expected in (
            (lambda value: value.__setitem__("apply", True), "apply_forbidden"),
            (
                lambda value: value["freshness"].__setitem__("current_provider_freshness_claimed", True),
                "freshness_overclaim",
            ),
            (
                lambda value: value["mutations"].__setitem__("current_truth", True),
                "mutation_boundary_breached",
            ),
        ):
            forged = copy.deepcopy(self.build())
            mutate(forged)
            forged["projection_sha256"] = sha256_obj(
                {k: v for k, v in forged.items() if k != "projection_sha256"}
            )
            self.assertIn(expected, validate_replay_anchor_projection(forged))


if __name__ == "__main__":
    unittest.main()
