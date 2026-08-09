from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hanri import steady_integrity_cli as integrity


class R32SteadyIntegrityTests(unittest.TestCase):
    def _heavy(self, root: Path) -> list[Path]:
        paths = [
            root / "latest_ai_state.json",
            root / "latest_archive_causal_spine.json",
            root / "latest_archive_scope_certificate.json",
        ]
        for index, path in enumerate(paths, start=1):
            path.write_bytes((f"heavy-{index}-" * 64).encode("ascii"))
        return paths

    def _base_context(self, root: Path, paths: list[Path], expected: dict[str, str] | None) -> dict[str, object]:
        return {
            "previous_projection": {
                "heavy_snapshot_raw_sha256": expected,
            },
            "heavy_paths": paths,
        }

    def test_missing_raw_sha_checkpoint_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            context = self._base_context(root, paths, None)
            with mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)):
                eligible, reason, result = integrity.fast_path_context_integrity(root / "config.json", {})
            self.assertFalse(eligible)
            self.assertEqual(reason, "HEAVY_RAW_SHA_CHECKPOINT_MISSING")
            self.assertEqual(result, {})

    def test_modified_heavy_bytes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            expected = integrity._heavy_snapshot_raw_sha256(paths)
            paths[1].write_bytes(paths[1].read_bytes() + b"tamper")
            context = self._base_context(root, paths, expected)
            with mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)):
                eligible, reason, result = integrity.fast_path_context_integrity(root / "config.json", {})
            self.assertFalse(eligible)
            self.assertEqual(reason, "HEAVY_RAW_SHA_MISMATCH")
            self.assertEqual(result, {})

    def test_matching_raw_sha_is_eligible_and_records_hashed_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self._heavy(root)
            expected = integrity._heavy_snapshot_raw_sha256(paths)
            context = self._base_context(root, paths, expected)
            with mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)):
                eligible, reason, result = integrity.fast_path_context_integrity(root / "config.json", {})
            self.assertTrue(eligible)
            self.assertEqual(reason, "BASE_OK")
            self.assertEqual(result["heavy_snapshot_raw_sha256"], expected)
            self.assertEqual(result["heavy_snapshot_bytes_hashed"], sum(path.stat().st_size for path in paths))
            self.assertIn("heavy_snapshot_integrity_elapsed_ms", result)

    def test_process_hashes_heavy_state_once_under_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            paths = self._heavy(state)
            expected = {path.name: "x" * 64 for path in paths}
            context = self._base_context(root, paths, expected)
            config = {
                "state_root": str(state),
                "lock_file": str(state / "hanri.lock"),
                "lock_stale_seconds": 1800,
            }
            with (
                mock.patch.object(integrity.base, "r32_load_config", return_value=config),
                mock.patch.object(integrity, "_BASE_FAST_CONTEXT", return_value=(True, "BASE_OK", context)) as preflight,
                mock.patch.object(integrity, "_heavy_snapshot_raw_sha256", return_value=expected) as heavy_sha,
                mock.patch.object(integrity, "run_fast_path_integrity", return_value={"heartbeat_fast_path": True}) as run_fast,
            ):
                result = integrity.r32_process_once_integrity(root / "config.json")
            self.assertTrue(result["heartbeat_fast_path"])
            self.assertEqual(preflight.call_count, 2)
            self.assertEqual(heavy_sha.call_count, 1)
            run_fast.assert_called_once()

    def test_raw_sha_is_streaming_byte_integrity_not_json_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest_ai_state.json"
            payload = b"not-json-but-exact-bytes"
            path.write_bytes(payload)
            result = integrity._heavy_snapshot_raw_sha256([path])
            self.assertEqual(result[path.name], hashlib.sha256(payload).hexdigest())
            self.assertEqual(integrity.INTEGRITY_MODE, "STREAMING_SHA256_NO_JSON_PARSE")

    def test_integrity_wrapper_enriches_full_projection_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "drive"
            target.mkdir()
            paths = self._heavy(root)
            base_receipt = {
                "schema_version": 1,
                "program_version": "32.0.0",
                "material_policy": {},
                "can_trade": False,
            }
            with mock.patch.object(integrity, "_BASE_COPY_OUTPUTS", return_value=base_receipt):
                receipt = integrity.copy_latest_outputs_r32_integrity(root, target)
            self.assertEqual(receipt["heavy_snapshot_integrity_mode"], integrity.INTEGRITY_MODE)
            self.assertEqual(receipt["integrity_policy_version"], integrity.INTEGRITY_POLICY_VERSION)
            self.assertEqual(receipt["heavy_snapshot_bytes_hashed"], sum(path.stat().st_size for path in paths))
            self.assertEqual(set(receipt["heavy_snapshot_raw_sha256"]), {path.name for path in paths})
            self.assertTrue(receipt["material_policy"]["fast_path_streaming_sha256_integrity"])
            self.assertEqual(receipt["material_policy"]["fast_path_heavy_sha_passes"], 1)
            self.assertFalse(receipt["material_policy"]["heavy_json_parse_required_on_fast_path"])
            self.assertFalse(receipt["can_trade"])

    def test_integrity_layer_does_not_add_effect_authority(self) -> None:
        text = Path(integrity.__file__).read_text(encoding="utf-8")
        self.assertIn('INTEGRITY_MODE = "STREAMING_SHA256_NO_JSON_PARSE"', text)
        self.assertIn("base.install_r32_guard()", text)
        self.assertIn("core.process_once = r32_process_once_integrity", text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("can_trade = True", text)


if __name__ == "__main__":
    unittest.main()
