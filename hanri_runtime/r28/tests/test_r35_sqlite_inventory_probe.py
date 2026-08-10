from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hanri import sqlite_inventory_probe as probe


class R35SQLiteInventoryProbeTests(unittest.TestCase):
    def _record(self, path: Path, sha: str = "a" * 64) -> dict[str, object]:
        return {
            "path": str(path),
            "name": path.name,
            "suffix": path.suffix,
            "size_bytes": 5,
            "mtime_utc": "2026-08-10T00:00:00Z",
            "sha256": sha,
            "content_class": "GENERIC_TEXT",
            "content_signature_verified": True,
            "full_text_read": True,
            "text_characters_read": 5,
            "line_count_read": 1,
            "first_nonempty_lines": ["hello"],
            "last_nonempty_lines": ["hello"],
        }

    def test_config_gate_is_fail_closed(self) -> None:
        good = {"program_version": "33.0.0", "shadow_only": True, "external_model_api": "DENY", "can_trade": False}
        probe._validate_config(good)
        for key, value in (("program_version", "32.0.0"), ("shadow_only", False), ("external_model_api", "ALLOW"), ("can_trade", True)):
            bad = dict(good)
            bad[key] = value
            with self.assertRaises(Exception):
                probe._validate_config(bad)

    def test_sqlite_import_preserves_logical_cache_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.json"
            record = self._record(path)
            cache = {str(path).casefold(): {"size_bytes": 5, "mtime_ns": 123, "record": record}}
            conn = probe._create_db(root / "cache.sqlite3")
            try:
                probe._import_cache(conn, cache)
                self.assertEqual(probe._cache_logical_sha(cache), probe._db_logical_sha(conn))
            finally:
                conn.close()

    def test_sqlite_hit_uses_indexed_record_without_fresh_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.json"
            record = self._record(path)
            cache = {str(path).casefold(): {"size_bytes": 5, "mtime_ns": 123, "record": record}}
            conn = probe._create_db(root / "cache.sqlite3")
            try:
                probe._import_cache(conn, cache)
                rows, hits, misses, changed = probe._classify_sqlite(conn, [(path, 5, 123)], {})
                self.assertEqual((hits, misses, changed), (1, 0, 0))
                self.assertEqual(rows[0]["sha256"], record["sha256"])
            finally:
                conn.close()

    def test_sqlite_stale_row_upserts_shared_fresh_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.json"
            old = self._record(path, "a" * 64)
            fresh = self._record(path, "b" * 64)
            cache = {str(path).casefold(): {"size_bytes": 5, "mtime_ns": 123, "record": old}}
            conn = probe._create_db(root / "cache.sqlite3")
            try:
                probe._import_cache(conn, cache)
                rows, hits, misses, changed = probe._classify_sqlite(conn, [(path, 5, 124)], {str(path).casefold(): fresh})
                conn.commit()
                self.assertEqual((hits, misses, changed), (0, 1, 1))
                self.assertEqual(rows[0]["sha256"], fresh["sha256"])
                stored = conn.execute("SELECT mtime_ns,sha256 FROM inventory WHERE path_key=?", (str(path).casefold(),)).fetchone()
                self.assertEqual(stored, (124, fresh["sha256"]))
            finally:
                conn.close()

    def test_probe_source_contains_no_runtime_or_network_authority(self) -> None:
        text = Path(probe.__file__).read_text(encoding="utf-8")
        self.assertIn("TemporaryDirectory", text)
        self.assertIn('"runtime_install_or_promotion": False', text)
        self.assertIn('"sqlite_location": "TEMP_ONLY"', text)
        for forbidden in ("Register-ScheduledTask", "Enable-ScheduledTask", "Disable-ScheduledTask", "requests.", "urllib.", "subprocess"):
            self.assertNotIn(forbidden, text)

    def test_probe_version_is_fixed(self) -> None:
        self.assertEqual(probe.PROBE_VERSION, "35.0.0-probe-v1")
        self.assertEqual(probe.EXPECTED_PROGRAM_VERSION, "33.0.0")


if __name__ == "__main__":
    unittest.main()
