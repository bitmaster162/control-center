from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hanri import archive as archive_mod
from hanri import cli as core
from hanri.stability_cli import (
    ACTOR,
    HUMAN_LABEL,
    MATERIAL_POLICY_VERSION,
    copy_latest_outputs_stable,
    install_r31_guard,
    material_digest_r31,
    r31_archive_frontier_event,
    r31_render_human_digest,
    r31_snapshot_event,
)


class R31AiStateStabilityTests(unittest.TestCase):
    def _write(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def test_ai_state_top_level_new_events_is_run_ephemeral(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "latest_ai_state.json"
            second = root / "second" / "latest_ai_state.json"
            second.parent.mkdir()
            base = {
                "generated_at": "t1",
                "run_id": "r1",
                "new_events": 3,
                "new_findings": 0,
                "new_candidates": 0,
                "new_decisions": 0,
                "total_findings": 0,
                "total_candidates": 0,
                "pending_human_decisions": 0,
                "stop_reasons": [],
                "archive_causal_spine": {"status": "SPINE_READY", "value": 7},
                "latest_findings": [],
                "latest_candidates": [],
            }
            changed = dict(base)
            changed.update({"generated_at": "t2", "run_id": "r2", "new_events": 1})
            self._write(first, base)
            self._write(second, changed)
            self.assertEqual(material_digest_r31(first), material_digest_r31(second))

    def test_nested_new_events_remains_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "latest_ai_state.json"
            second = root / "other" / "latest_ai_state.json"
            second.parent.mkdir()
            self._write(first, {"new_events": 1, "evidence": {"new_events": 4}})
            self._write(second, {"new_events": 9, "evidence": {"new_events": 5}})
            self.assertNotEqual(material_digest_r31(first), material_digest_r31(second))

    def test_new_findings_remains_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "latest_ai_state.json"
            second = root / "other" / "latest_ai_state.json"
            second.parent.mkdir()
            self._write(first, {"new_events": 1, "new_findings": 0})
            self._write(second, {"new_events": 2, "new_findings": 1})
            self.assertNotEqual(material_digest_r31(first), material_digest_r31(second))

    def test_new_candidates_remains_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "latest_ai_state.json"
            second = root / "other" / "latest_ai_state.json"
            second.parent.mkdir()
            self._write(first, {"new_events": 1, "new_candidates": 0})
            self._write(second, {"new_events": 2, "new_candidates": 1})
            self.assertNotEqual(material_digest_r31(first), material_digest_r31(second))

    def test_stop_reasons_remains_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "latest_ai_state.json"
            second = root / "other" / "latest_ai_state.json"
            second.parent.mkdir()
            self._write(first, {"new_events": 1, "stop_reasons": []})
            self._write(second, {"new_events": 2, "stop_reasons": ["HOLD"]})
            self.assertNotEqual(material_digest_r31(first), material_digest_r31(second))

    def test_projection_skips_ai_state_when_only_run_counter_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state"
            target = root / "drive"
            source.mkdir()
            target.mkdir()
            ai = source / "latest_ai_state.json"
            heartbeat = source / "latest_run_receipt.json"

            self._write(ai, {"generated_at": "t1", "run_id": "r1", "new_events": 3, "total_findings": 0})
            self._write(heartbeat, {"run_id": "r1"})
            first = copy_latest_outputs_stable(source, target)
            self.assertIn("latest_ai_state.json", first["copied"])
            first_ai = (target / "latest_ai_state.json").read_text(encoding="utf-8")

            self._write(ai, {"generated_at": "t2", "run_id": "r2", "new_events": 1, "total_findings": 0})
            self._write(heartbeat, {"run_id": "r2"})
            second = copy_latest_outputs_stable(source, target)

            self.assertIn("latest_ai_state.json", second["skipped_no_material_delta"])
            self.assertGreaterEqual(second["bytes_avoided"], ai.stat().st_size)
            self.assertEqual((target / "latest_ai_state.json").read_text(encoding="utf-8"), first_ai)
            self.assertEqual(json.loads((target / "latest_run_receipt.json").read_text(encoding="utf-8"))["run_id"], "r2")
            self.assertEqual(second["material_policy"]["version"], MATERIAL_POLICY_VERSION)
            self.assertEqual(second["material_policy"]["latest_ai_state_ignored_top_level_keys"], ["new_events"])
            self.assertTrue(second["material_policy"]["nested_new_events_remains_material"])

    def test_real_ai_state_change_is_projected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "state"
            target = root / "drive"
            source.mkdir()
            target.mkdir()
            ai = source / "latest_ai_state.json"
            self._write(ai, {"new_events": 3, "new_findings": 0, "latest_findings": []})
            copy_latest_outputs_stable(source, target)
            self._write(ai, {"new_events": 1, "new_findings": 1, "latest_findings": [{"finding_id": "F-1"}]})
            receipt = copy_latest_outputs_stable(source, target)
            self.assertIn("latest_ai_state.json", receipt["copied"])
            self.assertEqual(json.loads((target / "latest_ai_state.json").read_text(encoding="utf-8"))["new_findings"], 1)

    def test_identity_and_direct_archive_bindings_are_r31(self) -> None:
        install_r31_guard()
        self.assertEqual(core.VERSION, "31.0.0")
        self.assertIs(core.archive_frontier_event, r31_archive_frontier_event)
        self.assertIs(archive_mod.archive_frontier_event, r31_archive_frontier_event)

        digest = r31_render_human_digest("run", [], [], {}, {}, [])
        self.assertIn(HUMAN_LABEL, digest.splitlines()[0])
        self.assertNotIn("HANRI R30", digest.splitlines()[0])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(r31_snapshot_event(path, "state")["actor"], ACTOR)


if __name__ == "__main__":
    unittest.main()
