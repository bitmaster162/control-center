from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

OBSERVED_SCHEMA = "hanri.archiveos-freshness.observed/v1"
QUALIFICATION_SCHEMA = "hanri.archiveos-freshness.qualification/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _require_effect_ceiling(observed: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    invariants = observed.get("invariants") or {}
    effects = observed.get("effects") or {}

    expected_invariants = {
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
        "auto_dispatch": False,
        "auto_promotion": False,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) != expected:
            gaps.append(f"effect ceiling drift: invariants.{key}")

    for key in (
        "writes",
        "runtime_mutations",
        "provider_mutations",
        "external_messages",
        "trading_effects",
    ):
        if effects.get(key) != 0:
            gaps.append(f"effect ceiling drift: effects.{key}")
    return gaps


def qualify(observed: dict[str, Any]) -> dict[str, Any]:
    gaps: list[str] = []

    if observed.get("schema") != OBSERVED_SCHEMA:
        gaps.append("observed schema mismatch")
    if observed.get("surface") != "archive-os":
        gaps.append("surface must be archive-os")

    precedence = observed.get("source_precedence") or {}
    if not precedence.get("canonical_root"):
        gaps.append("canonical ArchiveOS root is not bound")
    if precedence.get("drive_role") != "MIRROR_EVIDENCE_ONLY":
        gaps.append("Drive source-precedence boundary is missing or widened")
    if precedence.get("archive_tooling_role") != "ARTIFACT_COMPILER_NOT_ARCHIVE_ENGINE":
        gaps.append("Archive Tooling boundary is missing or widened")

    gaps.extend(_require_effect_ceiling(observed))

    root = observed.get("authoritative_root_readback") or {}
    if root.get("provider_readback_available") is not True:
        gaps.append("authoritative root provider readback is missing")
    if root.get("root_exists_verified") is not True:
        gaps.append("authoritative root existence is not independently verified")
    if root.get("full_integrity_receipt_present") is not True:
        gaps.append("fresh full archive-integrity receipt is missing")
    if root.get("full_sha_performed") is not True:
        gaps.append("full SHA over the authoritative immutable source set was not performed")

    bytes_hashed = root.get("bytes_hashed")
    if not isinstance(bytes_hashed, int) or isinstance(bytes_hashed, bool) or bytes_hashed <= 0:
        gaps.append("authoritative full-integrity bytes_hashed must be > 0")

    file_count = root.get("file_count")
    if not isinstance(file_count, int) or isinstance(file_count, bool) or file_count <= 0:
        gaps.append("authoritative full-integrity file_count must be > 0")

    manifest_sha = root.get("manifest_sha256")
    if not _is_sha256(manifest_sha):
        gaps.append("authoritative manifest_sha256 is missing or invalid")

    if root.get("independent_readback_present") is not True:
        gaps.append("independent post-integrity readback is missing")

    independent_sha = root.get("independent_manifest_sha256")
    if not _is_sha256(independent_sha):
        gaps.append("independent manifest SHA-256 is missing or invalid")
    elif _is_sha256(manifest_sha) and independent_sha != manifest_sha:
        gaps.append("independent manifest SHA-256 does not match authoritative receipt")

    independent_count = root.get("independent_file_count")
    if not isinstance(independent_count, int) or isinstance(independent_count, bool) or independent_count <= 0:
        gaps.append("independent file_count must be > 0")
    elif isinstance(file_count, int) and not isinstance(file_count, bool) and file_count > 0 and independent_count != file_count:
        gaps.append("independent file_count does not match authoritative receipt")

    provider = observed.get("provider_readbacks") or {}
    r36 = provider.get("hanri_r36_integrity") or {}
    if r36.get("full_sha_performed") is False or r36.get("bytes_hashed") == 0:
        # This is an observation, not an additional gap: cached stat-guard evidence
        # can coexist with a future dedicated ArchiveOS full-integrity receipt.
        pass

    passed = not gaps
    status = "PASS" if passed else "BLOCKED_REVERIFY"

    return {
        "schema": QUALIFICATION_SCHEMA,
        "surface": "archive-os",
        "observed_at": observed.get("observed_at"),
        "status": status,
        "operational_status": "OPERATIONAL" if passed else "BLOCKED_REVERIFY",
        "freshness": "CURRENT" if passed else "STALE",
        "current_claim_allowed": passed,
        "promotion_eligible": passed,
        "proof_gap": gaps,
        "claim_ceiling": {
            "property": "ARCHIVEOS_CURRENT_IMMUTABLE_SOURCE_SET_INTEGRITY",
            "drive_mirror_is_authority": False,
            "archive_tooling_is_archive_engine": False,
            "cached_stat_guard_is_full_integrity": False,
            "runtime_deployment_claim": False,
            "universal_archive_completeness_claim": False,
        },
        "effects": {
            "writes": 0,
            "runtime_mutations": 0,
            "provider_mutations": 0,
            "external_messages": 0,
            "trading_effects": 0,
        },
        "invariants": {
            "can_trade": False,
            "capital_permission": "DENY",
            "self_application": False,
            "auto_dispatch": False,
            "auto_promotion": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    observed = json.loads(Path(args.observed).read_text(encoding="utf-8"))
    result = qualify(observed)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
