from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

R8_1_CLOSURE_SCHEMA = "bitevo.shadow_writer_fencing_recovery_closure.v2"
AUTHORITY_ANCHOR_SCHEMA = "control_center.shadow_human_gate_writer_authority_anchor.v1"
PROJECTION_SCHEMA = "control_center.shadow_writer_recovery_projection.v2"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

CLOSURE_EFFECTS = {
    "human_gate_write": False,
    "credential_registry_write": False,
    "nonce_registry_write": False,
    "lease_registry_write": False,
    "commit_receipt_registry_write": False,
    "backend_write": False,
    "current_truth_apply": False,
    "registry_write": False,
    "ledger_write": False,
    "return_index_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}

CONTROL_EFFECTS = {
    "human_gate_write": False,
    "credential_registry_write": False,
    "nonce_registry_write": False,
    "lease_registry_write": False,
    "commit_receipt_registry_write": False,
    "backend_write": False,
    "current_truth_apply": False,
    "decision_ledger_write": False,
    "command_queue_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}


class WriterRecoveryProjectionV2Error(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WriterRecoveryProjectionV2Error(f"{field}_required")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise WriterRecoveryProjectionV2Error(f"{field}_must_be_sha256")
    return text


def _iso(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise WriterRecoveryProjectionV2Error(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise WriterRecoveryProjectionV2Error(f"{field}_timezone_required")
    return text


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise WriterRecoveryProjectionV2Error(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise WriterRecoveryProjectionV2Error(code)
    return supplied


def _verify_false_map(record: Mapping[str, Any], expected: Mapping[str, bool], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(expected):
        raise WriterRecoveryProjectionV2Error(f"{field}_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in expected):
        raise WriterRecoveryProjectionV2Error(f"{field}_effect_boundary_breached")


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise WriterRecoveryProjectionV2Error(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise WriterRecoveryProjectionV2Error(f"unsafe_{field}:{key}")


def build_writer_recovery_projection_v2(
    r8_1_closure: Mapping[str, Any],
    authority_anchor: Mapping[str, Any],
    *,
    expected_r8_1_closure_sha256: str,
    expected_authority_anchor_sha256: str,
    expected_authority_root_sha256: str,
    projected_at: str,
) -> dict[str, Any]:
    if not isinstance(r8_1_closure, Mapping) or r8_1_closure.get("schema") != R8_1_CLOSURE_SCHEMA:
        raise WriterRecoveryProjectionV2Error("closure_schema_mismatch")
    closure_sha = _verify_hash(
        r8_1_closure,
        "writer_fencing_recovery_closure_sha256",
        "closure_hash_mismatch",
    )
    if closure_sha != _sha(expected_r8_1_closure_sha256, "expected_r8_1_closure_sha256"):
        raise WriterRecoveryProjectionV2Error("closure_external_digest_mismatch")
    _verify_safety(r8_1_closure, "closure")
    _verify_false_map(r8_1_closure, CLOSURE_EFFECTS, "closure")
    if r8_1_closure.get("status") != "WRITER_FENCING_RECOVERY_HARDENED_SHADOW_ONLY":
        raise WriterRecoveryProjectionV2Error("closure_status_invalid")
    if r8_1_closure.get("decision") != "HOLD" or r8_1_closure.get("action") != "WAIT":
        raise WriterRecoveryProjectionV2Error("closure_gate_widening_forbidden")
    if r8_1_closure.get("paired_receipt_identity_verified") is not True or r8_1_closure.get("cross_plane_anchor_verified") is not True:
        raise WriterRecoveryProjectionV2Error("closure_hardening_guard_missing")
    if r8_1_closure.get("durable_commit_proven") is not False or r8_1_closure.get("human_gate_write_performed") is not False:
        raise WriterRecoveryProjectionV2Error("closure_durability_or_write_overclaim")
    if r8_1_closure.get("current_truth_promotion_allowed") is not False or r8_1_closure.get("apply_allowed") is not False:
        raise WriterRecoveryProjectionV2Error("closure_truth_or_apply_breached")
    if r8_1_closure.get("execution_authority") != "NONE" or r8_1_closure.get("can_execute") is not False:
        raise WriterRecoveryProjectionV2Error("closure_authority_breached")

    if not isinstance(authority_anchor, Mapping) or authority_anchor.get("schema") != AUTHORITY_ANCHOR_SCHEMA:
        raise WriterRecoveryProjectionV2Error("anchor_schema_mismatch")
    anchor_sha = _verify_hash(authority_anchor, "authority_anchor_sha256", "anchor_hash_mismatch")
    if anchor_sha != _sha(expected_authority_anchor_sha256, "expected_authority_anchor_sha256"):
        raise WriterRecoveryProjectionV2Error("anchor_external_digest_mismatch")
    root = _sha(expected_authority_root_sha256, "expected_authority_root_sha256")
    if authority_anchor.get("authority_root_sha256") != root:
        raise WriterRecoveryProjectionV2Error("anchor_root_mismatch")
    _verify_safety(authority_anchor, "anchor")
    _verify_false_map(authority_anchor, CONTROL_EFFECTS, "anchor")
    if r8_1_closure.get("authority_anchor_sha256") != anchor_sha or r8_1_closure.get("authority_root_sha256") != root:
        raise WriterRecoveryProjectionV2Error("closure_anchor_or_root_binding_mismatch")

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_role": "NON_AUTHORITY_WRITER_RECOVERY_PROJECTION_V2",
        "writer_fencing_recovery_closure_sha256": closure_sha,
        "authority_anchor_sha256": anchor_sha,
        "authority_root_sha256": root,
        "case_id": r8_1_closure["case_id"],
        "case_sha256": r8_1_closure["case_sha256"],
        "challenge_id": r8_1_closure["challenge_id"],
        "paired_receipt_identity": "VERIFIED_SHADOW_ONLY",
        "cross_plane_authority_root_anchor": "VERIFIED_SHADOW_ONLY",
        "durable_commit": "NOT_PROVEN",
        "current_truth_promotion_allowed": False,
        "apply": False,
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "decision": "HOLD",
        "action": "WAIT",
        "execution_authority": "NONE",
        "can_execute": False,
        "projected_at": _iso(projected_at, "projected_at"),
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(CONTROL_EFFECTS),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body
