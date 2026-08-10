from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).parents[1]


class R35ReleaseGateTests(unittest.TestCase):
    def test_installer_is_side_by_side_and_seeds_from_r33_only(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R35ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedBranch = "hanri/r35-sqlite-release-candidate"', text)
        self.assertIn("ControlCenterHANRIR35", text)
        self.assertIn("ControlCenter-HANRI-R35", text)
        self.assertIn("ControlCenter-HANRI-R33", text)
        self.assertIn('R33CachePath = Join-Path $R33StateRoot "archive_inventory_cache.json"', text)
        self.assertIn("Copy-Item -Force $R33CachePath $SeedCachePath", text)
        self.assertNotIn("Remove-Item", text)

    def test_installer_requires_sqlite_migration_scope_and_fast_readback(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R35ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        for required in (
            "sqlite_migration_performed",
            "sqlite_migration_parity_verified",
            "sqlite_seed_json_preserved",
            "sqlite_monolithic_json_rewrite",
            "sqlite_direct_json_fallback",
            "scope certificate is not COMPLETE",
            "predecessor R33 evidence is missing",
            "scheduled run did not use heartbeat fast path",
            "fast heartbeat unexpectedly changed SQLite DB",
            "Disable-ScheduledTask -TaskName $R33TaskName",
            'release = "HANRI_R35_RC1"',
            "INSTALL_R35_RC1_RECEIPT.json",
        ):
            self.assertIn(required, text)

    def test_failure_path_disables_r35_and_restores_r33(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R35ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        catch = text[text.rfind("catch {"):]
        self.assertIn("Disable-ScheduledTask -TaskName $R35TaskName", catch)
        self.assertIn("Stop-ScheduledTask -TaskName $R35TaskName", catch)
        self.assertIn("Enable-ScheduledTask -TaskName $R33TaskName", catch)

    def test_verifier_rechecks_sqlite_scope_integrity_and_authority(self) -> None:
        text = (APP_ROOT / "scripts" / "Verify-R35Runtime-PS51.ps1").read_text(encoding="ascii")
        for required in (
            "receipt_fast_path_true",
            "receipt_integrity_verified",
            "state_repo_writes_false",
            "projection_inventory_backend",
            "projection_inventory_policy",
            "projection_inventory_engine",
            "projection_bulk_snapshot_true",
            "projection_seed_json_preserved",
            "projection_monolithic_json_rewrite_denied",
            "projection_direct_json_fallback_denied",
            "sqlite_admin_pass",
            "sqlite_quick_check_ok",
            "sqlite_migration_parity_verified",
            "scope_complete",
            "scope_coverage_100",
            "scope_excludes_r35_projection",
            "scope_retains_r33_predecessor",
            "r33_disabled_after_cutover",
            "install_cutover_order_proven",
        ):
            self.assertIn(required, text)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', text)

    def test_rollback_restores_r33_without_deleting_bytes(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R33FromR35.ps1").read_text(encoding="ascii")
        self.assertIn("Disable-ScheduledTask -TaskName $R35TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R33TaskName", text)
        self.assertIn("Start-ScheduledTask -TaskName $R33TaskName", text)
        self.assertIn('sqlite_state_deleted = $false', text)
        self.assertNotIn("Remove-Item", text)


if __name__ == "__main__":
    unittest.main()
