from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

PROJECTION_SCHEMA = "control_center.shadow_replay_anchor_projection.v1"
AUTHORITY_ID = "control-center:R64"
AUTHORITY_GENERATION = "R64"
R64_PROVIDER_CAPTURE_AT = "2026-08-12T04:59:00+07:00"

R64_AUTHORITY = {
    "generation": "R64",
    "status": "R64_RESEALED_ALL_EXACT",
    "current_state_sha256": "701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68",
    "manifest_sha256": "383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d",
    "current_pointer_sha256": "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3",
}

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

MUTATIONS = {
    "current_truth": False,
    "command_queue": False,
    "decision_ledger": False,
    "return_registry": False,
    "human_gate": False,
    "continuity": False,
    "runtime": False,
    "trading": False,
    "capital": False,
}


class ReplayAnchorProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReplayAnchorProjectionError(f"{field}_required")
    return value.strip()


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ReplayAnchorProjectionError(f"{field}_must_be_sha256")
    return text


def _iso_epoch(value: Any, field: str) -> tuple[str, float]:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise ReplayAnchorProjectionError(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise ReplayAnchorProjectionError(f"{field}_timezone_required")
    return text, parsed.timestamp()


def authority_root_sha256() -> str:
    """Deterministic composite of the exact R64 authority-basis hashes.

    This is a projected replay reference, not a signature and not a fresh provider read.
    """
    return sha256_obj(R64_AUTHORITY)


def derive_case_binding_sha256(
    *,
    authority_id: str,
    authority_root_sha256: str,
    case_id: str,
    case_sha256: str,
    evidence_bundle_sha256: str,
) -> str:
    return sha256_obj(
        {
            "authority_id": _text(authority_id, "authority_id"),
            "authority_root_sha256": _sha256(authority_root_sha256, "authority_root_sha256"),
            "case_id": _text(case_id, "case_id"),
            "case_sha256": _sha256(case_sha256, "case_sha256"),
            "evidence_bundle_sha256": _sha256(evidence_bundle_sha256, "evidence_bundle_sha256"),
        }
    )


def build_replay_anchor_projection(
    *,
    case_id: str,
    case_sha256: str,
    evidence_bundle_sha256: str,
    frozen_at: str,
) -> dict[str, Any]:
    case = _text(case_id, "case_id")
    case_sha = _sha256(case_sha256, "case_sha256")
    evidence_sha = _sha256(evidence_bundle_sha256, "evidence_bundle_sha256")
    freeze_text, freeze_epoch = _iso_epoch(frozen_at, "frozen_at")
    capture_text, capture_epoch = _iso_epoch(R64_PROVIDER_CAPTURE_AT, "r64_provider_capture_at")
    if freeze_epoch + 1e-6 < capture_epoch:
        raise ReplayAnchorProjectionError("case_freeze_precedes_r64_root_capture")

    root_sha = authority_root_sha256()
    binding = derive_case_binding_sha256(
        authority_id=AUTHORITY_ID,
        authority_root_sha256=root_sha,
        case_id=case,
        case_sha256=case_sha,
        evidence_bundle_sha256=evidence_sha,
    )
    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_REPLAY_ANCHOR_PROJECTION",
        "authority_id": AUTHORITY_ID,
        "authority_generation": AUTHORITY_GENERATION,
        "authority_root_sha256": root_sha,
        "authority_root_basis": dict(R64_AUTHORITY),
        "root_effective_at": capture_text,
        "case_id": case,
        "case_sha256": case_sha,
        "evidence_bundle_sha256": evidence_sha,
        "case_binding_sha256": binding,
        "frozen_at": freeze_text,
        "expected_replay_reference": {
            "expected_authority_id": AUTHORITY_ID,
            "expected_root_sha256": root_sha,
            "expected_case_binding_sha256": binding,
        },
        "freshness": {
            "root_basis_capture_at": capture_text,
            "current_provider_freshness_claimed": False,
            "historical_replay_reference_only": True,
            "current_truth_promotion_allowed": False,
        },
        "trust_semantics": {
            "projection_is_not_current_truth": True,
            "projection_is_not_signature": True,
            "projected_hash_is_not_source_authenticity_by_itself": True,
            "independent_custody_or_signed_anchor_still_required_for_strong_authenticity": True,
            "replay_reference_does_not_grant_permission": True,
        },
        "apply": False,
        "mutations": dict(MUTATIONS),
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body


def validate_replay_anchor_projection(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, Mapping) or value.get("schema") != PROJECTION_SCHEMA:
        return ["wrong_projection_schema"]
    expected = sha256_obj({k: v for k, v in value.items() if k != "projection_sha256"})
    if value.get("projection_sha256") != expected:
        errors.append("projection_hash_mismatch")
    if value.get("projection_kind") != "NON_AUTHORITY_REPLAY_ANCHOR_PROJECTION":
        errors.append("projection_kind_invalid")
    if value.get("authority_id") != AUTHORITY_ID or value.get("authority_generation") != AUTHORITY_GENERATION:
        errors.append("authority_identity_mismatch")
    if value.get("authority_root_sha256") != authority_root_sha256():
        errors.append("authority_root_mismatch")
    if value.get("authority_root_basis") != R64_AUTHORITY:
        errors.append("authority_basis_mismatch")
    if value.get("apply") is not False:
        errors.append("apply_forbidden")
    mutations = value.get("mutations")
    if not isinstance(mutations, Mapping) or mutations != MUTATIONS:
        errors.append("mutation_boundary_breached")
    if value.get("effect_candidates_created") != 0 or value.get("executions_authorized") != 0:
        errors.append("effect_count_breached")
    freshness = value.get("freshness", {})
    if freshness.get("current_provider_freshness_claimed") is not False:
        errors.append("freshness_overclaim")
    if freshness.get("historical_replay_reference_only") is not True:
        errors.append("historical_only_flag_missing")
    if freshness.get("current_truth_promotion_allowed") is not False:
        errors.append("current_truth_promotion_forbidden")
    safety = value.get("safety")
    if not isinstance(safety, Mapping):
        errors.append("safety_missing")
    else:
        for key, expected_value in REQUIRED_SAFETY.items():
            if safety.get(key) != expected_value or type(safety.get(key)) is not type(expected_value):
                errors.append(f"unsafe:{key}")
    return errors
