from __future__ import annotations

import hashlib
import json
import unittest

from hanri.guarded_cli import enhanced_sanitize


class SecretBoundaryR29Tests(unittest.TestCase):
    def test_sensitive_dict_key_is_fingerprinted_not_persisted(self) -> None:
        findings: list[dict[str, str]] = []
        value = enhanced_sanitize({"password": "hunter2"}, findings)
        self.assertNotIn("hunter2", json.dumps(value))
        self.assertTrue(str(value["password"]).startswith("[REDACTED:SENSITIVE_FIELD:password:"))
        self.assertEqual(findings[0]["value_sha256"], hashlib.sha256(b"hunter2").hexdigest())
        self.assertNotIn("hunter2", json.dumps(findings))

    def test_function_kwarg_password_is_redacted(self) -> None:
        findings: list[dict[str, str]] = []
        text = 'ssh.connect(host="x", password="p@ssw0rd")'
        value = enhanced_sanitize(text, findings)
        self.assertNotIn("p@ssw0rd", value)
        self.assertTrue(any(row["kind"] == "CONTEXTUAL_CREDENTIAL_ASSIGNMENT" for row in findings))

    def test_json_like_client_secret_is_redacted(self) -> None:
        findings: list[dict[str, str]] = []
        text = '{"client_secret": "alpha-beta-123"}'
        value = enhanced_sanitize(text, findings)
        self.assertNotIn("alpha-beta-123", value)
        self.assertTrue(any(row["kind"] == "CONTEXTUAL_CREDENTIAL_ASSIGNMENT" for row in findings))

    def test_bearer_value_is_redacted(self) -> None:
        findings: list[dict[str, str]] = []
        text = 'Authorization: Bearer abcdefghijklmnop123456'
        value = enhanced_sanitize(text, findings)
        self.assertNotIn("abcdefghijklmnop123456", value)
        self.assertTrue(any(row["kind"] == "AUTHORIZATION_BEARER" for row in findings))

    def test_dsn_password_is_redacted(self) -> None:
        findings: list[dict[str, str]] = []
        text = 'postgresql://alice:s3cret-pass@db.internal/app'
        value = enhanced_sanitize(text, findings)
        self.assertNotIn("s3cret-pass", value)
        self.assertTrue(any(row["kind"] == "DSN_PASSWORD" for row in findings))

    def test_vendor_token_redaction_from_r28_is_preserved(self) -> None:
        findings: list[dict[str, str]] = []
        raw = "sk-" + "x" * 30
        value = enhanced_sanitize({"message": raw}, findings)
        self.assertNotIn(raw, json.dumps(value))
        self.assertTrue(any(row["kind"] == "OPENAI_KEY" for row in findings))

    def test_explicit_redaction_marker_does_not_create_new_secret_finding(self) -> None:
        findings: list[dict[str, str]] = []
        value = enhanced_sanitize({"password": "[REDACTED]"}, findings)
        self.assertEqual(value["password"], "[REDACTED]")
        self.assertEqual(findings, [])

    def test_non_secret_text_is_unchanged(self) -> None:
        findings: list[dict[str, str]] = []
        text = "operator approved bounded shadow-only analysis"
        self.assertEqual(enhanced_sanitize(text, findings), text)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
