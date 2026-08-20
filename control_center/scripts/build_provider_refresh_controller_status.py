from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from provider_freshness_refresh_controller import (
    _expected_bindings,
    classify_refresh,
)
from validate_provider_snapshot_freshness import EVIDENCE, RESEAL, SNAPSHOT, git_blob_sha, load, parse_time

SCHEMA = "control_center.provider_refresh_controller_status.v1"
PROJECTION_KIND = "NON_AUTHORITY_PROVIDER_REFRESH_DIAGNOSTIC"
DRIFT_VERDICT = "HOLD_PROVIDER_DRIFT_DETECTED"
EXPIRED_VERDICT = "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED"
INVALID_VERDICT = "HOLD_INVALID_OR_INCOMPLETE_CAPTURE"
ALLOWED_MISMATCH_FIELDS = {"drive_file_id", "sha256", "bytes", "modified_time", "pointer_order"}


def safety_block() -> dict[str, Any]:
    return {
        "diagnostic_grants_authority": False,
        "refresh_authorized": False,
        "root_write_authorized": False,
        "registry_write_authorized": False,
        "runtime_mutation_authorized": False,
        "routing_mutation_authorized": False,
        "dispatch_authorized": False,
        "apply_authorized": False,
        "execution_authorized": False,
        "deploy_authorized": False,
        "external_message_authorized": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "self_application": False,
    }


def neutral_status() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "projection_kind": PROJECTION_KIND,
        "verdict": "NO_HOLD_DIAGNOSTIC_RECORDED",
        "operator_state": "NO_HOLD_DIAGNOSTIC_RECORDED",
        "hold_active": False,
        "absence_does_not_prove_no_drift": True,
        "source_capture": None,
        "controller_errors": [],
        "mismatches": [],
        "note": "No current provider-drift HOLD diagnostic is recorded. This does not prove that provider drift is absent; only a fresh read-only capture classified by the Refresh Controller can establish a new diagnostic state.",
        "safety": safety_block(),
    }


def mismatch_rows(
    snapshot: dict[str, Any],
    current_evidence: dict[str, Any],
    reseal: dict[str, Any],
    capture: dict[str, Any],
) -> list[dict[str, Any]]:
    expected = _expected_bindings(snapshot, reseal)
    current_roots = current_evidence.get("stable_roots", {})
    capture_roots = capture.get("stable_roots", {})
    rows: list[dict[str, Any]] = []

    for name in sorted(expected):
        observed = capture_roots.get(name, {})
        for field in ("drive_file_id", "sha256", "bytes"):
            if observed.get(field) != expected[name].get(field):
                rows.append({
                    "root": name,
                    "field": field,
                    "expected": expected[name].get(field),
                    "observed": observed.get(field),
                })
        current_modified = current_roots.get(name, {}).get("modified_time")
        if observed.get("modified_time") != current_modified:
            rows.append({
                "root": name,
                "field": "modified_time",
                "expected": current_modified,
                "observed": observed.get("modified_time"),
            })

    try:
        times = {
            name: parse_time(str(capture_roots[name]["modified_time"]))
            for name in expected
            if name in capture_roots and capture_roots[name].get("modified_time")
        }
        if len(times) == len(expected):
            latest = max(times, key=times.get)
            if latest != "CURRENT_POINTER.json":
                rows.append({
                    "root": "CURRENT_POINTER.json",
                    "field": "pointer_order",
                    "expected": "LATEST_MODIFIED_STABLE_ROOT",
                    "observed": latest,
                })
    except (TypeError, ValueError):
        pass

    return rows


def build_status(
    snapshot: dict[str, Any],
    current_evidence: dict[str, Any],
    reseal: dict[str, Any],
    capture: dict[str, Any],
    *,
    now: datetime,
    snapshot_blob_sha: str,
) -> dict[str, Any]:
    result = classify_refresh(
        snapshot,
        current_evidence,
        reseal,
        capture,
        now=now,
        snapshot_blob_sha=snapshot_blob_sha,
    )
    verdict = result["verdict"]
    if verdict == DRIFT_VERDICT:
        operator_state = "DRIFT_HOLD"
        hold_active = True
        mismatches = mismatch_rows(snapshot, current_evidence, reseal, capture)
    elif verdict == EXPIRED_VERDICT:
        operator_state = "EXPIRED"
        hold_active = True
        mismatches = []
    elif verdict == INVALID_VERDICT:
        operator_state = "INVALID_CAPTURE_HOLD"
        hold_active = True
        mismatches = []
    else:
        operator_state = "NO_HOLD"
        hold_active = False
        mismatches = []

    return {
        "schema": SCHEMA,
        "projection_kind": PROJECTION_KIND,
        "verdict": verdict,
        "operator_state": operator_state,
        "hold_active": hold_active,
        "absence_does_not_prove_no_drift": True,
        "source_capture": {
            "schema": capture.get("schema"),
            "provider": capture.get("provider"),
            "observed_at": capture.get("observed_at"),
        },
        "controller_errors": list(result.get("errors") or []),
        "mismatches": mismatches,
        "note": "Diagnostic projection only. No provider/root/registry/runtime remediation is authorized by this status.",
        "safety": safety_block(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bounded provider refresh-controller diagnostic status JSON to stdout.")
    parser.add_argument("--capture", help="Path to control_center.provider_refresh_capture.v1 JSON. Omit for neutral no-record status.")
    parser.add_argument("--now", help="ISO-8601 current time override")
    args = parser.parse_args()

    if not args.capture:
        status = neutral_status()
    else:
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
        status = build_status(
            load(SNAPSHOT),
            load(EVIDENCE),
            load(RESEAL),
            load(Path(args.capture)),
            now=now,
            snapshot_blob_sha=git_blob_sha(SNAPSHOT),
        )
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
