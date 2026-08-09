from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class R32ReleaseGateTests(unittest.TestCase):
    def test_r32_config_is_isolated_and_fail_closed(self) -> None:
        config = json.loads((APP_ROOT / "config" / "r32.windows.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(config["program_version"], "32.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR32", config["state_root"])
        self.assertIn("HANRI_R32", config["human_output_root"])
        self.assertEqual(config["archive_frontier"]["scan_interval_seconds"], 900)

    def test_installer_is_bound_to_frozen_release_branch_and_exact_commit_gate(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R32ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedBranch = "hanri/r32-release-candidate"', text)
        self.assertIn("-ExpectedCommit is required with -Apply", text)
        self.assertIn("worktree must be clean", text)
        self.assertIn("does not match expected", text)

    def test_installer_requires_full_then_fast_before_disabling_r31(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R32ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        full = text.find("Assert-FullMaterialReadback $DirectRuntime")
        fast = text.find("Assert-FastHeartbeatReadback $ScheduledRuntime")
        result = text.find("LastTaskResult -ne 0")
        disable = text.find("Disable-ScheduledTask -TaskName $R31TaskName")
        self.assertGreaterEqual(full, 0)
        self.assertGreater(fast, full)
        self.assertGreater(result, fast)
        self.assertGreater(disable, result)
        self.assertIn("direct_full_material_run_id", text)
        self.assertIn("scheduled_fast_path_verified", text)
        self.assertIn("scheduled_fast_integrity_verified", text)

    def test_scheduler_gate_keeps_running_status_transitional(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R32ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn("SchedulerRunningResult = 267009", text)
        self.assertIn("SchedulerExecutionLimitMinutes = 20", text)
        self.assertIn("SchedulerGateTimeoutMinutes = 21", text)
        self.assertIn('TaskState -ne "Running"', text)
        self.assertIn("SCHED_S_TASK_RUNNING", text)
        self.assertIn("fresh run receipt", text)
        self.assertIn("fresh projection receipt", text)

    def test_installer_and_verifier_check_streaming_integrity_and_lineage(self) -> None:
        for name in ("Install-R32ReleaseCandidate-PS51.ps1", "Verify-R32Runtime-PS51.ps1"):
            text = (APP_ROOT / "scripts" / name).read_text(encoding="ascii")
            for required in (
                "STREAMING_SHA256_NO_JSON_PARSE",
                "32.0.0-steady-integrity-v1",
                "32.0.0-heartbeat-fast-path-v1",
                "heavy_snapshot_raw_sha256",
                "material_state_run_id",
                "heartbeat_fast_path",
                "source_sha256",
                "state_sha256",
                "shadow_only",
                "source_repository_writes",
                "external_model_api_calls",
                "self_application",
                "can_trade",
            ):
                self.assertIn(required, text, f"{required} missing from {name}")

    def test_verifier_hashes_actual_heavy_bytes_against_checkpoint(self) -> None:
        text = (APP_ROOT / "scripts" / "Verify-R32Runtime-PS51.ps1").read_text(encoding="ascii")
        self.assertIn("Get-FileHash $Path -Algorithm SHA256", text)
        self.assertIn("latest_ai_state.json", text)
        self.assertIn("latest_archive_causal_spine.json", text)
        self.assertIn("latest_archive_scope_certificate.json", text)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', text)

    def test_failure_path_stops_r32_and_restores_r31(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R32ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        catch = text[text.rfind("catch {"):]
        self.assertIn("Disable-ScheduledTask -TaskName $R32TaskName", catch)
        self.assertIn("Stop-ScheduledTask -TaskName $R32TaskName", catch)
        self.assertIn("Enable-ScheduledTask -TaskName $R31TaskName", catch)

    def test_rollback_preserves_r31_and_r32_bytes(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R31FromR32.ps1").read_text(encoding="ascii")
        self.assertIn("Disable-ScheduledTask -TaskName $R32TaskName", text)
        self.assertIn("Stop-ScheduledTask -TaskName $R32TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R31TaskName", text)
        self.assertIn("Start-ScheduledTask -TaskName $R31TaskName", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r31_files_deleted = $false', text)
        self.assertIn('r32_files_deleted = $false', text)

    def test_r32_release_entrypoints_are_ascii_only(self) -> None:
        for name in (
            "Install-R32ReleaseCandidate-PS51.ps1",
            "Verify-R32Runtime-PS51.ps1",
            "Restore-R31FromR32.ps1",
        ):
            payload = (APP_ROOT / "scripts" / name).read_bytes()
            self.assertTrue(payload, name)
            self.assertTrue(all(byte < 128 for byte in payload), name)


if __name__ == "__main__":
    unittest.main()
