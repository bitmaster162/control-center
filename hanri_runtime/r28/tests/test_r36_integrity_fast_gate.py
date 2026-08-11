from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from hanri import steady_integrity_cli as integrity


class R36HeartbeatIntegrityFastGateTests(unittest.TestCase):
    def _heavy(self, root: Path) -> list[Path]:
        paths = [
            root / "latest_ai_state.json",
            root / "latest_archive_causal_spine.json",
            root / "latest_archive_scope_certificate.json",
        ]
        for index, path in enumerate(paths, start=1):
            path.write_bytes((f"heavy-r36-{index}-" * 128).encode("ascii"))
        return paths

    def _context(
        self,
        paths: list[Path],
        *,
        full_verified_at: str | None,
        include_stats: bool = True,
    ) -> dict[str, object]:
        expected = integrity._heavy_snapshot_raw_sha256(paths)
        projection: dict[str, object] = {
            "heavy_snapshot_raw_sha256": expected,
            "heavy_snapshot_full_verified_at": full_verified_at,
        }
        if include_stats:
            projection["heavy_snapshot_stat_checkpoint"] = integrity._heavy_snapshot_stat_checkpoint(paths)
        return {
            "previous_projection": projection,
            "heavy_paths": paths,
        }

    def _config(self) -> dict[str, object]:
        return {
            "integrity_full_rehash_interval_seconds": 900,
            "archive_frontier": {
                "enabled": True,
                "scan_interval_seconds": 900,
            },
        }

    def test_unchanged_stat_checkpoint_within_ttl_skips_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            verified_at = integrity.core.iso_utc()
            context = self._context(paths, full_verified_at=verified_at)

            with (
                mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)),
                mock.patch.object(
                    integrity,
                    "_heavy_snapshot_raw_sha256",
                    side_effect=AssertionError("full SHA must not run on valid cached stat gate"),
                ),
            ):
                eligible, reason, result = integrity.fast_path_context_integrity(
                    root / "config.json", self._config()
                )

            self.assertTrue(eligible)
            self.assertEqual(reason, "BASE_OK")
            self.assertEqual(result["heavy_snapshot_integrity_mode"], integrity.CACHED_INTEGRITY_MODE)
            self.assertFalse(result["heavy_snapshot_full_sha_performed"])
            self.assertEqual(result["heavy_snapshot_bytes_hashed"], 0)
            self.assertIsNone(result["heavy_snapshot_integrity_refresh_reason"])

    def test_stat_change_forces_full_sha_and_matching_bytes_refresh_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            verified_at = integrity.core.iso_utc()
            context = self._context(paths, full_verified_at=verified_at)
            paths[0].touch()

            with mock.patch.object(
                integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)
            ):
                eligible, reason, result = integrity.fast_path_context_integrity(
                    root / "config.json", self._config()
                )

            self.assertTrue(eligible)
            self.assertEqual(reason, "BASE_OK")
            self.assertEqual(result["heavy_snapshot_integrity_mode"], integrity.INTEGRITY_MODE)
            self.assertTrue(result["heavy_snapshot_full_sha_performed"])
            self.assertGreater(result["heavy_snapshot_bytes_hashed"], 0)
            self.assertEqual(result["heavy_snapshot_integrity_refresh_reason"], "STAT_CHECKPOINT_CHANGED")

    def test_stat_change_with_tampered_bytes_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            verified_at = integrity.core.iso_utc()
            context = self._context(paths, full_verified_at=verified_at)
            paths[1].write_bytes(paths[1].read_bytes() + b"tamper")

            with mock.patch.object(
                integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)
            ):
                eligible, reason, result = integrity.fast_path_context_integrity(
                    root / "config.json", self._config()
                )

            self.assertFalse(eligible)
            self.assertEqual(reason, "HEAVY_RAW_SHA_MISMATCH")
            self.assertEqual(result, {})

    def test_missing_stat_checkpoint_rebuilds_with_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            verified_at = integrity.core.iso_utc()
            context = self._context(
                paths,
                full_verified_at=verified_at,
                include_stats=False,
            )

            with mock.patch.object(
                integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)
            ):
                eligible, _, result = integrity.fast_path_context_integrity(
                    root / "config.json", self._config()
                )

            self.assertTrue(eligible)
            self.assertTrue(result["heavy_snapshot_full_sha_performed"])
            self.assertEqual(result["heavy_snapshot_integrity_refresh_reason"], "STAT_CHECKPOINT_MISSING")

    def test_ttl_expiry_forces_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            now = integrity.core.utc_now()
            verified_at = (now - timedelta(seconds=901)).isoformat().replace("+00:00", "Z")
            context = self._context(paths, full_verified_at=verified_at)

            with (
                mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)),
                mock.patch.object(integrity.core, "utc_now", return_value=now),
            ):
                eligible, _, result = integrity.fast_path_context_integrity(
                    root / "config.json", self._config()
                )

            self.assertTrue(eligible)
            self.assertTrue(result["heavy_snapshot_full_sha_performed"])
            self.assertEqual(
                result["heavy_snapshot_integrity_refresh_reason"],
                "FULL_REHASH_INTERVAL_DUE",
            )

    def test_clock_rollback_forces_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            now = integrity.core.utc_now()
            verified_at = (now + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
            context = self._context(paths, full_verified_at=verified_at)

            with (
                mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)),
                mock.patch.object(integrity.core, "utc_now", return_value=now),
            ):
                eligible, _, result = integrity.fast_path_context_integrity(
                    root / "config.json", self._config()
                )

            self.assertTrue(eligible)
            self.assertTrue(result["heavy_snapshot_full_sha_performed"])
            self.assertEqual(result["heavy_snapshot_integrity_refresh_reason"], "CLOCK_ROLLBACK")

    def test_rehash_interval_is_capped_by_archive_scan_cadence(self) -> None:
        config = {
            "integrity_full_rehash_interval_seconds": 3600,
            "archive_frontier": {
                "enabled": True,
                "scan_interval_seconds": 900,
            },
        }
        self.assertEqual(integrity._full_rehash_interval_seconds(config), 900)

    def test_candidate_keeps_authority_fail_closed(self) -> None:
        text = Path(integrity.__file__).read_text(encoding="utf-8")
        self.assertIn('CACHED_INTEGRITY_MODE = "CACHED_STAT_GUARD"', text)
        self.assertIn("fast_path_full_rehash_required_periodically", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("can_trade = True", text)


if __name__ == "__main__":
    unittest.main()
