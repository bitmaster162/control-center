from __future__ import annotations

import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class R29RC2ReleaseGateTests(unittest.TestCase):
    def test_rc2_config_is_isolated_and_fail_closed(self) -> None:
        config = json.loads((APP_ROOT / "config" / "r29.rc2.windows.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(config["program_version"], "29.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR29RC2", config["state_root"])
        self.assertIn("HANRI_R29_RC2", config["human_output_root"])

    def test_rc2_installer_never_mutates_rc1_files_or_state(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R29RC2SideBySide.ps1").read_text(encoding="utf-8")
        self.assertIn('ExpectedBranch = "hanri/r29-release-candidate-2"', text)
        self.assertIn("ControlCenterHANRIR29RC2", text)
        self.assertIn("ControlCenter-HANRI-R29-RC2", text)
        self.assertNotIn("ControlCenterHANRIR29\\app", text)
        self.assertNotIn("ControlCenterHANRIR29\\state", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('rc1_files_modified = $false', text)
        self.assertIn('rc1_state_modified_by_installer = $false', text)

    def test_rc1_is_disabled_only_after_second_rc2_readback(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R29RC2SideBySide.ps1").read_text(encoding="utf-8")
        last_readback = text.rfind("Assert-R29RuntimeReadback")
        disable_rc1 = text.find("Disable-ScheduledTask -TaskName $R29RC1TaskName")
        self.assertGreater(last_readback, 0)
        self.assertGreater(disable_rc1, last_readback)

    def test_failure_path_disables_rc2_and_restores_rc1_scheduler(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R29RC2SideBySide.ps1").read_text(encoding="utf-8")
        catch = text[text.rfind("catch {"):]
        self.assertIn("Disable-ScheduledTask -TaskName $R29RC2TaskName", catch)
        self.assertIn("Enable-ScheduledTask -TaskName $R29RC1TaskName", catch)

    def test_rc2_verifier_requires_identity_and_safety_invariants(self) -> None:
        text = (APP_ROOT / "scripts" / "Verify-R29RC2Runtime.ps1").read_text(encoding="utf-8")
        for required in (
            "digest_identifies_r29",
            "digest_does_not_identify_r28",
            "receipt_self_application_false",
            "receipt_can_trade_false",
            "receipt_external_api_zero",
            "state_shadow_only",
            "state_self_application_false",
            "state_can_trade_false",
            "state_external_api_zero",
        ):
            self.assertIn(required, text)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', text)

    def test_rc2_rollback_switches_scheduler_without_deleting_bytes(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R29RC1FromRC2.ps1").read_text(encoding="utf-8")
        self.assertIn("Disable-ScheduledTask -TaskName $R29RC2TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R29RC1TaskName", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('rc1_files_deleted = $false', text)
        self.assertIn('rc2_files_deleted = $false', text)


if __name__ == "__main__":
    unittest.main()
