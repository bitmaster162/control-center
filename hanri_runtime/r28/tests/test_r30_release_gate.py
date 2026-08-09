from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class R30ReleaseGateTests(unittest.TestCase):
    def test_r30_config_is_isolated_and_fail_closed(self) -> None:
        config = json.loads((APP_ROOT / "config" / "r30.windows.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(config["program_version"], "30.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR30", config["state_root"])
        self.assertIn("HANRI_R30", config["human_output_root"])
        self.assertEqual(config["max_recursion_depth"], 2)

    def test_module_entrypoint_routes_through_r30_guard(self) -> None:
        text = (APP_ROOT / "src" / "hanri" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("from .delta_cli import main", text)

    def test_r30_delta_guard_does_not_enable_effect_authority(self) -> None:
        text = (APP_ROOT / "src" / "hanri" / "delta_cli.py").read_text(encoding="utf-8")
        self.assertIn('PROGRAM_VERSION = "30.0.0"', text)
        self.assertIn('"external_model_api_calls": 0', text)
        self.assertIn('"self_application": False', text)
        self.assertIn('"can_trade": False', text)
        self.assertNotIn("requests.", text)
        self.assertNotIn("subprocess", text)

    def test_installer_is_side_by_side_and_preserves_accepted_r29(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R30ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        self.assertIn('ExpectedBranch = "hanri/r30-release-candidate"', text)
        self.assertIn("ControlCenterHANRIR30", text)
        self.assertIn("ControlCenter-HANRI-R30", text)
        self.assertIn("ControlCenter-HANRI-R29-RC2", text)
        self.assertNotIn("ControlCenterHANRIR29RC2\\app", text)
        self.assertNotIn("ControlCenterHANRIR29RC2\\state", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r29_files_modified = $false', text)
        self.assertIn('r29_state_modified_by_installer = $false', text)

    def test_accepted_r29_is_disabled_only_after_r30_readback(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R30ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        last_readback = text.rfind("Assert-R30RuntimeReadback")
        disable_r29 = text.find("Disable-ScheduledTask -TaskName $R29TaskName")
        self.assertGreater(last_readback, 0)
        self.assertGreater(disable_r29, last_readback)

    def test_failure_path_restores_accepted_r29_scheduler(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R30ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        catch = text[text.rfind("catch {"):]
        self.assertIn("Disable-ScheduledTask -TaskName $R30TaskName", catch)
        self.assertIn("Enable-ScheduledTask -TaskName $R29TaskName", catch)

    def test_runtime_verifier_requires_projection_and_safety_invariants(self) -> None:
        text = (APP_ROOT / "scripts" / "Verify-R30Runtime-PS51.ps1").read_text(encoding="ascii")
        for required in (
            "projection_receipt_exists",
            "projection_self_exclusion_true",
            "projection_self_application_false",
            "projection_can_trade_false",
            "projection_external_api_zero",
            "state_shadow_only",
            "state_self_application_false",
            "state_can_trade_false",
            "state_external_api_zero",
            "state_repo_writes_false",
            "digest_identifies_r30",
            "digest_does_not_identify_r29",
        ):
            self.assertIn(required, text)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', text)

    def test_rollback_switches_scheduler_without_deleting_bytes(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R29RC2FromR30.ps1").read_text(encoding="ascii")
        self.assertIn("Disable-ScheduledTask -TaskName $R30TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R29TaskName", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r29_files_deleted = $false', text)
        self.assertIn('r30_files_deleted = $false', text)

    def test_release_entrypoints_are_ascii_only(self) -> None:
        for name in (
            "Install-R30ReleaseCandidate-PS51.ps1",
            "Verify-R30Runtime-PS51.ps1",
            "Restore-R29RC2FromR30.ps1",
        ):
            data = (APP_ROOT / "scripts" / name).read_bytes()
            self.assertTrue(all(byte < 128 for byte in data), name)


if __name__ == "__main__":
    unittest.main()
