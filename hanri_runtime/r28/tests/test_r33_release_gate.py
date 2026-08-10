from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class R33ReleaseGateTests(unittest.TestCase):
    def test_installer_is_side_by_side_and_seeds_only_inventory_cache(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R33ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedBranch = "hanri/r33-release-candidate-1.1"', text)
        self.assertIn("ControlCenterHANRIR33", text)
        self.assertIn("ControlCenter-HANRI-R33", text)
        self.assertIn("ControlCenter-HANRI-R32", text)
        self.assertIn('R32CachePath = Join-Path $R32StateRoot "archive_inventory_cache.json"', text)
        self.assertIn('Copy-Item -Force $R32CachePath (Join-Path $StateRoot "archive_inventory_cache.json")', text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r32_files_modified = $false', text)
        self.assertIn('r32_state_modified_by_installer = $false', text)

    def test_cutover_occurs_only_after_full_scope_fast_and_scheduler_pass(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R33ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        full = text.find("Assert-FullMaterialReadback $DirectRuntime")
        fast = text.find("Assert-FastHeartbeatReadback $ScheduledRuntime")
        task_result = text.find("LastTaskResult -ne 0")
        disable_r32 = text.find("Disable-ScheduledTask -TaskName $R32TaskName")
        self.assertGreater(full, 0)
        self.assertGreater(fast, full)
        self.assertGreater(task_result, fast)
        self.assertGreater(disable_r32, task_result)

    def test_full_gate_requires_complete_scope_narrow_exclusion_and_scan_metrics(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R33ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        for required in (
            'Scope.status -ne "COMPLETE"',
            "Scope.coverage_percent",
            "R33 scope denominator mismatch",
            "R33 self projection leaked into archive scope",
            "R33 predecessor R32 evidence is missing",
            "archive_scan_runtime_metrics",
            "runtime scan engine mismatch",
            "runtime scan policy mismatch",
            "runtime scan did not reuse seeded cache",
        ):
            self.assertIn(required, text)

    def test_installer_requires_bounded_atomic_replace_retry_policy(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R33ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedProjectionRetryPolicy = "33.0.0-drive-atomic-replace-retry-v1"', text)
        self.assertIn("projection atomic-replace retry policy mismatch", text)
        self.assertIn("bounded projection retry invariant missing", text)
        self.assertIn("projection direct-overwrite denial missing", text)
        self.assertIn('release = "HANRI_R33_RC1_1"', text)
        self.assertIn('INSTALL_R33_RC1_1_RECEIPT.json', text)

    def test_failure_path_stops_r33_and_restores_r32(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R33ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        catch = text[text.rfind("catch {"):]
        self.assertIn("Disable-ScheduledTask -TaskName $R33TaskName", catch)
        self.assertIn("Stop-ScheduledTask -TaskName $R33TaskName", catch)
        self.assertIn("Enable-ScheduledTask -TaskName $R32TaskName", catch)

    def test_verifier_rechecks_scope_integrity_authority_and_retry_policy(self) -> None:
        text = (APP_ROOT / "scripts" / "Verify-R33Runtime-PS51.ps1").read_text(encoding="ascii")
        for required in (
            "receipt_fast_path_true",
            "receipt_integrity_verified",
            "state_shadow_only",
            "state_repo_writes_false",
            "projection_scan_policy",
            "projection_scan_engine",
            "projection_retry_policy",
            "projection_retry_bounded",
            "projection_direct_overwrite_denied",
            "projection_streaming_integrity_true",
            "scope_complete",
            "scope_coverage_100",
            "scope_excludes_r33_projection",
            "scope_retains_r32_predecessor",
            "install_projection_retry_policy",
            "install_direct_scan_metrics_present",
            "install_r32_not_modified",
            "install_cutover_order_proven",
        ):
            self.assertIn(required, text)
        self.assertIn('INSTALL_R33_RC1_1_RECEIPT.json', text)
        self.assertIn('release = "HANRI_R33_RC1_1"', text)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', text)

    def test_rollback_restores_r32_without_deleting_bytes(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R32FromR33.ps1").read_text(encoding="ascii")
        self.assertIn("Disable-ScheduledTask -TaskName $R33TaskName", text)
        self.assertIn("Stop-ScheduledTask -TaskName $R33TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R32TaskName", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r32_files_deleted = $false', text)
        self.assertIn('r33_files_deleted = $false', text)

    def test_r33_release_scripts_are_ascii_only(self) -> None:
        for name in (
            "Install-R33ReleaseCandidate-PS51.ps1",
            "Verify-R33Runtime-PS51.ps1",
            "Restore-R32FromR33.ps1",
        ):
            data = (APP_ROOT / "scripts" / name).read_bytes()
            self.assertTrue(all(byte < 128 for byte in data), name)


if __name__ == "__main__":
    unittest.main()
