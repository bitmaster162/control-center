from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Mapping, Sequence


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def audit_partition(
    *,
    universe_id: str,
    total: int,
    components: Mapping[str, int],
    declared_disjoint: bool = True,
) -> dict[str, Any]:
    """Audit a numerical partition without guessing overlap semantics.

    `declared_disjoint=True` means the components are claimed to be a complete,
    non-overlapping partition of the same universe. Any mismatch is material.
    When False, a sum above total is not automatically false, but an explicit
    overlap matrix is required before the figures can be used as a partition.
    """
    if not universe_id.strip():
        raise ValueError("universe_id is required")
    if not isinstance(total, int) or total < 0:
        raise ValueError("total must be a non-negative integer")
    normalized: dict[str, int] = {}
    for name, value in components.items():
        if not str(name).strip() or not isinstance(value, int) or value < 0:
            raise ValueError("components must have non-empty names and non-negative integer values")
        normalized[str(name)] = value
    component_sum = sum(normalized.values())
    delta = component_sum - total
    if declared_disjoint:
        status = "PASS" if delta == 0 else "ARITHMETIC_PARTITION_INCONSISTENCY"
        overlap_matrix_required = False
    else:
        status = "PASS_NON_EXHAUSTIVE" if component_sum <= total else "OVERLAP_OR_UNIVERSE_MISMATCH"
        overlap_matrix_required = component_sum > total
    result = {
        "schema_version": 1,
        "universe_id": universe_id,
        "total": total,
        "components": normalized,
        "component_sum": component_sum,
        "delta": delta,
        "declared_disjoint": declared_disjoint,
        "overlap_matrix_required": overlap_matrix_required,
        "status": status,
        "can_trade": False,
    }
    result["audit_sha256"] = _digest(result)
    return result


def audit_occurrence_family(
    occurrences: Sequence[Mapping[str, Any]],
    *,
    family_key: str = "sha256",
) -> dict[str, Any]:
    """Separate physical occurrences from unique content/evidence families."""
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in occurrences:
        key = str(row.get(family_key, "")).strip()
        if not key:
            raise ValueError(f"missing family key: {family_key}")
        families[key].append(dict(row))
    family_rows = []
    for key, rows in sorted(families.items()):
        family_rows.append({
            "family_id": key,
            "occurrence_count": len(rows),
            "occurrences": rows,
        })
    result = {
        "schema_version": 1,
        "family_key": family_key,
        "occurrence_count": len(occurrences),
        "unique_family_count": len(family_rows),
        "duplicate_occurrence_count": len(occurrences) - len(family_rows),
        "families": family_rows,
        "status": "PASS",
        "can_trade": False,
    }
    result["audit_sha256"] = _digest(result)
    return result


def audit_authority_surfaces(
    surfaces: Sequence[Mapping[str, Any]],
    *,
    single_effect_broker_verified: bool,
) -> dict[str, Any]:
    """Detect more than one current mutable authority surface.

    A surface is counted when it is both mutable and current-authoritative. This
    deliberately distinguishes specifications, shadows and read-only projections.
    """
    normalized = []
    active = []
    for row in surfaces:
        item = {
            "surface_id": str(row.get("surface_id", "")).strip(),
            "root_or_target": str(row.get("root_or_target", "")).strip(),
            "mutable": bool(row.get("mutable", False)),
            "current_authority": bool(row.get("current_authority", False)),
            "evidence_state": str(row.get("evidence_state", "UNKNOWN")),
            "notes": str(row.get("notes", "")),
        }
        if not item["surface_id"]:
            raise ValueError("surface_id is required")
        normalized.append(item)
        if item["mutable"] and item["current_authority"]:
            active.append(item["surface_id"])
    if len(active) <= 1:
        status = "PASS_SINGLE_AUTHORITY"
    elif single_effect_broker_verified:
        status = "PASS_MULTIPLE_TARGETS_ONE_BROKER"
    else:
        status = "AUTHORITY_SURFACE_MULTIPLICITY"
    result = {
        "schema_version": 1,
        "surfaces": normalized,
        "active_mutable_authority_surfaces": active,
        "active_mutable_authority_count": len(active),
        "single_effect_broker_verified": single_effect_broker_verified,
        "status": status,
        "can_trade": False,
    }
    result["audit_sha256"] = _digest(result)
    return result



