from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hanri import archive as legacy
from hanri import archive_scandir
from hanri import archive_sqlite
from hanri import delta_cli as r30
from hanri import sqlite_cli


class R35SQLiteRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        r30.configure_excluded_roots([])

    def tearDown(self) -> None:
        r30.configure_excluded_roots([])

    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        origin = root / "origin"
        pivot = root / "pivot"
        current = root / "current"
        projection = pivot / "HANRI_R35"
        for directory in (origin, pivot, current, projection):
            directory.mkdir(parents=True, exist_ok=True)
        (origin / "old.txt").write_text("old", encoding="utf-8")
        (pivot / "control.json").write_text('{"x": 1}', encoding="utf-8")
        (current / "new.md").write_text("new", encoding="utf-8")
        (projection / "latest_ai_state.json").write_text('{"self": true}', encoding="utf-8")
        return origin, pivot, current, projection

    def _seed(self, root: Path, origin: Path, pivot: Path, current: Path) -> tuple[Path, dict[str, object]]:
        _, cache = archive_scandir.scan_causal_spine_scandir(
            [origin], [pivot], [current], inventory_cache={}, scope_id="TEST_SCOPE"
        )
        seed = root / archive_sqlite.CACHE_JSON_NAME
        seed.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return seed, cache

    @staticmethod
    def _semantic(value: dict[str, object]) -> dict[str, object]:
        result = json.loads(json.dumps(value))
        result.pop("generated_at", None)
        coverage = result.get("coverage_certificate")
        if isinstance(coverage, dict):
            coverage.pop("generated_at", None)
        return result

    def test_migration_preserves_seed_and_exact_r33_spine_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin, pivot, current, projection = self._fixture(root)
            r30.configure_excluded_roots([projection])
            seed, cache = self._seed(root, origin, pivot, current)
            before = seed.read_bytes()
            handle = archive_sqlite.prepare_inventory_handle(seed, lambda path: json.loads(path.read_text(encoding="utf-8")))
            self.assertTrue(handle.migration_performed)
            self.assertTrue(handle.migration_parity_verified)
            self.assertEqual(seed.read_bytes(), before)
            verification = archive_sqlite.verify_inventory(handle.db_path, seed)
            self.assertEqual(verification["status"], "PASS")
            reference, _ = archive_scandir.scan_causal_spine_scandir(
                [origin], [pivot], [current], inventory_cache=cache, scope_id="TEST_SCOPE"
            )
            actual, receipt = archive_sqlite.scan_causal_spine_sqlite(
                [origin], [pivot], [current], inventory_cache=handle, scope_id="TEST_SCOPE"
            )
            archive_sqlite.finalize_inventory_write(seed, receipt)
            self.assertEqual(self._semantic(actual), self._semantic(reference))
            self.assertEqual(seed.read_bytes(), before)
            metrics = archive_sqlite.get_last_scan_metrics()
            self.assertEqual(metrics["inventory_backend"], "SQLITE")
            self.assertTrue(metrics["sqlite_bulk_index_snapshot"])
            self.assertFalse(metrics["sqlite_monolithic_json_rewrite"])

    def test_stale_file_is_inspected_once_and_upserted_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin, pivot, current, projection = self._fixture(root)
            r30.configure_excluded_roots([projection])
            seed, _ = self._seed(root, origin, pivot, current)
            handle = archive_sqlite.prepare_inventory_handle(seed, lambda path: json.loads(path.read_text(encoding="utf-8")))
            changed = current / "new.md"
            changed.write_text("newer", encoding="utf-8")
            with mock.patch.object(legacy, "inspect_file", wraps=legacy.inspect_file) as inspect:
                spine, receipt = archive_sqlite.scan_causal_spine_sqlite(
                    [origin], [pivot], [current], inventory_cache=handle, scope_id="TEST_SCOPE"
                )
            self.assertEqual(inspect.call_count, 1)
            self.assertEqual(receipt.changed_rows, 1)
            self.assertEqual(spine["current"]["sha256"], legacy.sha256_file(changed))
            self.assertEqual(archive_sqlite.verify_inventory(handle.db_path, seed)["status"], "PASS")

    def test_removed_path_is_removed_from_sqlite_next_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin, pivot, current, projection = self._fixture(root)
            r30.configure_excluded_roots([projection])
            seed, _ = self._seed(root, origin, pivot, current)
            handle = archive_sqlite.prepare_inventory_handle(seed, lambda path: json.loads(path.read_text(encoding="utf-8")))
            before = archive_sqlite.verify_inventory(handle.db_path, seed)["entry_count"]
            (pivot / "control.json").unlink()
            _, receipt = archive_sqlite.scan_causal_spine_sqlite(
                [origin], [pivot], [current], inventory_cache=handle, scope_id="TEST_SCOPE"
            )
            after = archive_sqlite.verify_inventory(handle.db_path, seed)["entry_count"]
            self.assertEqual(receipt.removed_rows, 1)
            self.assertEqual(after, before - 1)

    def test_seed_mutation_after_migration_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin, pivot, current, projection = self._fixture(root)
            r30.configure_excluded_roots([projection])
            seed, _ = self._seed(root, origin, pivot, current)
            archive_sqlite.prepare_inventory_handle(seed, lambda path: json.loads(path.read_text(encoding="utf-8")))
            seed.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                archive_sqlite.prepare_inventory_handle(seed, lambda path: json.loads(path.read_text(encoding="utf-8")))

    def test_runtime_wrapper_preserves_r33_guards_and_denies_json_fallback(self) -> None:
        text = Path(sqlite_cli.__file__).read_text(encoding="utf-8")
        self.assertIn('PROGRAM_VERSION = "35.0.0"', text)
        self.assertIn("integrity.install_r32_integrity_guard()", text)
        self.assertIn("r30._atomic_copy = r33._atomic_copy_r33", text)
        self.assertIn("core.scan_causal_spine = archive_sqlite.scan_causal_spine_sqlite", text)
        self.assertIn("archive_inventory_monolithic_json_rewrite", text)
        self.assertIn("archive_inventory_direct_json_fallback", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("can_trade = True", text)

    def test_r35_config_is_isolated_and_denied(self) -> None:
        config_path = Path(__file__).parents[1] / "config" / "r35.windows.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["program_version"], "35.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR35", config["state_root"])
        self.assertIn("HANRI_R35", config["human_output_root"])


if __name__ == "__main__":
    unittest.main()
