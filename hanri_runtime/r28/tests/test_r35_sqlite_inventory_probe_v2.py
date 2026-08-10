from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hanri import sqlite_inventory_probe as v1
from hanri import sqlite_inventory_probe_v2 as v2


class R35SQLiteInventoryProbeV2Tests(unittest.TestCase):
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

    def test_bulk_hit_path_matches_v1_and_uses_single_select(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / f"{i}.json" for i in range(3)]
            cache = {
                str(path).casefold(): {"size_bytes": 5, "mtime_ns": 123, "record": self._record(path, str(i) * 64)}
                for i, path in enumerate(paths, start=1)
            }
            metadata = [(path, 5, 123) for path in paths]
            conn = v1._create_db(root / "cache.sqlite3")
            try:
                v1._import_cache(conn, cache)
                traces: list[str] = []
                conn.set_trace_callback(traces.append)
                bulk = v2._classify_sqlite_bulk(conn, metadata, {})
                conn.set_trace_callback(None)
                point = v1._classify_sqlite(conn, metadata, {})
                self.assertEqual(bulk, point)
                selects = [sql for sql in traces if sql.lstrip().upper().startswith("SELECT")]
                self.assertEqual(len(selects), 1)
                self.assertNotIn("WHERE path_key", selects[0])
            finally:
                conn.close()

    def test_bulk_stale_row_upserts_only_changed_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "a.json"
            old = self._record(path, "a" * 64)
            fresh = self._record(path, "b" * 64)
            cache = {str(path).casefold(): {"size_bytes": 5, "mtime_ns": 123, "record": old}}
            conn = v1._create_db(root / "cache.sqlite3")
            try:
                v1._import_cache(conn, cache)
                rows, hits, misses, changed = v2._classify_sqlite_bulk(
                    conn, [(path, 5, 124)], {str(path).casefold(): fresh}
                )
                conn.commit()
                self.assertEqual((hits, misses, changed), (0, 1, 1))
                self.assertEqual(rows[0]["sha256"], fresh["sha256"])
                stored = conn.execute("SELECT mtime_ns,sha256 FROM inventory WHERE path_key=?", (str(path).casefold(),)).fetchone()
                self.assertEqual(stored, (124, fresh["sha256"]))
            finally:
                conn.close()

    def test_v2_probe_identity_and_safety_inheritance(self) -> None:
        self.assertEqual(v2.PROBE_VERSION, "35.1.0-probe-v1")
        self.assertEqual(v2.SQLITE_STRATEGY, "BULK_INDEX_SNAPSHOT_SINGLE_SELECT_PLUS_CHANGED_ROW_UPSERT")
        text = Path(v2.__file__).read_text(encoding="utf-8")
        for forbidden in ("Register-ScheduledTask", "Enable-ScheduledTask", "Disable-ScheduledTask", "requests.", "urllib.", "subprocess"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
