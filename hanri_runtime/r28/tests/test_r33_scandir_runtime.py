from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hanri import archive as legacy
from hanri import archive_scandir as fast
from hanri import delta_cli as r30
from hanri import scandir_cli


class R33ScandirRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        r30.configure_excluded_roots([])

    def tearDown(self) -> None:
        r30.configure_excluded_roots([])

    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        origin = root / "origin"
        pivot = root / "pivot"
        current = root / "current"
        projection = pivot / "HANRI_R33"
        for directory in (origin, pivot, current, projection):
            directory.mkdir(parents=True, exist_ok=True)
        (origin / "old.txt").write_text("old", encoding="utf-8")
        (pivot / "control.json").write_text('{"x": 1}', encoding="utf-8")
        (current / "new.md").write_text("new", encoding="utf-8")
        (current / "ignored.bin").write_bytes(b"ignored")
        (projection / "latest_ai_state.json").write_text('{"self": true}', encoding="utf-8")
        (projection / "latest_run_receipt.json").write_text('{"self": true}', encoding="utf-8")
        return origin, pivot, current, projection

    def _semantic_spine(self, value: dict[str, object]) -> dict[str, object]:
        result = json.loads(json.dumps(value))
        result.pop("generated_at", None)
        coverage = result.get("coverage_certificate")
        if isinstance(coverage, dict):
            coverage.pop("generated_at", None)
        return result

    def test_scandir_spine_matches_legacy_with_projection_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            origin, pivot, current, projection = self._fixture(Path(tmp))
            r30.configure_excluded_roots([projection])
            old_iter = legacy.iter_files
            try:
                legacy.iter_files = r30.iter_files_excluding_projection
                legacy_spine, legacy_cache = legacy.scan_causal_spine(
                    [origin], [pivot], [current], inventory_cache={}, scope_id="TEST_SCOPE"
                )
            finally:
                legacy.iter_files = old_iter
            fast_spine, fast_cache = fast.scan_causal_spine_scandir(
                [origin], [pivot], [current], inventory_cache={}, scope_id="TEST_SCOPE"
            )
            self.assertEqual(self._semantic_spine(fast_spine), self._semantic_spine(legacy_spine))
            self.assertEqual(fast_cache, legacy_cache)
            self.assertEqual(fast_spine["coverage_certificate"]["coverage_ratio"], "3/3")
            self.assertEqual(fast_spine["pivot_files_seen"], 1)

    def test_cache_hits_reuse_records_without_content_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            origin, pivot, current, projection = self._fixture(Path(tmp))
            r30.configure_excluded_roots([projection])
            old_iter = legacy.iter_files
            try:
                legacy.iter_files = r30.iter_files_excluding_projection
                _, cache = legacy.scan_causal_spine(
                    [origin], [pivot], [current], inventory_cache={}, scope_id="TEST_SCOPE"
                )
            finally:
                legacy.iter_files = old_iter
            with mock.patch.object(legacy, "inspect_file", wraps=legacy.inspect_file) as inspect:
                spine, next_cache = fast.scan_causal_spine_scandir(
                    [origin], [pivot], [current], inventory_cache=cache, scope_id="TEST_SCOPE"
                )
            self.assertEqual(inspect.call_count, 0)
            self.assertEqual(next_cache, cache)
            self.assertEqual(spine["coverage_certificate"]["coverage_ratio"], "3/3")

    def test_stale_entry_is_inspected_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            origin, pivot, current, projection = self._fixture(Path(tmp))
            r30.configure_excluded_roots([projection])
            old_iter = legacy.iter_files
            try:
                legacy.iter_files = r30.iter_files_excluding_projection
                _, cache = legacy.scan_causal_spine(
                    [origin], [pivot], [current], inventory_cache={}, scope_id="TEST_SCOPE"
                )
            finally:
                legacy.iter_files = old_iter
            changed = current / "new.md"
            changed.write_text("newer", encoding="utf-8")
            with mock.patch.object(legacy, "inspect_file", wraps=legacy.inspect_file) as inspect:
                _, next_cache = fast.scan_causal_spine_scandir(
                    [origin], [pivot], [current], inventory_cache=cache, scope_id="TEST_SCOPE"
                )
            self.assertEqual(inspect.call_count, 1)
            key = str(changed.resolve()).casefold()
            self.assertEqual(next_cache[key]["record"]["sha256"], legacy.sha256_file(changed))

    def test_transient_projection_lock_retries_atomic_replace_and_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.json"
            destination = root / "drive" / "latest_run_receipt.json"
            source.write_text('{"ok": true}', encoding="utf-8")
            real_replace = scandir_cli.os.replace
            calls = {"count": 0}

            def flaky_replace(src: object, dst: object) -> None:
                calls["count"] += 1
                if calls["count"] <= 2:
                    raise PermissionError(5, "Access is denied")
                real_replace(src, dst)

            with (
                mock.patch.object(scandir_cli.os, "replace", side_effect=flaky_replace),
                mock.patch.object(scandir_cli.time, "sleep") as sleep,
            ):
                scandir_cli._atomic_copy_r33(source, destination)

            self.assertEqual(calls["count"], 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(destination.read_text(encoding="utf-8"), '{"ok": true}')
            self.assertEqual(list(destination.parent.glob("*.tmp-*")), [])

    def test_persistent_projection_lock_fails_closed_after_bounded_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.json"
            destination = root / "drive" / "latest_run_receipt.json"
            source.write_text('{"ok": true}', encoding="utf-8")
            with (
                mock.patch.object(scandir_cli.os, "replace", side_effect=PermissionError(5, "Access is denied")) as replace,
                mock.patch.object(scandir_cli.time, "sleep") as sleep,
            ):
                with self.assertRaises(PermissionError):
                    scandir_cli._atomic_copy_r33(source, destination)
            self.assertEqual(replace.call_count, len(scandir_cli.PROJECTION_REPLACE_DELAYS_SECONDS) + 1)
            self.assertEqual(sleep.call_count, len(scandir_cli.PROJECTION_REPLACE_DELAYS_SECONDS))
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob("*.tmp-*")), [])

    def test_runtime_wrapper_preserves_authority_denials(self) -> None:
        text = Path(scandir_cli.__file__).read_text(encoding="utf-8")
        self.assertIn('PROGRAM_VERSION = "33.0.0"', text)
        self.assertIn("integrity.install_r32_integrity_guard()", text)
        self.assertIn("core.scan_causal_spine = archive_scandir.scan_causal_spine_scandir", text)
        self.assertIn("r30._atomic_copy = _atomic_copy_r33", text)
        self.assertIn("projection_atomic_replace_retry_bounded", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("can_trade = True", text)

    def test_r33_config_is_isolated_and_denied(self) -> None:
        config_path = Path(__file__).parents[1] / "config" / "r33.windows.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["program_version"], "33.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR33", config["state_root"])
        self.assertIn("HANRI_R33", config["human_output_root"])


if __name__ == "__main__":
    unittest.main()
