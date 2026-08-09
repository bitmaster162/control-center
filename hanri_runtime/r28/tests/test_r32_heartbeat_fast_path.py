from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hanri import cli as core
from hanri import stability_cli as r31
from hanri import steady_cli as r32


class R32HeartbeatFastPathTests(unittest.TestCase):
    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _fixture(
        self,
        root: Path,
        *,
        checkpoint_time: str | None = None,
        current_state: bool = False,
        new_findings: int = 0,
        stop_reasons: list[str] | None = None,
    ) -> tuple[Path, dict[str, Path], str]:
        state = root / "state"
        events = root / "events"
        decisions = root / "decisions"
        drive = root / "drive"
        for path in (state, events, decisions, drive):
            path.mkdir(parents=True, exist_ok=True)

        current = root / "current.json"
        if current_state:
            self._write_json(current, {"value": 2})

        config = {
            "schema_version": 1,
            "program_version": "32.0.0",
            "shadow_only": True,
            "external_model_api": "DENY",
            "can_trade": False,
            "max_recursion_depth": 2,
            "lock_stale_seconds": 1800,
            "state_root": str(state),
            "lock_file": str(state / "hanri.lock"),
            "event_inbox": str(events),
            "decision_inbox": str(decisions),
            "human_output_root": str(drive),
            "current_state_paths": [str(current)] if current_state else [],
            "archive_frontier": {
                "enabled": True,
                "scan_interval_seconds": 900,
                "origin_paths": [],
                "pivot_paths": [str(root / "pivot")],
                "current_paths": [],
            },
        }
        config_path = root / "r32.json"
        self._write_json(config_path, config)
        config_sha = core.sha256_file(config_path)

        ai = state / "latest_ai_state.json"
        self._write_json(ai, {
            "schema_version": 1,
            "program_version": "32.0.0",
            "run_id": "material-run",
            "generated_at": "2026-08-09T18:00:00Z",
            "mode": "BOUNDED_RECURSIVE_SHADOW",
            "shadow_only": True,
            "new_events": 0,
            "new_findings": new_findings,
            "new_candidates": 0,
            "new_decisions": 0,
            "total_findings": new_findings,
            "total_candidates": 0,
            "pending_human_decisions": 0,
            "stop_reasons": stop_reasons or [],
            "latest_findings": [],
            "latest_candidates": [],
            "secret_findings": [],
            "invariants": {
                "self_application": False,
                "external_model_api_calls": 0,
                "network_calls": 0,
                "source_repository_writes": False,
                "human_approval_required": True,
                "can_trade": False,
            },
        })
        self._write_json(state / "latest_archive_causal_spine.json", {"generated_at": checkpoint_time or core.iso_utc(), "scan_interval_seconds": 900})
        self._write_json(state / "latest_archive_scope_certificate.json", {"generated_at": checkpoint_time or core.iso_utc()})
        self._write_json(state / "latest_regression_suite.json", {"schema_version": 1, "cases": [], "can_trade": False})
        (state / "latest_human_digest.md").write_text(
            "# Human Decision Digest — HANRI R32\n\nRun: `material-run`\n\n## Состояние\n\n- Новых findings: **0**\n- Кандидатов на изменение: **0**\n- Stop signals: **0**\n- `can_trade=false`\n",
            encoding="utf-8",
        )
        self._write_json(state / "processed_event_hashes.json", [])
        self._write_json(state / "processed_decision_hashes.json", [])

        state_sha = core.sha256_file(ai)
        material_digest = r31.material_digest_r31(ai)
        previous_run = {
            "schema_version": 1,
            "program_version": "32.0.0",
            "run_id": "material-run",
            "generated_at": "2026-08-09T18:00:00Z",
            "config_path": str(config_path),
            "config_sha256": config_sha,
            "events_processed": 0,
            "decisions_processed": 0,
            "findings_generated": new_findings,
            "candidates_generated": 0,
            "stop_reasons": stop_reasons or [],
            "state_sha256": state_sha,
            "human_digest_sha256": core.sha256_file(state / "latest_human_digest.md"),
            "external_model_api_calls": 0,
            "self_application": False,
            "can_trade": False,
        }
        self._write_json(state / "latest_run_receipt.json", previous_run)
        previous_projection = {
            "schema_version": 1,
            "program_version": "32.0.0",
            "material_digests": {"latest_ai_state.json": material_digest},
            "ai_state_run_envelope": {
                "source_sha256": state_sha,
                "material_digest": material_digest,
                "run_id": "material-run",
                "generated_at": "2026-08-09T18:00:00Z",
                "new_events": 0,
                "new_findings": new_findings,
                "new_candidates": 0,
                "new_decisions": 0,
                "total_findings": new_findings,
                "total_candidates": 0,
                "pending_human_decisions": 0,
                "stop_reasons": stop_reasons or [],
                "shadow_only": True,
                "self_application": False,
                "external_model_api_calls": 0,
                "source_repository_writes": False,
                "can_trade": False,
            },
            "archive_scan_checkpoint": {
                "generated_at": checkpoint_time or core.iso_utc(),
                "scan_interval_seconds": 900,
            },
            "can_trade": False,
        }
        self._write_json(state / "latest_projection_receipt.json", previous_projection)
        return config_path, {"state": state, "events": events, "decisions": decisions, "drive": drive, "current": current, "ai": ai}, state_sha

    def test_fast_path_reuses_heavy_state_without_reading_or_hashing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, paths, state_sha = self._fixture(Path(tmp))
            ai_before = paths["ai"].read_bytes()
            mtime_before = paths["ai"].stat().st_mtime_ns
            raw_sha = core.sha256_file

            def guarded_sha(path: Path, *args: object, **kwargs: object) -> str:
                if Path(path).name in {"latest_ai_state.json", "latest_archive_causal_spine.json", "latest_archive_scope_certificate.json"}:
                    raise AssertionError(f"heavy file hashed on fast path: {path}")
                return raw_sha(path, *args, **kwargs)

            with mock.patch.object(core, "sha256_file", side_effect=guarded_sha):
                result = r32.r32_process_once(config_path)

            self.assertTrue(result["heartbeat_fast_path"])
            self.assertTrue(result["material_state_reused"])
            self.assertEqual(result["state_sha256"], state_sha)
            self.assertEqual(paths["ai"].read_bytes(), ai_before)
            self.assertEqual(paths["ai"].stat().st_mtime_ns, mtime_before)

            projection = json.loads((paths["state"] / "latest_projection_receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(projection["heartbeat_fast_path"])
            self.assertEqual(projection["ai_state_run_envelope"]["run_id"], result["run_id"])
            self.assertEqual(projection["ai_state_run_envelope"]["source_sha256"], state_sha)
            self.assertIn("latest_ai_state.json", projection["skipped_no_material_delta"])
            self.assertIn("latest_archive_causal_spine.json", projection["heavy_snapshot_files_not_read"])
            self.assertGreater(projection["ai_state_rewrite_bytes_avoided"], 0)
            self.assertFalse(projection["can_trade"])

    def test_repeated_fast_path_preserves_original_material_state_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, paths, _ = self._fixture(Path(tmp))
            first = r32.r32_process_once(config_path)
            second = r32.r32_process_once(config_path)
            self.assertNotEqual(first["run_id"], second["run_id"])
            projection = json.loads((paths["state"] / "latest_projection_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(projection["material_state_run_id"], "material-run")
            self.assertEqual(projection["ai_state_run_envelope"]["material_state_run_id"], "material-run")

    def test_new_event_forces_full_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, paths, _ = self._fixture(Path(tmp))
            self._write_json(paths["events"] / "new.json", {"event": "new"})
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_new_decision_forces_full_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, paths, _ = self._fixture(Path(tmp))
            self._write_json(paths["decisions"] / "new.json", {"decision": "new"})
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_current_state_drift_forces_full_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, _ = self._fixture(Path(tmp), current_state=True)
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_archive_scan_due_forces_full_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, _ = self._fixture(Path(tmp), checkpoint_time="2000-01-01T00:00:00Z")
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_prior_finding_surface_forces_one_full_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, _ = self._fixture(Path(tmp), new_findings=1)
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_prior_stop_reason_forces_one_full_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, _, _ = self._fixture(Path(tmp), stop_reasons=["HOLD"])
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_bad_state_sha_forces_full_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, paths, _ = self._fixture(Path(tmp))
            run_path = paths["state"] / "latest_run_receipt.json"
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["state_sha256"] = "0" * 64
            self._write_json(run_path, run)
            with mock.patch.object(r32, "_RAW_PROCESS_ONCE", return_value={"fallback": True}) as fallback:
                result = r32.r32_process_once(config_path)
            self.assertEqual(result, {"fallback": True})
            fallback.assert_called_once_with(config_path)

    def test_status_reports_current_heartbeat_without_rehashing_material_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path, paths, _ = self._fixture(Path(tmp))
            result = r32.r32_process_once(config_path)
            raw_sha = core.sha256_file

            def guarded_sha(path: Path, *args: object, **kwargs: object) -> str:
                if Path(path).name == "latest_ai_state.json":
                    raise AssertionError("status rehashed heavy AI-state")
                return raw_sha(path, *args, **kwargs)

            with mock.patch.object(core, "sha256_file", side_effect=guarded_sha):
                status = r32.r32_status(config_path)
            self.assertEqual(status["run_id"], result["run_id"])
            self.assertEqual(status["material_state_run_id"], "material-run")
            self.assertTrue(status["heartbeat_fast_path"])
            self.assertFalse(status["can_trade"])

    def test_identity_and_authority_remain_fail_closed(self) -> None:
        self.assertEqual(r32.PROGRAM_VERSION, "32.0.0")
        digest = r32.r32_render_human_digest("run", [], [], {}, {}, [])
        self.assertIn("HANRI R32", digest.splitlines()[0])
        self.assertNotIn("HANRI R31", digest.splitlines()[0])
        text = Path(r32.__file__).read_text(encoding="utf-8")
        self.assertIn("r31.install_r31_guard()", text)
        self.assertIn('"external_model_api_calls": 0', text)
        self.assertIn('"self_application": False', text)
        self.assertIn('"can_trade": False', text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)


if __name__ == "__main__":
    unittest.main()
