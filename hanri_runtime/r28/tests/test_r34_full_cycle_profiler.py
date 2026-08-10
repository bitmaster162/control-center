from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hanri import full_cycle_profiler as profiler


class R34FullCycleProfilerTests(unittest.TestCase):
    def _config(self, root: Path) -> dict[str, object]:
        return {
            "program_version": "33.0.0",
            "shadow_only": True,
            "external_model_api": "DENY",
            "can_trade": False,
            "state_root": str(root / "ControlCenterHANRIR33" / "state"),
            "human_output_root": str(root / "Drive" / "HANRI_R33"),
            "lock_file": str(root / "ControlCenterHANRIR33" / "state" / "hanri.lock"),
            "event_inbox": str(root / "events"),
            "decision_inbox": str(root / "decisions"),
            "archive_frontier": {"enabled": True, "origin_paths": [str(root / "origin")], "pivot_paths": [str(root / "pivot")], "current_paths": [str(root / "current")]},
        }

    def test_requires_exact_accepted_r33_safety_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw = self._config(Path(tmp))
            profiler._validate_source_config(raw)
            for key, value in (("program_version", "32.0.0"), ("shadow_only", False), ("external_model_api", "ALLOW"), ("can_trade", True)):
                bad = json.loads(json.dumps(raw))
                bad[key] = value
                with self.assertRaises(Exception):
                    profiler._validate_source_config(bad)

    def test_isolated_config_redirects_only_state_projection_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = self._config(root)
            state = root / "sandbox" / "state"
            projection = root / "sandbox" / "projection"
            isolated = profiler._isolated_config(raw, state, projection)
            self.assertEqual(isolated["state_root"], str(state))
            self.assertEqual(isolated["human_output_root"], str(projection))
            self.assertEqual(isolated["lock_file"], str(state / "hanri.lock"))
            self.assertEqual(isolated["event_inbox"], raw["event_inbox"])
            self.assertEqual(isolated["decision_inbox"], raw["decision_inbox"])
            self.assertEqual(isolated["archive_frontier"], raw["archive_frontier"])

    def test_clone_forces_full_path_only_inside_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "ControlCenterHANRIR33" / "state"
            sandbox = root / "sandbox" / "state"
            live.mkdir(parents=True)
            (live / "archive_inventory_cache.json").write_text('{"cache": 1}', encoding="utf-8")
            for name in profiler.FORCE_FULL_REMOVE:
                (live / name).write_text('{"live": true}', encoding="utf-8")
            (live / "hanri.lock").write_text("lock", encoding="utf-8")
            before = profiler._state_metadata_snapshot(live)
            profiler._clone_live_state(live, sandbox)
            after = profiler._state_metadata_snapshot(live)
            self.assertEqual(before, after)
            self.assertTrue((sandbox / "archive_inventory_cache.json").exists())
            self.assertFalse((sandbox / "hanri.lock").exists())
            for name in profiler.FORCE_FULL_REMOVE:
                self.assertTrue((live / name).exists())
                self.assertFalse((sandbox / name).exists())

    def test_timing_book_reports_elapsed_and_calls(self) -> None:
        book = profiler.TimingBook()
        book.add("stage.example", 0.001)
        book.add("stage.example", 0.002)
        self.assertEqual(book.rounded()["stage.example"], 3.0)
        self.assertEqual(book.call_counts()["stage.example"], 2)

    def test_profiler_source_has_no_scheduler_or_network_calls(self) -> None:
        text = Path(profiler.__file__).read_text(encoding="utf-8")
        self.assertIn("TemporaryDirectory", text)
        self.assertIn("r30.configure_excluded_roots([live_projection_root, sandbox_projection_root])", text)
        self.assertIn('"drive_hanri_r33_writes": 0', text)
        self.assertNotIn("Register-ScheduledTask", text)
        self.assertNotIn("Disable-ScheduledTask", text)
        self.assertNotIn("Enable-ScheduledTask", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("urllib.", text)
        self.assertNotIn("subprocess", text)

    def test_probe_version_is_fixed(self) -> None:
        self.assertEqual(profiler.PROBE_VERSION, "34.0.0-probe-v1")
        self.assertEqual(profiler.EXPECTED_PROGRAM_VERSION, "33.0.0")


if __name__ == "__main__":
    unittest.main()
