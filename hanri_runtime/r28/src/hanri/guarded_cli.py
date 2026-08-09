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

_BASE_SCAN_FRONTIER_PAIR = core.scan_frontier_pair
_BASE_SCAN_CAUSAL_SPINE = core.scan_causal_spine


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
    """Sanitize persistence-bound values and retain fingerprints only."""
    findings = findings if findings is not None else []

    if isinstance(value, str):
        return _redact_contextual_string(value, findings)

    if isinstance(value, list):
        return [enhanced_sanitize(item, findings) for item in value]

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            raw_key = str(key)
            safe_key = _redact_contextual_string(raw_key, findings)
            normalized_key = raw_key.strip().replace("-", "_")
            if SENSITIVE_KEY.fullmatch(normalized_key) and item not in (None, ""):
                if isinstance(item, str):
                    raw = item
                else:
                    raw = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                result[safe_key] = _fingerprint_and_redact(
                    raw,
                    f"SENSITIVE_FIELD:{normalized_key.lower()}",
                    findings,
                )
            else:
                result[safe_key] = enhanced_sanitize(item, findings)
        return result

    return value


def _dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in findings:
        key = (str(row.get("kind", "UNKNOWN")), str(row.get("value_sha256", "")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(dict(row))
    return unique


def _sanitize_archive_scan(result: Any, cache: Any) -> tuple[Any, Any]:
    """Sanitize archive scan output before R28 writes frontier/spine state or cache."""
    findings: list[dict[str, str]] = []
    clean_result = enhanced_sanitize(result, findings)
    clean_cache = enhanced_sanitize(cache, findings)
    unique = _dedupe_findings(findings)
    if isinstance(clean_result, dict):
        clean_result["secret_boundary"] = {
            "guard_version": GUARD_VERSION,
            "finding_count": len(unique),
            "raw_values_persisted": False,
        }
        if unique:
            clean_result["secret_findings"] = unique
    return clean_result, clean_cache


def guarded_scan_frontier_pair(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
    result, cache = _BASE_SCAN_FRONTIER_PAIR(*args, **kwargs)
    return _sanitize_archive_scan(result, cache)


def guarded_scan_causal_spine(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
    result, cache = _BASE_SCAN_CAUSAL_SPINE(*args, **kwargs)
    return _sanitize_archive_scan(result, cache)


def install_guard() -> None:
    # R28 writes event/decision payloads through `sanitize`, but archive frontier/spine
    # objects and their inventory cache are persisted before event sanitization. Guard
    # both surfaces so no raw contextual credential reaches state or Drive projection.
    core.sanitize = enhanced_sanitize
    core.scan_frontier_pair = guarded_scan_frontier_pair
    core.scan_causal_spine = guarded_scan_causal_spine


def main(argv: Sequence[str] | None = None) -> int:
    install_guard()
    return core.main(argv)
