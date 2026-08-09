from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hanri import archive_scan_profiler as profiler


class R33ArchiveScanProfilerTests(unittest.TestCase):
    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")

    def _cache_row(self, path: Path, *, stale: bool = False) -> dict[str, object]:
        stat = path.stat()
        return {
            "size_bytes": stat.st_size + (1 if stale else 0),
            "mtime_ns": stat.st_mtime_ns,
            "record": {"path": str(path.resolve()), "sha256": "x" * 64},
        }

    def _fixture(self, root: Path) -> tuple[Path, Path]:
        state = root / "ControlCenterHANRIR32" / "state"
        origin = root / "origin"
        pivot = root / "pivot"
        current = root / "current"
        for directory in (state, origin, pivot, current):
            directory.mkdir(parents=True, exist_ok=True)

        origin_file = origin / "a.txt"
        pivot_file = pivot / "b.json"
        current_file = current / "c.md"
        origin_file.write_text("origin", encoding="utf-8")
        pivot_file.write_text("{}", encoding="utf-8")
        current_file.write_text("current", encoding="utf-8")
        (current / "ignored.bin").write_bytes(b"binary")

        cache = {
            str(origin_file.resolve()).casefold(): self._cache_row(origin_file),
            str(pivot_file.resolve()).casefold(): self._cache_row(pivot_file),
            str(current_file.resolve()).casefold(): self._cache_row(current_file, stale=True),
        }
        self._write_json(state / "archive_inventory_cache.json", cache)
        self._write_json(
            state / "latest_archive_scope_certificate.json",
            {
                "scope_id": "TEST_R32",
                "coverage_percent": 100.0,
                "coverage_ratio": "3/3",
                "denominator": 3,
                "status": "COMPLETE",
            },
        )
        config = root / "r32.windows.json"
        self._write_json(
            config,
            {
                "program_version": "32.0.0",
                "shadow_only": True,
                "external_model_api": "DENY",
                "can_trade": False,
                "state_root": str(state),
                "archive_frontier": {
                    "enabled": True,
                    "scope_id": "TEST_R32",
                    "scan_interval_seconds": 900,
                    "origin_paths": [str(origin)],
                    "pivot_paths": [str(pivot)],
                    "current_paths": [str(current)],
                },
            },
        )
        return config, state

    def test_probe_counts_hits_and_stale_without_content_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = self._fixture(Path(tmp))
            result = profiler.profile_archive_scan(config)
            totals = result["totals"]
            self.assertEqual(totals["files_seen"], 3)
            self.assertEqual(totals["cache_hits"], 2)
            self.assertEqual(totals["cache_stale"], 1)
            self.assertEqual(totals["cache_missing"], 0)
            self.assertEqual(totals["would_require_content_inspection"], 1)
            self.assertEqual(result["previous_scope_certificate"]["coverage_ratio"], "3/3")
            self.assertTrue(result["safety"]["read_only"])
            self.assertEqual(result["safety"]["writes_performed"], 0)
            self.assertEqual(result["safety"]["file_content_reads_performed"], 0)
            self.assertFalse(result["safety"]["can_trade"])

    def test_probe_does_not_modify_r32_state_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, state = self._fixture(Path(tmp))
            before = {
                path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in state.iterdir()
                if path.is_file()
            }
            profiler.profile_archive_scan(config)
            after = {
                path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in state.iterdir()
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_probe_refuses_authority_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = self._fixture(Path(tmp))
            value = json.loads(config.read_text(encoding="utf-8"))
            value["can_trade"] = True
            config.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "can_trade=false"):
                profiler.profile_archive_scan(config)

    def test_probe_refuses_non_r32_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = self._fixture(Path(tmp))
            value = json.loads(config.read_text(encoding="utf-8"))
            value["state_root"] = str(Path(tmp) / "other" / "state")
            config.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "isolated R32 state root"):
                profiler.profile_archive_scan(config)


if __name__ == "__main__":
    unittest.main()
