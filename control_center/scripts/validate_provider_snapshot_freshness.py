from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SNAPSHOT = DATA / "provider_snapshot.current.v1.json"
EVIDENCE = DATA / "provider_freshness_evidence.current.v1.json"
RESEAL = DATA / "canonical_reseal_execution_receipt.generated.v1.json"

EXPECTED_EVIDENCE_SCHEMA = "control_center.provider_freshness_evidence.v1"
EXPECTED_SNAPSHOT_SCHEMA = "control_center.provider_snapshot.v1"
EXPECTED_RESEAL_SCHEMA = "control_center.canonical_reseal_execution_receipt.v1"
EXPECTED_ROOTS = {
    "CURRENT_STATE.json",
    "ROLE_INDEX.json",
    "ROLE_VIEWS.json",
    "MANIFEST.json",
    "CURRENT_POINTER.json",
}
MAX_AGE_SECONDS = 21600
FUTURE_SKEW_SECONDS = 300


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp_missing_timezone")
    return parsed.astimezone(timezone.utc)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("utf-8")
    return hashlib.sha1(header + payload).hexdigest()


def validate(
    snapshot: dict[str, Any],
    evidence: dict[str, Any],
    reseal: dict[str, Any],
    *,
    now: datetime,
    snapshot_blob_sha: str | None = None,
) -> list[str]:
    errors: list[str] = []

    if snapshot.get("schema") != EXPECTED_SNAPSHOT_SCHEMA:
        errors.append("snapshot_schema_mismatch")
    if evidence.get("schema") != EXPECTED_EVIDENCE_SCHEMA:
        errors.append("evidence_schema_mismatch")
    if reseal.get("schema") != EXPECTED_RESEAL_SCHEMA:
        errors.append("reseal_schema_mismatch")
    if evidence.get("projection_kind") != "NON_AUTHORITY_PROVIDER_READBACK_EVIDENCE":
        errors.append("evidence_projection_kind_mismatch")
    if evidence.get("freshness_scope") != "AUTHORITY_CRITICAL_R64_STABLE_ROOTS":
        errors.append("freshness_scope_mismatch")
    if evidence.get("freshness_status") != "FRESH_AT_CAPTURE":
        errors.append("freshness_status_mismatch")
    if evidence.get("continuous_freshness") is not False:
        errors.append("continuous_freshness_overclaim")
    if evidence.get("max_age_seconds") != MAX_AGE_SECONDS:
        errors.append("max_age_contract_mismatch")
    if evidence.get("future_clock_skew_tolerance_seconds") != FUTURE_SKEW_SECONDS:
        errors.append("future_skew_contract_mismatch")

    try:
        observed = parse_time(str(evidence.get("observed_at", "")))
        current = now.astimezone(timezone.utc)
        age = (current - observed).total_seconds()
        if age > MAX_AGE_SECONDS:
            errors.append("freshness_evidence_stale")
        if age < -FUTURE_SKEW_SECONDS:
            errors.append("freshness_evidence_from_future")
    except (TypeError, ValueError):
        errors.append("freshness_timestamp_invalid")

    source = evidence.get("source_snapshot", {})
    if source.get("path") != "control_center/data/provider_snapshot.current.v1.json":
        errors.append("snapshot_path_binding_mismatch")
    if source.get("snapshot_schema") != snapshot.get("schema"):
        errors.append("snapshot_schema_binding_mismatch")
    if source.get("snapshot_observed_at") != snapshot.get("observed_at"):
        errors.append("snapshot_observed_at_binding_mismatch")
    if snapshot_blob_sha and source.get("github_blob_sha") != snapshot_blob_sha:
        errors.append("snapshot_blob_binding_mismatch")

    roots = evidence.get("stable_roots", {})
    if set(roots) != EXPECTED_ROOTS:
        errors.append("stable_root_identity_set_mismatch")

    canonical = snapshot.get("canonical_roots", {})
    snapshot_bindings = {
        "CURRENT_STATE.json": (canonical.get("current_state_drive_file_id"), canonical.get("current_state_sha256")),
        "ROLE_INDEX.json": (canonical.get("role_index_drive_file_id"), canonical.get("role_index_sha256")),
        "ROLE_VIEWS.json": (canonical.get("role_views_drive_file_id"), canonical.get("role_views_sha256")),
        "CURRENT_POINTER.json": (canonical.get("pointer_drive_file_id"), canonical.get("pointer_sha256")),
        "MANIFEST.json": (None, canonical.get("manifest_sha256")),
    }
    reseal_files = reseal.get("post_write_provider_readback", {}).get("files", {})
    write_ids = {
        row.get("file"): row.get("drive_file_id")
        for row in reseal.get("writes", [])
        if row.get("file") and row.get("drive_file_id")
    }

    modified_times: dict[str, datetime] = {}
    for name in EXPECTED_ROOTS:
        row = roots.get(name, {})
        snapshot_id, snapshot_sha = snapshot_bindings[name]
        reseal_row = reseal_files.get(name, {})
        expected_id = snapshot_id or write_ids.get(name)
        if expected_id and row.get("drive_file_id") != expected_id:
            errors.append(f"drive_id_mismatch:{name}")
        if row.get("sha256") != snapshot_sha:
            errors.append(f"snapshot_sha_mismatch:{name}")
        if row.get("sha256") != reseal_row.get("sha256"):
            errors.append(f"reseal_sha_mismatch:{name}")
        if row.get("bytes") != reseal_row.get("bytes"):
            errors.append(f"byte_length_mismatch:{name}")
        if reseal_row.get("exact_match") is not True:
            errors.append(f"reseal_exact_match_missing:{name}")
        try:
            modified_times[name] = parse_time(str(row.get("modified_time", "")))
        except (TypeError, ValueError):
            errors.append(f"modified_time_invalid:{name}")

    manifest_write = next((x for x in reseal.get("writes", []) if x.get("file") == "MANIFEST.json"), None)
    pointer_write = next((x for x in reseal.get("writes", []) if x.get("file") == "CURRENT_POINTER.json"), None)
    if manifest_write and roots.get("MANIFEST.json", {}).get("modified_time") != manifest_write.get("provider_modified_time"):
        errors.append("manifest_modified_time_reseal_mismatch")
    if pointer_write and roots.get("CURRENT_POINTER.json", {}).get("modified_time") != pointer_write.get("provider_modified_time"):
        errors.append("pointer_modified_time_reseal_mismatch")

    if len(modified_times) == len(EXPECTED_ROOTS):
        pointer_time = modified_times["CURRENT_POINTER.json"]
        if any(pointer_time < value for name, value in modified_times.items() if name != "CURRENT_POINTER.json"):
            errors.append("current_pointer_not_latest_modified_root")

    readback = evidence.get("readback_result", {})
    for key in ("all_five_exact_at_capture", "pointer_last_by_provider_modified_time", "authority_critical_snapshot_match"):
        if readback.get(key) is not True:
            errors.append(f"readback_result_not_true:{key}")

    info = evidence.get("informational_self_referential", {}).get("control_center_github_lane", {})
    snapshot_head = snapshot.get("github_lanes", {}).get("control_center", {}).get("head_sha")
    if info.get("snapshot_head_sha") != snapshot_head:
        errors.append("informational_snapshot_head_binding_mismatch")
    if info.get("authority_relevant") is not False:
        errors.append("self_referential_head_authority_leak")
    if info.get("self_reference_exempt") is not True:
        errors.append("self_reference_exemption_missing")
    pre_capture_head = str(info.get("pre_capture_live_pr_head_sha", ""))
    stale_claim = info.get("snapshot_head_was_stale_at_capture")
    if stale_claim is not (pre_capture_head != str(snapshot_head)):
        errors.append("self_reference_stale_claim_mismatch")

    safety = evidence.get("safety", {})
    false_keys = (
        "evidence_grants_authority",
        "dispatch_authorized",
        "apply_authorized",
        "execution_authorized",
        "root_write_authorized",
        "registry_write_authorized",
        "deploy_authorized",
        "external_message_authorized",
        "can_trade",
        "self_application",
    )
    for key in false_keys:
        if safety.get(key) is not False:
            errors.append(f"freshness_authority_leak:{key}")
    if safety.get("capital_permission") != "DENY":
        errors.append("freshness_capital_permission_mismatch")

    if canonical.get("generation") != "R64" or canonical.get("status") != "ACTIVE" or canonical.get("provider_readback") != "all_exact":
        errors.append("snapshot_canonical_status_mismatch")
    if reseal.get("canonical_result", {}).get("status") != "R64_RESEALED_ALL_EXACT":
        errors.append("reseal_canonical_status_mismatch")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bounded provider freshness evidence for the Control Center snapshot.")
    parser.add_argument("--now", help="ISO-8601 current time override for deterministic testing")
    args = parser.parse_args()

    now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
    snapshot = load(SNAPSHOT)
    evidence = load(EVIDENCE)
    reseal = load(RESEAL)
    errors = validate(snapshot, evidence, reseal, now=now, snapshot_blob_sha=git_blob_sha(SNAPSHOT))
    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "gate": "PROVIDER_SNAPSHOT_FRESHNESS_V1",
        "freshness": evidence.get("freshness_status"),
        "observed_at": evidence.get("observed_at"),
        "max_age_seconds": evidence.get("max_age_seconds"),
        "errors": errors,
    }, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
