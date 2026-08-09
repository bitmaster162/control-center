from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hanri.delta_cli import (
    ACTOR,
    HUMAN_LABEL,
    configure_excluded_roots,
    copy_latest_outputs_delta,
    iter_files_excluding_projection,
    material_digest,
    r30_archive_frontier_event,
    r30_render_human_digest,
    r30_snapshot_event,
)


class R30DeltaProjectionTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_excluded_roots([])

    def test_active_projection_is_not_reingested_as_archive_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pivot = root / "00_CONTROL"
            self_output = pivot / "HANRI_R30"
            other = pivot / "OTHER"
            self_output.mkdir(parents=True)
            other.mkdir(parents=True)
            (self_output / "latest_ai_state.json").write_text("{}", encoding="utf-8")
            (other / "authority.json").write_text("{}", encoding="utf-8")

            configure_excluded_roots([self_output])
            files = list(iter_files_excluding_projection([pivot]))
            names = {path.name for path in files}

            self.assertIn("authority.json", names)
            self.assertNotIn("latest_ai_state.json", names)

    def test_material_digest_ignores_only_generated_at_and_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.json"
            second = root / "second.json"
            changed = root / "changed.json"
            first.write_text(
                json.dumps({
                    "generated_at": "2026-08-09T00:00:00Z",
                    "run_id": "a",
                    "nested": {"generated_at": "old", "value": 7},
                }),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps({
                    "generated_at": "2026-08-10T00:00:00Z",
                    "run_id": "b",
                    "nested": {"generated_at": "new", "value": 7},
                }),
                encoding="utf-8",
            )
            changed.write_text(
                json.dumps({
                    "generated_at": "2026-08-10T00:00:00Z",
                    "run_id": "c",
                    "nested": {"generated_at": "new", "value": 8},
                }),
                encoding="utf-8",
            )

            self.assertEqual(material_digest(first), material_digest(second))
            self.assertNotEqual(material_digest(first), material_digest(changed))

    def test_heavy_snapshot_is_skipped_on_no_material_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state"
            target = root / "drive"
            source.mkdir()
            target.mkdir()
            heavy = source / "latest_ai_state.json"
            heartbeat = source / "latest_run_receipt.json"

            heavy.write_text(
                json.dumps({"generated_at": "t1", "run_id": "r1", "value": 1}),
                encoding="utf-8",
            )
            heartbeat.write_text(json.dumps({"run_id": "r1"}), encoding="utf-8")
            first = copy_latest_outputs_delta(source, target)
            self.assertIn("latest_ai_state.json", first["copied"])
            first_destination = (target / "latest_ai_state.json").read_text(encoding="utf-8")

            heavy.write_text(
                json.dumps({"generated_at": "t2", "run_id": "r2", "value": 1}),
                encoding="utf-8",
            )
            heartbeat.write_text(json.dumps({"run_id": "r2"}), encoding="utf-8")
            second = copy_latest_outputs_delta(source, target)

            self.assertIn("latest_ai_state.json", second["skipped_no_material_delta"])
            self.assertGreater(second["bytes_avoided"], 0)
            self.assertEqual(
                (target / "latest_ai_state.json").read_text(encoding="utf-8"),
                first_destination,
            )
            self.assertEqual(
                json.loads((target / "latest_run_receipt.json").read_text(encoding="utf-8"))["run_id"],
                "r2",
            )

    def test_real_heavy_snapshot_delta_is_projected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state"
            target = root / "drive"
            source.mkdir()
            target.mkdir()
            heavy = source / "latest_archive_causal_spine.json"

            heavy.write_text(json.dumps({"generated_at": "t1", "value": 1}), encoding="utf-8")
            copy_latest_outputs_delta(source, target)
            heavy.write_text(json.dumps({"generated_at": "t2", "value": 2}), encoding="utf-8")
            receipt = copy_latest_outputs_delta(source, target)

            self.assertIn("latest_archive_causal_spine.json", receipt["copied"])
            self.assertEqual(
                json.loads((target / "latest_archive_causal_spine.json").read_text(encoding="utf-8"))["value"],
                2,
            )

    def test_projection_receipt_preserves_safety_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state"
            target = root / "drive"
            source.mkdir()
            receipt = copy_latest_outputs_delta(source, target)
            self.assertFalse(receipt["can_trade"])
            self.assertFalse(receipt["self_application"])
            self.assertEqual(receipt["external_model_api_calls"], 0)
            self.assertTrue(receipt["self_projection_excluded_from_archive"])
            self.assertTrue((target / "latest_projection_receipt.json").exists())

    def test_identity_is_r30(self) -> None:
        digest = r30_render_human_digest("run", [], [], {}, {}, [])
        self.assertIn(HUMAN_LABEL, digest.splitlines()[0])
        self.assertNotIn("HANRI R29", digest.splitlines()[0])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(r30_snapshot_event(path, "state")["actor"], ACTOR)

        item = {
            "name": "x.md",
            "path": "/tmp/x.md",
            "sha256": "a" * 64,
            "content_class": "GENERIC_TEXT",
            "content_signature_verified": True,
        }
        pair = {
            "generated_at": "2026-08-09T00:00:00Z",
            "origin": dict(item),
            "current": dict(item),
            "same_name_collisions": [],
        }
        self.assertEqual(r30_archive_frontier_event(pair)["actor"], ACTOR)


if __name__ == "__main__":
    unittest.main()
