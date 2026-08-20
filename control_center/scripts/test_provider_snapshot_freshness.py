from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from validate_provider_snapshot_freshness import (
    EVIDENCE,
    RESEAL,
    SNAPSHOT,
    git_blob_sha,
    load,
    parse_time,
    validate,
)


def expect_marker(name: str, snapshot, evidence, reseal, marker: str, *, now) -> None:
    errors = validate(snapshot, evidence, reseal, now=now, snapshot_blob_sha=git_blob_sha(SNAPSHOT))
    if not any(marker in error for error in errors):
        raise AssertionError(f"{name}: expected {marker}, got {errors}")


def main() -> int:
    snapshot = load(SNAPSHOT)
    evidence = load(EVIDENCE)
    reseal = load(RESEAL)
    observed = parse_time(evidence["observed_at"])
    baseline_now = observed + timedelta(minutes=5)

    baseline = validate(snapshot, evidence, reseal, now=baseline_now, snapshot_blob_sha=git_blob_sha(SNAPSHOT))
    assert baseline == [], baseline

    bad = deepcopy(evidence)
    bad["stable_roots"]["CURRENT_POINTER.json"]["sha256"] = "11" * 32
    expect_marker("pointer_sha_tamper", snapshot, bad, reseal, "snapshot_sha_mismatch:CURRENT_POINTER.json", now=baseline_now)

    bad = deepcopy(evidence)
    bad["stable_roots"]["CURRENT_STATE.json"]["bytes"] += 1
    expect_marker("state_bytes_tamper", snapshot, bad, reseal, "byte_length_mismatch:CURRENT_STATE.json", now=baseline_now)

    bad = deepcopy(evidence)
    bad["stable_roots"]["MANIFEST.json"]["sha256"] = "22" * 32
    expect_marker("manifest_sha_tamper", snapshot, bad, reseal, "snapshot_sha_mismatch:MANIFEST.json", now=baseline_now)

    bad = deepcopy(evidence)
    bad["stable_roots"]["CURRENT_POINTER.json"]["modified_time"] = "2026-08-11T20:00:00Z"
    expect_marker("pointer_not_last", snapshot, bad, reseal, "current_pointer_not_latest_modified_root", now=baseline_now)

    stale_now = observed + timedelta(seconds=evidence["max_age_seconds"] + 1)
    expect_marker("expired_evidence", snapshot, deepcopy(evidence), reseal, "freshness_evidence_stale", now=stale_now)

    future = deepcopy(evidence)
    future["observed_at"] = (baseline_now + timedelta(seconds=301)).isoformat()
    expect_marker("future_evidence", snapshot, future, reseal, "freshness_evidence_from_future", now=baseline_now)

    bad = deepcopy(evidence)
    bad["stable_roots"].pop("ROLE_INDEX.json")
    expect_marker("missing_root", snapshot, bad, reseal, "stable_root_identity_set_mismatch", now=baseline_now)

    bad = deepcopy(evidence)
    bad["continuous_freshness"] = True
    expect_marker("continuous_overclaim", snapshot, bad, reseal, "continuous_freshness_overclaim", now=baseline_now)

    bad = deepcopy(evidence)
    bad["informational_self_referential"]["control_center_github_lane"]["authority_relevant"] = True
    expect_marker("self_reference_authority", snapshot, bad, reseal, "self_referential_head_authority_leak", now=baseline_now)

    bad = deepcopy(evidence)
    bad["safety"]["execution_authorized"] = True
    expect_marker("execution_authority_leak", snapshot, bad, reseal, "freshness_authority_leak:execution_authorized", now=baseline_now)

    bad = deepcopy(evidence)
    bad["source_snapshot"]["github_blob_sha"] = "00" * 20
    expect_marker("snapshot_blob_tamper", snapshot, bad, reseal, "snapshot_blob_binding_mismatch", now=baseline_now)

    print("PROVIDER_SNAPSHOT_FRESHNESS_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
