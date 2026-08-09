from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class R31ReleaseGateTests(unittest.TestCase):
    def test_r31_config_is_isolated_and_fail_closed(self) -> None:
        config = json.loads((APP_ROOT / "config" / "r31.windows.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(config["program_version"], "31.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR31", config["state_root"])
        self.assertIn("HANRI_R31", config["human_output_root"])
        self.assertEqual(config["max_recursion_depth"], 2)

    def test_installer_is_bound_to_frozen_release_branch_and_exact_commit_gate(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R31ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedBranch = "hanri/r31-release-candidate"', text)
        self.assertIn("-ExpectedCommit is required with -Apply", text)
        self.assertIn("worktree must be clean", text)
        self.assertIn("does not match expected", text)

    def test_installer_is_side_by_side_and_preserves_accepted_r30(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R31ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn("ControlCenterHANRIR31", text)
        self.assertIn("ControlCenter-HANRI-R31", text)
        self.assertIn("ControlCenter-HANRI-R30", text)
        self.assertNotIn("ControlCenterHANRIR30\\app", text)
        self.assertNotIn("ControlCenterHANRIR30\\state", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r30_files_modified = $false', text)
        self.assertIn('r30_state_modified_by_installer = $false', text)

    def test_previous_failed_r31_instance_is_stopped_before_app_replacement(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R31ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        disable_old = text.find("Disable-ScheduledTask -TaskName $R31TaskName")
        stop_old = text.find("Stop-ScheduledTask -TaskName $R31TaskName")
        move_app = text.find("Move-Item -Force $InstallRoot")
        self.assertGreaterEqual(disable_old, 0)
        self.assertGreater(stop_old, disable_old)
        self.assertGreater(move_app, stop_old)
        self.assertIn("Wait-TaskStopped $R31TaskName 60", text)

    def test_scheduler_completion_gate_handles_running_status_and_long_run(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R31ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn("SchedulerRunningResult = 267009", text)
        self.assertIn("SchedulerExecutionLimitMinutes = 20", text)
        self.assertIn("SchedulerGateTimeoutMinutes = 21", text)
        self.assertIn("fresh run receipt", text)
        self.assertIn("fresh projection receipt", text)
        self.assertIn('TaskState -ne "Running"', text)
        self.assertIn("SCHED_S_TASK_RUNNING", text)

    def test_r30_is_disabled_only_after_complete_r31_readback_and_zero_task_result(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R31ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        last_readback = text.rfind("Assert-R31RuntimeReadback")
        task_result_check = text.rfind("LastTaskResult -ne 0")
        disable_r30 = text.find("Disable-ScheduledTask -TaskName $R30TaskName")
        self.assertGreater(last_readback, 0)
        self.assertGreater(task_result_check, last_readback)
        self.assertGreater(disable_r30, task_result_check)

    def test_installer_and_verifier_cross_check_current_run_envelope(self) -> None:
        for name in ("Install-R31ReleaseCandidate-PS51.ps1", "Verify-R31Runtime-PS51.ps1"):
            text = (APP_ROOT / "scripts" / name).read_text(encoding="ascii")
            for required in (
                "ai_state_run_envelope",
                "latest_ai_state_ignored_top_level_keys",
                "nested_new_events_remains_material",
                "current_run_envelope_always_projected",
                "new_events",
                "new_findings",
                "new_candidates",
                "new_decisions",
                "source_sha256",
                "material_digest",
                "state_sha256",
            ):
                self.assertIn(required, text, f"{required} missing from {name}")
        verifier = (APP_ROOT / "scripts" / "Verify-R31Runtime-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedMaterialPolicy = "31.0.0-ai-state-stability-v2"', verifier)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', verifier)

    def test_failure_path_stops_r31_and_restores_r30(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R31ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        catch = text[text.rfind("catch {"):]
        self.assertIn("Disable-ScheduledTask -TaskName $R31TaskName", catch)
        self.assertIn("Stop-ScheduledTask -TaskName $R31TaskName", catch)
        self.assertIn("Enable-ScheduledTask -TaskName $R30TaskName", catch)

    def test_rollback_switches_scheduler_without_deleting_bytes(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R30FromR31.ps1").read_text(encoding="ascii")
        self.assertIn("Disable-ScheduledTask -TaskName $R31TaskName", text)
        self.assertIn("Stop-ScheduledTask -TaskName $R31TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R30TaskName", text)
        self.assertIn("Start-ScheduledTask -TaskName $R30TaskName", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r30_files_deleted = $false', text)
        self.assertIn('r31_files_deleted = $false', text)

    def test_r31_release_entrypoints_are_ascii_only(self) -> None:
        for name in (
            "Install-R31ReleaseCandidate-PS51.ps1",
            "Verify-R31Runtime-PS51.ps1",
            "Restore-R30FromR31.ps1",
        ):
            payload = (APP_ROOT / "scripts" / name).read_bytes()
            self.assertTrue(payload, name)
            self.assertTrue(all(byte < 128 for byte in payload), name)


if __name__ == "__main__":
    unittest.main()
