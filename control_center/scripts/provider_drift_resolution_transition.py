from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from validate_provider_snapshot_freshness import EXPECTED_ROOTS, EVIDENCE, parse_time

BASE = Path(__file__).resolve().parents[1]
DIAGNOSTIC = BASE / "data" / "provider_refresh_controller_status.current.v1.json"
OUTPUT = BASE / "data" / "provider_drift_resolution.generated.v1.json"

SCHEMA = "control_center.provider_drift_resolution.v1"
PROJECTION_KIND = "NON_AUTHORITY_PROVIDER_DRIFT_RESOLUTION_TRANSITION"
DRIFT_VERDICT = "HOLD_PROVIDER_DRIFT_DETECTED"
NO_ACTIVE = "NO_ACTIVE_DRIFT_HOLD"
UNRESOLVED = "DRIFT_HOLD_UNRESOLVED"
RESOLVED = "RESOLVED_BY_NEWER_EXACT_CAPTURE"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def serialize(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def drift_fingerprint(diagnostic: dict[str, Any]) -> str:
    payload = {
        "verdict": diagnostic.get("verdict"),
        "source_capture": diagnostic.get("source_capture"),
        "controller_errors": diagnostic.get("controller_errors", []),
        "mismatches": diagnostic.get("mismatches", []),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safety_block() -> dict[str, Any]:
    return {
        "resolution_grants_authority": False,
        "provider_write_authorized": False,
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


def evidence_exact_errors(evidence: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if evidence.get("schema") != "control_center.provider_freshness_evidence.v1":
        errors.append("evidence_schema_mismatch")
    if evidence.get("freshness_status") != "FRESH_AT_CAPTURE":
        errors.append("evidence_not_fresh_at_capture")
    if evidence.get("continuous_freshness") is not False:
        errors.append("continuous_freshness_not_false")
    if set(evidence.get("stable_roots", {})) != set(EXPECTED_ROOTS):
        errors.append("stable_root_set_mismatch")
    readback = evidence.get("readback_result", {})
    for key in (
        "all_five_exact_at_capture",
        "pointer_last_by_provider_modified_time",
        "authority_critical_snapshot_match",
    ):
        if readback.get(key) is not True:
            errors.append(f"readback_not_true:{key}")
    try:
        parse_time(str(evidence.get("observed_at", "")))
    except (TypeError, ValueError):
        errors.append("evidence_observed_at_invalid")
    return errors


def build_transition(diagnostic: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    verdict = str(diagnostic.get("verdict", ""))
    active_drift = verdict == DRIFT_VERDICT and diagnostic.get("hold_active") is True
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "projection_kind": PROJECTION_KIND,
        "source_diagnostic_verdict": verdict,
        "source_drift_fingerprint": None,
        "source_drift_observed_at": None,
        "resolution_evidence_observed_at": None,
        "transition_state": NO_ACTIVE,
        "active_drift_hold_before": active_drift,
        "active_drift_hold_after": active_drift,
        "absence_does_not_prove_no_drift": True,
        "resolution": None,
        "reasons": [],
        "invariants": {
            "silent_clear_forbidden": True,
            "strictly_newer_exact_evidence_required": True,
            "resolution_bound_to_drift_fingerprint": True,
            "system_attention_clear_requires_matching_resolution": True,
        },
        "safety": safety_block(),
    }

    if not active_drift:
        base["reasons"] = ["no_active_provider_drift_hold"]
        return base

    fingerprint = drift_fingerprint(diagnostic)
    base["source_drift_fingerprint"] = fingerprint
    source_capture = diagnostic.get("source_capture") or {}
    drift_observed_at = source_capture.get("observed_at")
    base["source_drift_observed_at"] = drift_observed_at
    base["transition_state"] = UNRESOLVED
    base["active_drift_hold_after"] = True

    exact_errors = evidence_exact_errors(evidence)
    if exact_errors:
        base["reasons"] = exact_errors
        return base

    evidence_observed_at = evidence.get("observed_at")
    base["resolution_evidence_observed_at"] = evidence_observed_at
    try:
        drift_time = parse_time(str(drift_observed_at or ""))
    except (TypeError, ValueError):
        base["reasons"] = ["drift_source_capture_observed_at_invalid"]
        return base
    evidence_time = parse_time(str(evidence_observed_at))
    if evidence_time <= drift_time:
        base["reasons"] = ["strictly_newer_exact_capture_required"]
        return base

    base["transition_state"] = RESOLVED
    base["active_drift_hold_after"] = False
    base["reasons"] = []
    base["resolution"] = {
        "source_drift_fingerprint": fingerprint,
        "drift_capture_observed_at": drift_observed_at,
        "resolution_evidence_observed_at": evidence_observed_at,
        "strictly_newer": True,
        "all_five_exact_at_capture": True,
        "pointer_last_by_provider_modified_time": True,
        "authority_critical_snapshot_match": True,
        "clears_system_attention_for_matching_fingerprint_only": True,
        "remediation_authorized": False,
    }
    return base


def validate_transition(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if data.get("projection_kind") != PROJECTION_KIND:
        errors.append("projection_kind_mismatch")
    state = data.get("transition_state")
    if state not in {NO_ACTIVE, UNRESOLVED, RESOLVED}:
        errors.append("transition_state_invalid")
    if data.get("absence_does_not_prove_no_drift") is not True:
        errors.append("absence_semantics_overclaim")

    if state == NO_ACTIVE:
        if data.get("active_drift_hold_before") is not False or data.get("active_drift_hold_after") is not False:
            errors.append("no_active_state_hold_mismatch")
        if data.get("source_drift_fingerprint") is not None:
            errors.append("no_active_has_drift_fingerprint")
        if data.get("resolution") is not None:
            errors.append("no_active_has_resolution")
    elif state == UNRESOLVED:
        if data.get("active_drift_hold_before") is not True or data.get("active_drift_hold_after") is not True:
            errors.append("unresolved_hold_state_mismatch")
        if not data.get("source_drift_fingerprint"):
            errors.append("unresolved_fingerprint_missing")
        if data.get("resolution") is not None:
            errors.append("unresolved_has_resolution")
        if not data.get("reasons"):
            errors.append("unresolved_reason_missing")
    elif state == RESOLVED:
        if data.get("active_drift_hold_before") is not True or data.get("active_drift_hold_after") is not False:
            errors.append("resolved_hold_state_mismatch")
        resolution = data.get("resolution")
        if not isinstance(resolution, dict):
            errors.append("resolved_resolution_missing")
            resolution = {}
        if resolution.get("source_drift_fingerprint") != data.get("source_drift_fingerprint"):
            errors.append("resolved_fingerprint_mismatch")
        if resolution.get("strictly_newer") is not True:
            errors.append("resolved_not_strictly_newer")
        for key in (
            "all_five_exact_at_capture",
            "pointer_last_by_provider_modified_time",
            "authority_critical_snapshot_match",
            "clears_system_attention_for_matching_fingerprint_only",
        ):
            if resolution.get(key) is not True:
                errors.append(f"resolved_proof_not_true:{key}")
        if resolution.get("remediation_authorized") is not False:
            errors.append("resolved_remediation_authority_leak")
        try:
            drift_time = parse_time(str(data.get("source_drift_observed_at")))
            resolution_time = parse_time(str(data.get("resolution_evidence_observed_at")))
            if resolution_time <= drift_time:
                errors.append("resolved_time_not_strictly_newer")
        except (TypeError, ValueError):
            errors.append("resolved_timestamp_invalid")

    invariants = data.get("invariants", {})
    for key in (
        "silent_clear_forbidden",
        "strictly_newer_exact_evidence_required",
        "resolution_bound_to_drift_fingerprint",
        "system_attention_clear_requires_matching_resolution",
    ):
        if invariants.get(key) is not True:
            errors.append(f"invariant_not_true:{key}")

    safety = data.get("safety", {})
    for key in (
        "resolution_grants_authority",
        "provider_write_authorized",
        "root_write_authorized",
        "registry_write_authorized",
        "runtime_mutation_authorized",
        "routing_mutation_authorized",
        "dispatch_authorized",
        "apply_authorized",
        "execution_authorized",
        "deploy_authorized",
        "external_message_authorized",
        "can_trade",
        "self_application",
    ):
        if safety.get(key) is not False:
            errors.append(f"safety_not_false:{key}")
    if safety.get("capital_permission") != "DENY":
        errors.append("capital_permission_not_deny")
    return errors


def self_test() -> None:
    evidence = load(EVIDENCE)
    neutral = build_transition({"verdict": "NO_HOLD_DIAGNOSTIC_RECORDED", "hold_active": False}, evidence)
    assert neutral["transition_state"] == NO_ACTIVE
    assert validate_transition(neutral) == []

    drift = {
        "verdict": DRIFT_VERDICT,
        "hold_active": True,
        "source_capture": {"observed_at": "2026-08-12T04:00:00+07:00"},
        "controller_errors": ["provider_drift:CURRENT_STATE.json:sha256"],
        "mismatches": [{"root": "CURRENT_STATE.json", "field": "sha256", "expected": "a", "observed": "b"}],
    }
    resolved = build_transition(drift, evidence)
    assert resolved["transition_state"] == RESOLVED
    assert resolved["active_drift_hold_after"] is False
    assert validate_transition(resolved) == []

    equal_evidence = deepcopy(evidence)
    equal_evidence["observed_at"] = "2026-08-12T04:00:00+07:00"
    unresolved = build_transition(drift, equal_evidence)
    assert unresolved["transition_state"] == UNRESOLVED
    assert "strictly_newer_exact_capture_required" in unresolved["reasons"]
    assert validate_transition(unresolved) == []

    bad_evidence = deepcopy(evidence)
    bad_evidence["readback_result"]["all_five_exact_at_capture"] = False
    unresolved = build_transition(drift, bad_evidence)
    assert unresolved["transition_state"] == UNRESOLVED
    assert "readback_not_true:all_five_exact_at_capture" in unresolved["reasons"]
    assert validate_transition(unresolved) == []

    mutated = deepcopy(resolved)
    mutated["resolution"]["source_drift_fingerprint"] = "wrong"
    assert "resolved_fingerprint_mismatch" in validate_transition(mutated)

    mutated = deepcopy(resolved)
    mutated["safety"]["root_write_authorized"] = True
    assert "safety_not_false:root_write_authorized" in validate_transition(mutated)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/validate Provider Drift Resolution Transition V1.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("PROVIDER_DRIFT_RESOLUTION_TRANSITION_ADVERSARIAL_TEST_PASS")
        return 0

    built = build_transition(load(DIAGNOSTIC), load(EVIDENCE))
    errors = validate_transition(built)
    if errors:
        raise SystemExit(";".join(errors))
    if args.check:
        committed = load(OUTPUT)
        if committed != built:
            raise SystemExit("provider_drift_resolution_generated_mismatch")
        print("PROVIDER_DRIFT_RESOLUTION_TRANSITION_VALIDATION_PASS")
        return 0

    OUTPUT.write_text(serialize(built), encoding="utf-8")
    print(str(OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
