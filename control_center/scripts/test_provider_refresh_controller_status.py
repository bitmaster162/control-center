from __future__ import annotations

import copy
from datetime import timedelta

from build_provider_refresh_controller_status import build_status, neutral_status
from validate_provider_refresh_controller_status import validate
from validate_provider_snapshot_freshness import EVIDENCE, RESEAL, SNAPSHOT, git_blob_sha, load, parse_time


def exact_capture() -> dict:
    evidence = load(EVIDENCE)
    return {
        "schema": "control_center.provider_refresh_capture.v1",
        "capture_kind": "READ_ONLY_PROVIDER_CAPTURE",
        "provider": "GOOGLE_DRIVE_DIRECT_READBACK",
        "observed_at": "2026-08-12T05:30:00+07:00",
        "stable_roots": copy.deepcopy(evidence["stable_roots"]),
        "informational": {
            "pre_capture_live_pr_head_sha": "test-head"
        },
        "safety": {
            "provider_mutation_performed": False,
            "authority_granted": False
        }
    }


def build(capture: dict, now: str = "2026-08-12T05:31:00+07:00") -> dict:
    return build_status(
        load(SNAPSHOT),
        load(EVIDENCE),
        load(RESEAL),
        capture,
        now=parse_time(now),
        snapshot_blob_sha=git_blob_sha(SNAPSHOT),
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    neutral = neutral_status()
    require(not validate(neutral), "neutral status must validate")
    require(neutral["absence_does_not_prove_no_drift"] is True, "neutral must preserve uncertainty")

    exact = build(exact_capture())
    require(exact["verdict"] == "REFRESH_EVIDENCE_ONLY_ALLOWED", "new exact capture should be refresh-eligible")
    require(exact["hold_active"] is False and exact["mismatches"] == [], "exact capture must not create hold")
    require(not validate(exact), "exact non-hold status must validate")

    sha_drift_capture = exact_capture()
    sha_drift_capture["stable_roots"]["CURRENT_STATE.json"]["sha256"] = "0" * 64
    sha_drift = build(sha_drift_capture)
    require(sha_drift["verdict"] == "HOLD_PROVIDER_DRIFT_DETECTED", "sha drift must HOLD")
    require(sha_drift["operator_state"] == "DRIFT_HOLD", "sha drift must project DRIFT_HOLD")
    require(any(row["field"] == "sha256" for row in sha_drift["mismatches"]), "sha drift mismatch missing")
    require(not validate(sha_drift), "sha drift status must validate structurally")

    metadata_capture = exact_capture()
    metadata_capture["stable_roots"]["ROLE_INDEX.json"]["modified_time"] = "2026-08-12T00:00:00Z"
    metadata = build(metadata_capture)
    require(metadata["verdict"] == "HOLD_PROVIDER_DRIFT_DETECTED", "metadata rewrite must HOLD")
    require(any(row["field"] == "modified_time" for row in metadata["mismatches"]), "metadata mismatch missing")

    pointer_capture = exact_capture()
    pointer_capture["stable_roots"]["CURRENT_STATE.json"]["modified_time"] = "2026-08-12T00:01:00Z"
    pointer = build(pointer_capture)
    require(pointer["verdict"] == "HOLD_PROVIDER_DRIFT_DETECTED", "pointer order drift must HOLD")
    require(any(row["field"] == "pointer_order" for row in pointer["mismatches"]), "pointer order mismatch missing")

    invalid_capture = exact_capture()
    invalid_capture["stable_roots"].pop("ROLE_VIEWS.json")
    invalid = build(invalid_capture)
    require(invalid["verdict"] == "HOLD_INVALID_OR_INCOMPLETE_CAPTURE", "missing root must be invalid HOLD")
    require(invalid["operator_state"] == "INVALID_CAPTURE_HOLD", "invalid capture must not be drift")
    require(invalid["mismatches"] == [], "invalid capture must not fabricate drift mismatches")
    require(not validate(invalid), "invalid capture diagnostic must validate structurally")

    old_capture = exact_capture()
    current_observed = parse_time(load(EVIDENCE)["observed_at"])
    old_capture["observed_at"] = (current_observed - timedelta(minutes=1)).isoformat()
    expired = build(old_capture, "2026-08-12T11:00:00+07:00")
    require(expired["verdict"] == "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED", "expired lease with old capture must HOLD for recapture")
    require(expired["operator_state"] == "EXPIRED", "expired recapture must not be drift")
    require(expired["mismatches"] == [], "expired recapture must not fabricate drift mismatches")

    leaked = copy.deepcopy(sha_drift)
    leaked["safety"]["root_write_authorized"] = True
    require("diagnostic_authority_leak:root_write_authorized" in validate(leaked), "root-write authority leak not detected")

    fake_neutral = neutral_status()
    fake_neutral["absence_does_not_prove_no_drift"] = False
    require("absence_semantics_overclaim" in validate(fake_neutral), "neutral no-drift overclaim not detected")

    fake_drift = copy.deepcopy(sha_drift)
    fake_drift["mismatches"] = []
    require("drift_mismatches_missing" in validate(fake_drift), "drift without mismatches not detected")

    print("PROVIDER_DRIFT_HOLD_DIAGNOSTIC_PROJECTION_V1_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