RECOVERY_ARTIFACT_ROLES = {
    "PRIMARY_SOURCE",
    "DERIVATIVE_REPORT",
    "AGENT_RETURN",
    "CONTROL_METADATA",
    "RECOVERY_SELF_DERIVATIVE",
    "RESTRICTED_SECRET_BEARING",
    "UNKNOWN",
}


def audit_recovery_provenance(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    credential_values_output_false: bool,
    no_source_effect_proof_claimed: bool,
    no_secret_content_proof_inferred: bool,
    claimed_primary_coverage_count: int | None,
    unsafe_count_label: str,
    unsafe_non_pointer_count: int,
    secret_scanner_claimed_complete: bool,
    secret_findings_escaped_scan: int,
) -> dict[str, Any]:
    """Audit a recovery package's provenance and secrecy boundary.

    The audit intentionally separates copy/source-effect safety from content
    secrecy. Secret values are never accepted as input; callers pass only
    counts and fingerprints in artifact metadata.
    """
    normalized: list[dict[str, Any]] = []
    for row in artifacts:
        role = str(row.get("artifact_role", "UNKNOWN")).strip().upper()
        if role not in RECOVERY_ARTIFACT_ROLES:
            raise ValueError(f"unsupported artifact_role: {role}")
        derivation_depth = int(row.get("derivation_depth", 0))
        if derivation_depth < 0:
            raise ValueError("derivation_depth must be non-negative")
        secret_findings = int(row.get("secret_finding_count", 0))
        if secret_findings < 0:
            raise ValueError("secret_finding_count must be non-negative")
        item = {
            "artifact_id": str(row.get("artifact_id", "")).strip(),
            "path": str(row.get("path", "")).strip(),
            "sha256": str(row.get("sha256", "")).strip(),
            "artifact_role": role,
            "derivation_depth": derivation_depth,
            "copied": bool(row.get("copied", False)),
            "primary_source_eligible": bool(row.get("primary_source_eligible", False)),
            "secret_finding_count": secret_findings,
        }
        if not item["artifact_id"]:
            raise ValueError("artifact_id is required")
        normalized.append(item)

    copied = [row for row in normalized if row["copied"]]
    self_ingested = [
        row for row in copied
        if row["artifact_role"] == "RECOVERY_SELF_DERIVATIVE" or row["derivation_depth"] > 0
    ]
    control_artifacts = [
        row for row in copied
        if row["artifact_role"] in {"CONTROL_METADATA", "RECOVERY_SELF_DERIVATIVE"}
    ]
    primary_eligible = [row for row in copied if row["primary_source_eligible"]]
    secret_count = sum(row["secret_finding_count"] for row in copied)

    statuses: list[str] = []
    if self_ingested:
        statuses.append("RECOVERY_SELF_INGESTION")
    if credential_values_output_false and secret_count > 0:
        statuses.append("CONTENT_SECRET_SAFETY_FALSE_CLAIM")
    if (
        claimed_primary_coverage_count is not None
        and claimed_primary_coverage_count > len(primary_eligible)
        and control_artifacts
    ):
        statuses.append("CONTROL_ARTIFACT_COVERAGE_INFLATION")
    if no_source_effect_proof_claimed and no_secret_content_proof_inferred:
        statuses.append("PROOF_SCOPE_CONFLATION")
    if unsafe_count_label == "excluded_pointer_only" and unsafe_non_pointer_count > 0:
        statuses.append("UNSAFE_ROW_LABEL_MISMATCH")
    if secret_scanner_claimed_complete and secret_findings_escaped_scan > 0:
        statuses.append("SECRET_SCANNER_COVERAGE_GAP")

    result = {
        "schema_version": 1,
        "artifact_count": len(normalized),
        "copied_count": len(copied),
        "primary_source_eligible_count": len(primary_eligible),
        "control_or_self_derivative_count": len(control_artifacts),
        "self_ingested_count": len(self_ingested),
        "secret_finding_count": secret_count,
        "claims": {
            "credential_values_output_false": credential_values_output_false,
            "no_source_effect_proof_claimed": no_source_effect_proof_claimed,
            "no_secret_content_proof_inferred": no_secret_content_proof_inferred,
            "claimed_primary_coverage_count": claimed_primary_coverage_count,
            "unsafe_count_label": unsafe_count_label,
            "unsafe_non_pointer_count": unsafe_non_pointer_count,
            "secret_scanner_claimed_complete": secret_scanner_claimed_complete,
            "secret_findings_escaped_scan": secret_findings_escaped_scan,
        },
        "self_ingested_artifact_ids": [row["artifact_id"] for row in self_ingested],
        "statuses": sorted(set(statuses)),
        "status": "PASS" if not statuses else "REVISE",
        "can_trade": False,
    }
    result["audit_sha256"] = _digest(result)
    return result


