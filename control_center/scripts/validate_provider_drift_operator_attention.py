from __future__ import annotations

from build_provider_drift_operator_attention import (
    COMMAND_QUEUE,
    DIAGNOSTIC,
    DRIFT_VERDICT,
    NEUTRAL_VERDICT,
    OUTPUT,
    RESOLUTION,
    build_projection,
    load,
)
from provider_drift_resolution_transition import RESOLVED

EXPECTED_FALSE_SAFETY = {
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
}


def validate_projection(data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "control_center.provider_system_attention.v1":
        errors.append("schema_mismatch")
    if data.get("projection_kind") != "NON_AUTHORITY_OPERATOR_ATTENTION_PROJECTION":
        errors.append("projection_kind_mismatch")

    summary = data.get("summary", {})
    if summary.get("human_now_before") != summary.get("human_now_after"):
        errors.append("human_now_changed")
    if summary.get("effect_candidates_before") != summary.get("effect_candidates_after"):
        errors.append("effect_candidates_changed")

    invariants = data.get("invariants", {})
    expected_invariants = {
        "command_queue_mutated": False,
        "human_now_unchanged": True,
        "effect_candidates_unchanged": True,
        "human_gate_created": False,
        "effect_candidate_created": False,
        "command_created": False,
        "system_attention_grants_authority": False,
        "drift_alert_clear_requires_matching_resolution": True,
    }
    for key, expected in expected_invariants.items():
        if invariants.get(key) is not expected:
            errors.append(f"invariant_mismatch:{key}")

    safety = data.get("safety", {})
    for key in EXPECTED_FALSE_SAFETY:
        if safety.get(key) is not False:
            errors.append(f"safety_not_false:{key}")
    if safety.get("capital_permission") != "DENY":
        errors.append("capital_permission_not_deny")

    verdict = data.get("source_status_verdict")
    resolution_state = data.get("source_resolution_state")
    resolution_applied = data.get("resolution_applied")
    items = data.get("system_attention", [])
    if summary.get("system_attention_count") != len(items):
        errors.append("attention_count_mismatch")

    if verdict == DRIFT_VERDICT:
        if resolution_applied is True:
            if resolution_state != RESOLVED:
                errors.append("resolved_drift_resolution_state_mismatch")
            if items:
                errors.append("matching_resolution_must_clear_drift_attention")
            if not data.get("resolved_drift_fingerprint"):
                errors.append("resolved_drift_fingerprint_missing")
        else:
            if data.get("resolved_drift_fingerprint") is not None:
                errors.append("unresolved_drift_has_resolved_fingerprint")
            if len(items) != 1:
                errors.append("drift_must_emit_exactly_one_attention")
            else:
                item = items[0]
                expected = {
                    "id": "SYSATTN::PROVIDER_DRIFT_HOLD",
                    "state": "DRIFT_HOLD",
                    "severity": "HIGH",
                    "owner": "CONTROL_CENTER",
                    "source_verdict": DRIFT_VERDICT,
                    "requested_action": "READ_ONLY_PROVIDER_DRIFT_INVESTIGATION",
                    "human_now": False,
                    "human_gate": False,
                    "effect_candidate": False,
                    "dispatch_authorized": False,
                    "apply_authorized": False,
                    "execution_authorized": False,
                    "write_authorized": False,
                    "auto_fix": False,
                }
                for key, value in expected.items():
                    if item.get(key) != value:
                        errors.append(f"drift_item_mismatch:{key}")
    else:
        if resolution_applied is not False:
            errors.append("non_drift_must_not_apply_resolution")
        if data.get("resolved_drift_fingerprint") is not None:
            errors.append("non_drift_has_resolved_fingerprint")
        if items:
            errors.append("non_drift_verdict_must_not_emit_attention")

    if verdict == NEUTRAL_VERDICT and data.get("absence_does_not_prove_no_drift") is not True:
        errors.append("neutral_absence_semantic_missing")

    return errors


def main() -> int:
    committed = load(OUTPUT)
    deterministic = build_projection(load(DIAGNOSTIC), load(COMMAND_QUEUE), load(RESOLUTION))
    errors = validate_projection(committed)
    if committed != deterministic:
        errors.append("deterministic_projection_mismatch")
    if errors:
        raise SystemExit(";".join(errors))
    print("PROVIDER_DRIFT_OPERATOR_ATTENTION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
