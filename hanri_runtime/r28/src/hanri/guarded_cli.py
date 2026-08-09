from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

from . import cli as core

GUARD_VERSION = "29.0.0-candidate"

SENSITIVE_KEY = re.compile(
    r"(?i)^(?:password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|apikey|"
    r"access[_-]?token|auth[_-]?token|refresh[_-]?token|private[_-]?key|credential)$"
)

_CONTEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "CONTEXTUAL_CREDENTIAL_ASSIGNMENT",
        re.compile(
            r"(?i)(?P<prefix>\b(?:password|passwd|pwd|secret|client[_-]?secret|api[_-]?key|apikey|"
            r"access[_-]?token|auth[_-]?token|refresh[_-]?token|private[_-]?key|credential)\b"
            r"[\"']?\s*[:=]\s*[\"']?)(?P<secret>\[[^\]\r\n]{1,160}\]|<[^>\r\n]{1,160}>|[^\s,;\)\]}\"']+)"
        ),
    ),
    (
        "AUTHORIZATION_BEARER",
        re.compile(
            r"(?i)(?P<prefix>\bauthorization\b[\"']?\s*[:=]\s*[\"']?\s*bearer\s+)"
            r"(?P<secret>[A-Za-z0-9._~+/=-]{8,})"
        ),
    ),
    (
        "DSN_PASSWORD",
        re.compile(
            r"(?i)(?P<prefix>\b[a-z][a-z0-9+.-]*://[^/\s:@]+:)(?P<secret>[^@\s/]+)(?P<suffix>@)"
        ),
    ),
)


def _explicitly_redacted(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return (
        normalized in {"redacted", "***", "****", "*****", "<redacted>", "[redacted]"}
        or normalized.startswith("[redacted:")
    )


def _fingerprint_and_redact(raw: str, kind: str, findings: list[dict[str, str]]) -> str:
    if _explicitly_redacted(raw):
        return raw
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    findings.append(
        {
            "kind": kind,
            "value_sha256": fingerprint,
            "source": "R29_CONTEXTUAL_SECRET_BOUNDARY",
        }
    )
    return f"[REDACTED:{kind}:{fingerprint[:12]}]"


def _redact_contextual_string(value: str, findings: list[dict[str, str]]) -> str:
    redacted = core.redact_string(value, findings)
    for kind, pattern in _CONTEXT_PATTERNS:
        def replace(match: re.Match[str]) -> str:
            secret = match.group("secret")
            replacement = _fingerprint_and_redact(secret, kind, findings)
            suffix = match.groupdict().get("suffix") or ""
            return f"{match.group('prefix')}{replacement}{suffix}"

        redacted = pattern.sub(replace, redacted)
    return redacted


def enhanced_sanitize(value: Any, findings: list[dict[str, str]] | None = None) -> Any:
    """Fail-safe R29 sanitization without changing R28 core persistence semantics.

    Raw secret values are never copied into findings: only SHA-256 fingerprints and
    classification metadata are retained. Dict keys that explicitly name credential
    fields are treated as secrets even when the value does not match a vendor-specific
    token format. Free-text strings additionally cover named assignments, Bearer auth,
    and DSN user:password forms.
    """
    findings = findings if findings is not None else []

    if isinstance(value, str):
        return _redact_contextual_string(value, findings)

    if isinstance(value, list):
        return [enhanced_sanitize(item, findings) for item in value]

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            string_key = str(key)
            normalized_key = string_key.strip().replace("-", "_")
            if SENSITIVE_KEY.fullmatch(normalized_key) and item not in (None, ""):
                if isinstance(item, str):
                    raw = item
                else:
                    raw = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                result[string_key] = _fingerprint_and_redact(
                    raw,
                    f"SENSITIVE_FIELD:{normalized_key.lower()}",
                    findings,
                )
            else:
                result[string_key] = enhanced_sanitize(item, findings)
        return result

    return value


def install_guard() -> None:
    # R28 calls its module-global `sanitize` at every event/decision persistence path.
    # Rebinding only that function keeps the verified R28 core intact and makes rollback
    # a one-line entrypoint change.
    core.sanitize = enhanced_sanitize


def main(argv: Sequence[str] | None = None) -> int:
    install_guard()
    return core.main(argv)
