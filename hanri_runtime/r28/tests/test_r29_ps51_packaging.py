from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCRIPTS = (
    APP_ROOT / "scripts" / "Install-R29RC2SideBySide-PS51.ps1",
    APP_ROOT / "scripts" / "Verify-R29RC2Runtime-PS51.ps1",
    APP_ROOT / "scripts" / "Restore-R29RC1FromRC2.ps1",
)


class R29PowerShell51PackagingTests(unittest.TestCase):
    def test_release_entrypoints_are_ascii_only(self) -> None:
        for path in RELEASE_SCRIPTS:
            payload = path.read_bytes()
            self.assertTrue(payload, str(path))
            non_ascii = [value for value in payload if value > 0x7F]
            self.assertEqual(non_ascii, [], f"non-ASCII byte in {path}")

    def test_ps51_installer_is_bound_to_rc2_1_release_branch(self) -> None:
        text = RELEASE_SCRIPTS[0].read_text(encoding="ascii")
        self.assertIn('ExpectedBranch = "hanri/r29-release-candidate-2.1"', text)
        self.assertIn('ExpectedDigestIdentity = "HANRI R29"', text)
        self.assertIn('ForbiddenDigestIdentity = "HANRI R28"', text)
        self.assertNotIn("ExpectedDigestHeader", text)

    def test_ps51_verifier_uses_ascii_identity_check(self) -> None:
        text = RELEASE_SCRIPTS[1].read_text(encoding="ascii")
        self.assertIn('ExpectedDigestIdentity = "HANRI R29"', text)
        self.assertIn('ForbiddenDigestIdentity = "HANRI R28"', text)
        self.assertNotIn("ExpectedDigestHeader", text)


if __name__ == "__main__":
    unittest.main()
