from __future__ import annotations

import json
import unittest
from pathlib import Path

from hanri.cli import HanriError
from hanri.guarded_cli import PROGRAM_VERSION, guarded_load_config

APP_ROOT = Path(__file__).resolve().parents[1]


class R29ReleaseGateTests(unittest.TestCase):
    def test_r29_config_is_shadow_only_and_capital_denied(self) -> None:
        path = APP_ROOT / "config" / "r29.windows.json"
        config = json.loads(path.read_text(encoding="utf-8-sig"))
        self.assertEqual(config["program_version"], "29.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR29", config["state_root"])
        self.assertIn("HANRI_R29", config["human_output_root"])

    def test_guard_accepts_r29_config_and_rejects_r28_identity(self) -> None:
        r29 = guarded_load_config(APP_ROOT / "config" / "r29.windows.json")
        self.assertEqual(r29["program_version"], PROGRAM_VERSION)
        with self.assertRaises(HanriError):
            guarded_load_config(APP_ROOT / "config" / "r28.windows.json")

    def test_installer_is_side_by_side_and_preserves_r28_files(self) -> None:
        text = (APP_ROOT / "scripts" / "Install-R29ReleaseCandidate.ps1").read_text(encoding="utf-8")
        self.assertIn("ControlCenterHANRIR29", text)
        self.assertIn('ExpectedBranch = "hanri/r29-release-candidate"', text)
        self.assertIn("-ExpectedCommit is required with -Apply", text)
        self.assertIn("Disable-ScheduledTask -TaskName $R28TaskName", text)
        self.assertNotIn("Unregister-ScheduledTask -TaskName $R28TaskName", text)
        self.assertNotIn("ControlCenterHANRIR28\\app", text)
        self.assertIn("R28 was not deleted", text)

    def test_rollback_switches_scheduler_without_deleting_state(self) -> None:
        text = (APP_ROOT / "scripts" / "Restore-R28FromR29.ps1").read_text(encoding="utf-8")
        self.assertIn("Disable-ScheduledTask -TaskName $R29TaskName", text)
        self.assertIn("Enable-ScheduledTask -TaskName $R28TaskName", text)
        self.assertNotIn("Remove-Item", text)
        self.assertIn('r29_files_deleted = $false', text)
        self.assertIn('r29_state_deleted = $false', text)

    def test_runtime_verifier_requires_all_invariants(self) -> None:
        text = (APP_ROOT / "scripts" / "Verify-R29Runtime.ps1").read_text(encoding="utf-8")
        for required in (
            "receipt_program_version",
            "receipt_self_application_false",
            "receipt_can_trade_false",
            "receipt_external_api_zero",
            "state_program_version",
            "state_shadow_only",
            "state_self_application_false",
            "state_can_trade_false",
            "state_external_api_zero",
        ):
            self.assertIn(required, text)
        self.assertIn('if ($Status -ne "PASS") { exit 2 }', text)


if __name__ == "__main__":
    unittest.main()
