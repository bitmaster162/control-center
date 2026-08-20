from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_provider_snapshot_freshness import (
    EVIDENCE,
    EXPECTED_ROOTS,
    FUTURE_SKEW_SECONDS,
    MAX_AGE_SECONDS,
    RESEAL,
    SNAPSHOT,
    git_blob_sha,
    load,
    parse_time,
)

EXPECTED_CAPTURE_SCHEMA = "control_center.provider_refresh_capture.v1"
EXPECTED_CAPTURE_KIND = "READ_ONLY_PROVIDER_CAPTURE"
EXPECTED_PROVIDER = "GOOGLE_DRIVE_DIRECT_READBACK"


def _expected_bindings(snapshot: dict[str, Any], reseal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    canonical = snapshot.get("canonical_roots", {})
    reseal_files = reseal.get("post_write_provider_readback", {}).get("files", {})
    write_ids = {
        row.get("file"): row.get("drive_file_id")
        for row in reseal.get("writes", [])
        if row.get("file") and row.get("drive_file_id")
    }
    ids = {
        "CURRENT_STATE.json": canonical.get("current_state_drive_file_id"),
        "ROLE_INDEX.json": canonical.get("role_index_drive_file_id"),
        "ROLE_VIEWS.json": canonical.get("role_views_drive_file_id"),
        "MANIFEST.json": write_ids.get("MANIFEST.json"),
        "CURRENT_POINTER.json": canonical.get("pointer_drive_file_id") or write_ids.get("CURRENT_POINTER.json"),
    }
    hashes = {
        "CURRENT_STATE.json": canonical.get("current_state_sha256"),
        "ROLE_INDEX.json": canonical.get("role_index_sha256"),
        "ROLE_VIEWS.json": canonical.get("role_views_sha256"),
        "MANIFEST.json": canonical.get("manifest_sha256"),
        "CURRENT_POINTER.json": canonical.get("pointer_sha256"),
    }
    return {
        name: {
            "drive_file_id": ids[name],
            "sha256": hashes[name],
            "bytes": reseal_files.get(name, {}).get("bytes"),
        }
        for name in EXPECTED_ROOTS
    }


def _invalid_capture_errors(capture: dict[str, Any], *, now: datetime) -> list[str]:
    errors: list[str] = []
    if capture.get("schema") != EXPECTED_CAPTURE_SCHEMA:
        errors.append("capture_schema_mismatch")
    if capture.get("capture_kind") != EXPECTED_CAPTURE_KIND:
        errors.append("capture_kind_mismatch")
    if capture.get("provider") != EXPECTED_PROVIDER:
        errors.append("capture_provider_mismatch")
    if set(capture.get("stable_roots", {})) != EXPECTED_ROOTS:
        errors.append("capture_root_identity_set_mismatch")
    safety = capture.get("safety", {})
    if safety.get("provider_mutation_performed") is not False:
        errors.append("capture_provider_mutation_not_false")
    if safety.get("authority_granted") is not False:
        errors.append("capture_authority_grant")
    try:
        observed = parse_time(str(capture.get("observed_at", "")))
        age = (now.astimezone(timezone.utc) - observed).total_seconds()
        if age < -FUTURE_SKEW_SECONDS:
            errors.append("capture_from_future")
    except (TypeError, ValueError):
        errors.append("capture_timestamp_invalid")
    for name, row in capture.get("stable_roots", {}).items():
        if not isinstance(row, dict):
            errors.append(f"capture_root_row_invalid:{name}")
            continue
        for key in ("drive_file_id", "modified_time", "bytes", "sha256"):
            if row.get(key) in (None, ""):
                errors.append(f"capture_root_field_missing:{name}:{key}")
        try:
            parse_time(str(row.get("modified_time", "")))
        except (TypeError, ValueError):
            errors.append(f"capture_modified_time_invalid:{name}")
    return errors


def _drift_errors(
    snapshot: dict[str, Any],
    current_evidence: dict[str, Any],
    reseal: dict[str, Any],
    capture: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    expected = _expected_bindings(snapshot, reseal)
    current_roots = current_evidence.get("stable_roots", {})
    capture_roots = capture.get("stable_roots", {})
    modified: dict[str, datetime] = {}
    for name in EXPECTED_ROOTS:
        row = capture_roots.get(name, {})
        exp = expected[name]
        for key in ("drive_file_id", "sha256", "bytes"):
            if row.get(key) != exp.get(key):
                errors.append(f"provider_drift:{name}:{key}")
        current_row = current_roots.get(name, {})
        if row.get("modified_time") != current_row.get("modified_time"):
            errors.append(f"provider_metadata_drift:{name}:modified_time")
        try:
            modified[name] = parse_time(str(row.get("modified_time", "")))
        except (TypeError, ValueError):
            pass
    if len(modified) == len(EXPECTED_ROOTS):
        pointer_time = modified["CURRENT_POINTER.json"]
        if any(pointer_time < value for name, value in modified.items() if name != "CURRENT_POINTER.json"):
            errors.append("provider_drift:current_pointer_not_latest_modified_root")
    return errors


def build_candidate_evidence(
    snapshot: dict[str, Any],
    capture: dict[str, Any],
    *,
    snapshot_blob_sha: str,
) -> dict[str, Any]:
    snapshot_head = snapshot.get("github_lanes", {}).get("control_center", {}).get("head_sha")
    live_head = capture.get("informational", {}).get("pre_capture_live_pr_head_sha")
    return {
        "schema": "control_center.provider_freshness_evidence.v1",
        "projection_kind": "NON_AUTHORITY_PROVIDER_READBACK_EVIDENCE",
        "observed_at": capture["observed_at"],
        "freshness_scope": "AUTHORITY_CRITICAL_R64_STABLE_ROOTS",
        "freshness_status": "FRESH_AT_CAPTURE",
        "continuous_freshness": False,
        "max_age_seconds": MAX_AGE_SECONDS,
        "future_clock_skew_tolerance_seconds": FUTURE_SKEW_SECONDS,
        "provider": EXPECTED_PROVIDER,
        "source_snapshot": {
            "path": "control_center/data/provider_snapshot.current.v1.json",
            "snapshot_schema": snapshot.get("schema"),
            "snapshot_observed_at": snapshot.get("observed_at"),
            "github_blob_sha": snapshot_blob_sha,
        },
        "stable_roots": capture["stable_roots"],
        "readback_result": {
            "all_five_exact_at_capture": True,
            "pointer_last_by_provider_modified_time": True,
            "authority_critical_snapshot_match": True,
        },
        "informational_self_referential": {
            "control_center_github_lane": {
                "snapshot_head_sha": snapshot_head,
                "pre_capture_live_pr_head_sha": live_head,
                "snapshot_head_was_stale_at_capture": str(live_head) != str(snapshot_head),
                "authority_relevant": False,
                "self_reference_exempt": True,
                "note": "A committed provider snapshot cannot bind its own eventual commit SHA. Live Control Center head is verified separately before every GitHub write.",
            }
        },
        "safety": {
            "evidence_grants_authority": False,
            "dispatch_authorized": False,
            "apply_authorized": False,
            "execution_authorized": False,
            "root_write_authorized": False,
            "registry_write_authorized": False,
            "deploy_authorized": False,
            "external_message_authorized": False,
            "can_trade": False,
            "capital_permission": "DENY",
            "self_application": False,
        },
    }


def classify_refresh(
    snapshot: dict[str, Any],
    current_evidence: dict[str, Any],
    reseal: dict[str, Any],
    capture: dict[str, Any],
    *,
    now: datetime,
    snapshot_blob_sha: str,
) -> dict[str, Any]:
    invalid = _invalid_capture_errors(capture, now=now)
    if invalid:
        return {
            "verdict": "HOLD_INVALID_OR_INCOMPLETE_CAPTURE",
            "refresh_allowed": False,
            "errors": invalid,
            "candidate_evidence": None,
        }

    drift = _drift_errors(snapshot, current_evidence, reseal, capture)
    if drift:
        return {
            "verdict": "HOLD_PROVIDER_DRIFT_DETECTED",
            "refresh_allowed": False,
            "errors": drift,
            "candidate_evidence": None,
        }

    observed = parse_time(capture["observed_at"])
    current_observed = parse_time(current_evidence["observed_at"])
    current_age = (now.astimezone(timezone.utc) - current_observed).total_seconds()

    if observed <= current_observed:
        if current_age <= MAX_AGE_SECONDS:
            return {
                "verdict": "NO_REFRESH_REQUIRED_CURRENT_LEASE_FRESH",
                "refresh_allowed": False,
                "errors": [],
                "candidate_evidence": None,
            }
        return {
            "verdict": "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED",
            "refresh_allowed": False,
            "errors": ["strictly_newer_capture_required"],
            "candidate_evidence": None,
        }

    candidate = build_candidate_evidence(snapshot, capture, snapshot_blob_sha=snapshot_blob_sha)
    return {
        "verdict": "REFRESH_EVIDENCE_ONLY_ALLOWED",
        "refresh_allowed": True,
        "allowed_write_path": "control_center/data/provider_freshness_evidence.current.v1.json",
        "all_other_writes_allowed": False,
        "errors": [],
        "candidate_evidence": candidate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a read-only provider capture for bounded freshness-evidence refresh.")
    parser.add_argument("--capture", required=True, help="Path to raw control_center.provider_refresh_capture.v1 JSON")
    parser.add_argument("--now", help="ISO-8601 current time override")
    args = parser.parse_args()

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    result = classify_refresh(
        load(SNAPSHOT),
        load(EVIDENCE),
        load(RESEAL),
        load(Path(args.capture)),
        now=now,
        snapshot_blob_sha=git_blob_sha(SNAPSHOT),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] in {"REFRESH_EVIDENCE_ONLY_ALLOWED", "NO_REFRESH_REQUIRED_CURRENT_LEASE_FRESH"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
