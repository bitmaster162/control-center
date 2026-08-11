from __future__ import annotations

import json
import unittest
from pathlib import Path

from hanri import sqlite_cli

APP_ROOT = Path(__file__).parents[1]

class R36ReleaseGateTests(unittest.TestCase):
    def test_runtime_identity(self) -> None:
        self.assertEqual(sqlite_cli.PROGRAM_VERSION, "36.0.0")
        self.assertEqual(sqlite_cli.ACTOR, "HANRI_R36")
        self.assertEqual(sqlite_cli.HUMAN_LABEL, "HANRI R36")
        self.assertEqual(sqlite_cli.INTEGRITY_POLICY_VERSION, "36.0.0-heartbeat-integrity-fast-gate-v1")

    def test_config(self) -> None:
        config = json.loads((APP_ROOT / "config" / "r36.windows.json").read_text(encoding="utf-8"))
        self.assertEqual(config["program_version"], "36.0.0")
        self.assertTrue(config["shadow_only"])
        self.assertEqual(config["external_model_api"], "DENY")
        self.assertFalse(config["can_trade"])
        self.assertIn("ControlCenterHANRIR36", config["state_root"])
        self.assertIn("HANRI_R36", config["human_output_root"])
        self.assertEqual(config["integrity_full_rehash_interval_seconds"], 900)

    def test_release_scripts(self) -> None:
        install = (APP_ROOT / "scripts" / "Install-R36ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        verify = (APP_ROOT / "scripts" / "Verify-R36Runtime-PS51.ps1").read_text(encoding="ascii")
        restore = (APP_ROOT / "scripts" / "Restore-R35FromR36.ps1").read_text(encoding="ascii")
        for required in ("CACHED_STAT_GUARD", "Collect-FastSamples", "R35_MEDIAN_MS", "R36_MEDIAN_MS", "HANRI_R36_RUNTIME_CUTOVER_PASS"):
            self.assertIn(required, install)
        for required in ("CACHED_STAT_GUARD", "Get-FileHash", "HANRI_R36_RUNTIME_VERIFY_PASS"):
            self.assertIn(required, verify)
        for required in ("ControlCenter-HANRI-R35", "ControlCenter-HANRI-R36", "HANRI_R35_ROLLBACK_PASS"):
            self.assertIn(required, restore)

if __name__ == "__main__":
    unittest.main()
