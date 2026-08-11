from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from provider_freshness_refresh_controller import classify_refresh
from validate_provider_snapshot_freshness import EVIDENCE, RESEAL, SNAPSHOT, git_blob_sha, load, parse_time


def make_capture(evidence, *, observed_at=None):
    return {
        "schema": "control_center.provider_refresh_capture.v1",
        "capture_kind": "READ_ONLY_PROVIDER_CAPTURE",
        "observed_at": observed_at or evidence["observed_at"],
        "provider": "GOOGLE_DRIVE_DIRECT_READBACK",
        "stable_roots": deepcopy(evidence["stable_roots"]),
        "informational": {
            "pre_capture_live_pr_head_sha": "20f0ec92ec8bdc65a455526532e8d150e53cd617"
        },
        "safety": {
            "provider_mutation_performed": False,
            "authority_granted": False,
        },
    }


def classify(capture, *, now):
    snapshot = load(SNAPSHOT)
    evidence = load(EVIDENCE)
    reseal = load(RESEAL)
    return classify_refresh(
        snapshot,
        evidence,
        reseal,
        capture,
        now=now,
        snapshot_blob_sha=git_blob_sha(SNAPSHOT),
    )


def expect(capture, verdict, *, now):
    result = classify(capture, now=now)
    assert result["verdict"] == verdict, result
    return result


def main() -> int:
    evidence = load(EVIDENCE)
    observed = parse_time(evidence["observed_at"])

    same = make_capture(evidence)
    expect(same, "NO_REFRESH_REQUIRED_CURRENT_LEASE_FRESH", now=observed + timedelta(minutes=20))

    newer = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    allowed = expect(newer, "REFRESH_EVIDENCE_ONLY_ALLOWED", now=observed + timedelta(hours=1, minutes=1))
    assert allowed["refresh_allowed"] is True
    assert allowed["allowed_write_path"] == "control_center/data/provider_freshness_evidence.current.v1.json"
    assert allowed["all_other_writes_allowed"] is False
    candidate = allowed["candidate_evidence"]
    assert candidate["observed_at"] == newer["observed_at"]
    assert candidate["continuous_freshness"] is False
    assert candidate["safety"]["evidence_grants_authority"] is False
    assert candidate["safety"]["root_write_authorized"] is False
    assert candidate["safety"]["registry_write_authorized"] is False
    assert candidate["safety"]["deploy_authorized"] is False
    assert candidate["safety"]["can_trade"] is False
    assert candidate["safety"]["capital_permission"] == "DENY"

    expired_same = make_capture(evidence)
    expect(expired_same, "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED", now=observed + timedelta(hours=7))

    bad = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    bad["stable_roots"]["CURRENT_STATE.json"]["sha256"] = "11" * 32
    expect(bad, "HOLD_PROVIDER_DRIFT_DETECTED", now=observed + timedelta(hours=1, minutes=1))

    bad = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    bad["stable_roots"]["MANIFEST.json"]["bytes"] += 1
    expect(bad, "HOLD_PROVIDER_DRIFT_DETECTED", now=observed + timedelta(hours=1, minutes=1))

    bad = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    bad["stable_roots"]["ROLE_INDEX.json"]["drive_file_id"] = "wrong"
    expect(bad, "HOLD_PROVIDER_DRIFT_DETECTED", now=observed + timedelta(hours=1, minutes=1))

    bad = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    bad["stable_roots"]["ROLE_VIEWS.json"]["modified_time"] = "2026-08-12T00:00:00Z"
    expect(bad, "HOLD_PROVIDER_DRIFT_DETECTED", now=observed + timedelta(hours=1, minutes=1))

    bad = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    bad["stable_roots"].pop("ROLE_VIEWS.json")
    expect(bad, "HOLD_INVALID_OR_INCOMPLETE_CAPTURE", now=observed + timedelta(hours=1, minutes=1))

    bad = make_capture(evidence, observed_at=(observed + timedelta(hours=1)).isoformat())
    bad["safety"]["authority_granted"] = True
    expect(bad, "HOLD_INVALID_OR_INCOMPLETE_CAPTURE", now=observed + timedelta(hours=1, minutes=1))

    future = make_capture(evidence, observed_at=(observed + timedelta(hours=2)).isoformat())
    expect(future, "HOLD_INVALID_OR_INCOMPLETE_CAPTURE", now=observed + timedelta(hours=1))

    print("PROVIDER_FRESHNESS_REFRESH_CONTROLLER_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
