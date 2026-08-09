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


if __name__ == "__main__":
    unittest.main()
