from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "data" / "provider_refresh_controller_status.current.v1.json"

SCHEMA = "control_center.provider_refresh_controller_status.v1"
PROJECTION_KIND = "NON_AUTHORITY_PROVIDER_REFRESH_DIAGNOSTIC"
NEUTRAL = "NO_HOLD_DIAGNOSTIC_RECORDED"
DRIFT = "HOLD_PROVIDER_DRIFT_DETECTED"
EXPIRED = "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED"
INVALID = "HOLD_INVALID_OR_INCOMPLETE_CAPTURE"
ALLOWED_FIELDS = {"drive_file_id", "sha256", "bytes", "modified_time", "pointer_order"}


def validate(status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if status.get("schema") != SCHEMA:
        errors.append("status_schema_mismatch")
    if status.get("projection_kind") != PROJECTION_KIND:
        errors.append("status_projection_kind_mismatch")
    if status.get("absence_does_not_prove_no_drift") is not True:
        errors.append("absence_semantics_overclaim")

    verdict = status.get("verdict")
    operator_state = status.get("operator_state")
    hold_active = status.get("hold_active")
    controller_errors = status.get("controller_errors")
    mismatches = status.get("mismatches")

    if not isinstance(controller_errors, list):
        errors.append("controller_errors_not_list")
        controller_errors = []
    if not isinstance(mismatches, list):
        errors.append("mismatches_not_list")
        mismatches = []

    if verdict == NEUTRAL:
        if operator_state != NEUTRAL:
            errors.append("neutral_operator_state_mismatch")
        if hold_active is not False:
            errors.append("neutral_hold_active")
        if status.get("source_capture") is not None:
            errors.append("neutral_source_capture_present")
        if controller_errors:
            errors.append("neutral_controller_errors_present")
        if mismatches:
            errors.append("neutral_mismatches_present")
        note = str(status.get("note", "")).lower()
        if "does not prove" not in note:
            errors.append("neutral_note_missing_uncertainty")
    elif verdict == DRIFT:
        if operator_state != "DRIFT_HOLD":
            errors.append("drift_operator_state_mismatch")
        if hold_active is not True:
            errors.append("drift_hold_not_active")
        if not status.get("source_capture"):
            errors.append("drift_source_capture_missing")
        if not controller_errors:
            errors.append("drift_controller_errors_missing")
        if not mismatches:
            errors.append("drift_mismatches_missing")
        for code in controller_errors:
            if not str(code).startswith(("provider_drift:", "provider_metadata_drift:")):
                errors.append(f"drift_unexpected_controller_error:{code}")
    elif verdict == EXPIRED:
        if operator_state != "EXPIRED":
            errors.append("expired_operator_state_mismatch")
        if hold_active is not True:
            errors.append("expired_hold_not_active")
        if mismatches:
            errors.append("expired_mislabeled_with_drift_mismatches")
    elif verdict == INVALID:
        if operator_state != "INVALID_CAPTURE_HOLD":
            errors.append("invalid_operator_state_mismatch")
        if hold_active is not True:
            errors.append("invalid_hold_not_active")
        if mismatches:
            errors.append("invalid_capture_mislabeled_as_drift")
    else:
        if str(verdict).startswith("HOLD_"):
            errors.append("unknown_hold_verdict")
        elif operator_state not in {"NO_HOLD", NEUTRAL}:
            errors.append("nonhold_operator_state_mismatch")
        if hold_active is not False:
            errors.append("nonhold_hold_active")
        if mismatches:
            errors.append("nonhold_mismatches_present")

    for idx, row in enumerate(mismatches):
        if not isinstance(row, dict):
            errors.append(f"mismatch_row_invalid:{idx}")
            continue
        if not row.get("root"):
            errors.append(f"mismatch_root_missing:{idx}")
        if row.get("field") not in ALLOWED_FIELDS:
            errors.append(f"mismatch_field_invalid:{idx}")
        if "expected" not in row or "observed" not in row:
            errors.append(f"mismatch_values_missing:{idx}")

    safety = status.get("safety", {})
    false_keys = (
        "diagnostic_grants_authority",
        "refresh_authorized",
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
    )
    for key in false_keys:
        if safety.get(key) is not False:
            errors.append(f"diagnostic_authority_leak:{key}")
    if safety.get("capital_permission") != "DENY":
        errors.append("diagnostic_capital_permission_mismatch")

    forbidden_keys = {
        "remediation_authorized",
        "auto_fix",
        "auto_repair",
        "root_write",
        "registry_write",
        "runtime_mutation",
        "deploy",
        "trade_authorized",
    }
    if any(key in status for key in forbidden_keys):
        errors.append("forbidden_top_level_remediation_field")

    return errors


def main() -> int:
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    errors = validate(status)
    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "gate": "PROVIDER_DRIFT_HOLD_DIAGNOSTIC_PROJECTION_V1",
        "verdict": status.get("verdict"),
        "operator_state": status.get("operator_state"),
        "errors": errors,
    }, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