def recovery_provenance_audit_event(
    *,
    task_id: str,
    step_id: str,
    audit: Mapping[str, Any],
    evidence_refs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    statuses = set(str(value) for value in audit.get("statuses", []))
    digest = _digest(dict(audit))
    return {
        "schema_version": 1,
        "event_id": "RP-" + digest[:20],
        "task_id": task_id,
        "step_id": step_id,
        "event_type": "RECOVERY_PROVENANCE_AUDIT",
        "actor": "HANRI_R28",
        "goal": "Audit recovery provenance, self-ingestion and secret-content boundaries.",
        "human_summary": "Recovery package provenance and content-safety audit.",
        "checks": {
            "changed_evidence": True,
            "recovery_self_ingestion": "RECOVERY_SELF_INGESTION" in statuses,
            "content_secret_safety_false_claim": "CONTENT_SECRET_SAFETY_FALSE_CLAIM" in statuses,
            "control_artifact_coverage_inflation": "CONTROL_ARTIFACT_COVERAGE_INFLATION" in statuses,
            "proof_scope_conflation": "PROOF_SCOPE_CONFLATION" in statuses,
            "unsafe_row_label_mismatch": "UNSAFE_ROW_LABEL_MISMATCH" in statuses,
            "secret_scanner_coverage_gap": "SECRET_SCANNER_COVERAGE_GAP" in statuses,
        },
        "payload": {"recovery_provenance_audit": dict(audit)},
        "evidence_refs": [dict(row) for row in evidence_refs],
        "recursion_depth": 0,
        "can_trade": False,
    }

def truth_kernel_audit_event(
    *,
    task_id: str,
    step_id: str,
    partition_audits: Sequence[Mapping[str, Any]] = (),
    authority_audit: Mapping[str, Any] | None = None,
    count_universes_mixed: bool = False,
    spec_claimed_current_implementation: bool = False,
    implementation_receipt_present: bool = False,
    proof_ledger_claimed: bool = False,
    proof_identity_fields_present: bool = False,
    evidence_refs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    arithmetic_bad = any(
        str(row.get("status")) == "ARITHMETIC_PARTITION_INCONSISTENCY"
        for row in partition_audits
    )
    overlap_unresolved = any(
        str(row.get("status")) == "OVERLAP_OR_UNIVERSE_MISMATCH"
        for row in partition_audits
    )
    authority_bad = bool(authority_audit) and str(authority_audit.get("status")) == "AUTHORITY_SURFACE_MULTIPLICITY"
    payload = {
        "partition_audits": [dict(row) for row in partition_audits],
        "authority_audit": dict(authority_audit or {}),
    }
    digest = _digest(payload)
    return {
        "schema_version": 1,
        "event_id": "TK-" + digest[:20],
        "task_id": task_id,
        "step_id": step_id,
        "event_type": "TRUTH_KERNEL_AUDIT",
        "actor": "HANRI_R28",
        "goal": "Audit numerical universes, authority surfaces and report-to-implementation promotion.",
        "human_summary": "Truth-kernel audit of counts, authority and proof semantics.",
        "checks": {
            "changed_evidence": True,
            "partition_declared": bool(partition_audits),
            "arithmetic_partition_inconsistent": arithmetic_bad,
            "overlap_or_universe_mismatch": overlap_unresolved,
            "count_universes_mixed": count_universes_mixed,
            "authority_surface_multiplicity": authority_bad,
            "spec_claimed_current_implementation": spec_claimed_current_implementation,
            "implementation_receipt_present": implementation_receipt_present,
            "proof_ledger_claimed": proof_ledger_claimed,
            "proof_identity_fields_present": proof_identity_fields_present,
        },
        "payload": payload,
        "evidence_refs": [dict(row) for row in evidence_refs],
        "recursion_depth": 0,
        "can_trade": False,
    }
