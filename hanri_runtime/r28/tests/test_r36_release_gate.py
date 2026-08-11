from __future__ import annotations

import json
import unittest
from pathlib import Path

from hanri import r36_cli

APP_ROOT = Path(__file__).parents[1]


class R36ReleaseGateTests(unittest.TestCase):
    def test_runtime_identity(self) -> None:
        self.assertEqual(r36_cli.PROGRAM_VERSION, "36.0.0")
        self.assertEqual(r36_cli.ACTOR, "HANRI_R36")
        self.assertEqual(r36_cli.HUMAN_LABEL, "HANRI R36")
        self.assertEqual(
            r36_cli.INTEGRITY_POLICY_VERSION,
            "36.0.0-heartbeat-integrity-fast-gate-v1",
        )

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
        for required in (
            "CACHED_STAT_GUARD",
            "Collect-FastSamples",
            "R35_MEDIAN_MS",
            "R36_MEDIAN_MS",
            "HANRI_R36_RUNTIME_CUTOVER_PASS",
        ):
            self.assertIn(required, install)
        for required in ("CACHED_STAT_GUARD", "Get-FileHash", "HANRI_R36_RUNTIME_VERIFY_PASS"):
            self.assertIn(required, verify)
        for required in ("ControlCenter-HANRI-R35", "ControlCenter-HANRI-R36", "HANRI_R35_ROLLBACK_PASS"):
            self.assertIn(required, restore)

    def test_r35_lock_is_quiesced_before_benchmark_without_blind_delete(self) -> None:
        install = (APP_ROOT / "scripts" / "Install-R36ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        for required in (
            "function Quiesce-HanriLock",
            "Get-CimInstance Win32_Process",
            '-ErrorAction Stop',
            "orphaned-r36-cutover-",
            "Move-Item -LiteralPath $LockPath",
            "R35_ORPHAN_LOCK_QUARANTINED",
            "r35_orphan_lock_quarantined",
            "refusing quarantine",
            "$rollbackLockSafeToStart = $false",
            "R35 task re-enabled but not force-started",
        ):
            self.assertIn(required, install)
        self.assertNotIn("Remove-Item -LiteralPath $R35LockPath", install)
        stopped = install.find("Wait-TaskStopped $R35TaskName 60")
        quiesce = install.find("Quiesce-HanriLock $R35LockPath 15")
        benchmark = install.find("Collect-FastSamples $R35App $R35Config $R35State")
        self.assertGreater(stopped, 0)
        self.assertGreater(quiesce, stopped)
        self.assertGreater(benchmark, quiesce)

    def test_sample_runner_suppresses_hanri_stdout_before_numeric_median(self) -> None:
        install = (APP_ROOT / "scripts" / "Install-R36ReleaseCandidate-PS51.ps1").read_text(encoding="ascii")
        start = install.index("function Invoke-HanriOnce")
        end = install.index("function Assert-HeavyHashes", start)
        invoke_once = install[start:end]
        self.assertIn(
            'Invoke-Native $Python @("-m", "hanri", "once", "--config", $ConfigPath) | Out-Null',
            invoke_once,
        )
        self.assertIn("return [double[]]$samples", install)
        self.assertIn("function Median([double[]]$Values)", install)

    def test_r35_wrapper_remains_r35(self) -> None:
        text = (APP_ROOT / "src" / "hanri" / "sqlite_cli.py").read_text(encoding="utf-8")
        self.assertIn('PROGRAM_VERSION = "35.0.0"', text)
        self.assertIn("r36-heartbeat-integrity-fast-gate", text)


if __name__ == "__main__":
    unittest.main()
