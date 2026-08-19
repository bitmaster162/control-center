from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

LEGACY_RECOVERY_SCHEMA = "control_center.shadow_human_gate_crash_recovery_verification.v1"
LEGACY_LEASE_SCHEMA = "control_center.shadow_human_gate_writer_lease_snapshot.v1"
LEGACY_INDEX_SCHEMA = "control_center.shadow_human_gate_commit_receipt_index_snapshot.v1"
PAIRED_INDEX_SCHEMA = "control_center.shadow_human_gate_commit_receipt_index_snapshot.v2"
AUTHORITY_ANCHOR_SCHEMA = "control_center.shadow_human_gate_writer_authority_anchor.v1"
RECOVERY_V2_SCHEMA = "control_center.shadow_human_gate_crash_recovery_verification.v2"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

R8_EFFECTS = {
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

ALLOWED_RECOVERY = {
    "STALE_WRITER_FENCED_REACQUIRE_REQUIRED",
    "NO_WRITE_OBSERVED_RETRY_REQUIRES_FRESH_CAS",
    "WRITE_OBSERVED_RECEIPT_ABSENT_HOLD",
    "RECEIPT_INDEXED_DEDUP_NO_RETRY",
}


class HumanGateWriterFencingV2Error(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanGateWriterFencingV2Error(f"{field}_required")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HumanGateWriterFencingV2Error(f"{field}_must_be_sha256")
    return text


def _iso(value: Any, field: str) -> str:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise HumanGateWriterFencingV2Error(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise HumanGateWriterFencingV2Error(f"{field}_timezone_required")
    return text


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise HumanGateWriterFencingV2Error(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise HumanGateWriterFencingV2Error(code)
    return supplied


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise HumanGateWriterFencingV2Error(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise HumanGateWriterFencingV2Error(f"unsafe_{field}:{key}")


def _verify_effects(record: Mapping[str, Any], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(R8_EFFECTS):
        raise HumanGateWriterFencingV2Error(f"{field}_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in R8_EFFECTS):
        raise HumanGateWriterFencingV2Error(f"{field}_effect_boundary_breached")


def _verify_legacy_index(index: Mapping[str, Any], expected_sha256: str, expected_root: str) -> str:
    if not isinstance(index, Mapping) or index.get("schema") != LEGACY_INDEX_SCHEMA:
        raise HumanGateWriterFencingV2Error("legacy_index_schema_mismatch")
    digest = _verify_hash(index, "index_sha256", "legacy_index_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_legacy_index_sha256"):
        raise HumanGateWriterFencingV2Error("legacy_index_external_digest_mismatch")
    if index.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise HumanGateWriterFencingV2Error("legacy_index_authority_root_mismatch")
    _verify_safety(index, "legacy_index")
    _verify_effects(index, "legacy_index")
    commits = tuple(index.get("commit_ids") or ())
    keys = tuple(index.get("idempotency_key_sha256s") or ())
    if len(commits) != len(keys) or index.get("entry_count") != len(commits):
        raise HumanGateWriterFencingV2Error("legacy_index_count_mismatch")
    if len(set(commits)) != len(commits) or len(set(keys)) != len(keys):
        raise HumanGateWriterFencingV2Error("legacy_index_duplicates_forbidden")
    for i, value in enumerate(commits):
        _sha(value, f"legacy_index.commit_id[{i}]")
    for i, value in enumerate(keys):
        _sha(value, f"legacy_index.idempotency_key[{i}]")
    return digest


def _normalize_pair(entry: Mapping[str, Any], index: int) -> dict[str, str]:
    if not isinstance(entry, Mapping):
        raise HumanGateWriterFencingV2Error(f"receipt_pair[{index}]_must_be_object")
    return {
        "commit_id": _sha(entry.get("commit_id"), f"receipt_pair[{index}].commit_id"),
        "idempotency_key_sha256": _sha(
            entry.get("idempotency_key_sha256"), f"receipt_pair[{index}].idempotency_key_sha256"
        ),
        "receipt_reference_sha256": _sha(
            entry.get("receipt_reference_sha256"), f"receipt_pair[{index}].receipt_reference_sha256"
        ),
    }


def build_paired_commit_receipt_index_snapshot(
    legacy_index: Mapping[str, Any],
    receipt_pairs: Sequence[Mapping[str, Any]],
    *,
    expected_legacy_index_sha256: str,
    expected_authority_root_sha256: str,
) -> dict[str, Any]:
    legacy_sha = _verify_legacy_index(
        legacy_index, expected_legacy_index_sha256, expected_authority_root_sha256
    )
    if isinstance(receipt_pairs, (str, bytes)) or not isinstance(receipt_pairs, Sequence):
        raise HumanGateWriterFencingV2Error("receipt_pairs_must_be_sequence")
    pairs = tuple(_normalize_pair(entry, i) for i, entry in enumerate(receipt_pairs))
    commits = tuple(legacy_index.get("commit_ids") or ())
    keys = tuple(legacy_index.get("idempotency_key_sha256s") or ())
    if len(pairs) != len(commits):
        raise HumanGateWriterFencingV2Error("paired_index_entry_count_mismatch")
    seen_receipts: set[str] = set()
    for i, pair in enumerate(pairs):
        if pair["commit_id"] != commits[i] or pair["idempotency_key_sha256"] != keys[i]:
            raise HumanGateWriterFencingV2Error("paired_index_legacy_pair_position_mismatch")
        if pair["receipt_reference_sha256"] in seen_receipts:
            raise HumanGateWriterFencingV2Error("paired_index_receipt_reference_duplicate")
        seen_receipts.add(pair["receipt_reference_sha256"])
    body = {
        "schema": PAIRED_INDEX_SCHEMA,
        "index_id": _text(legacy_index.get("index_id"), "legacy_index.index_id"),
        "authority_root_sha256": _sha(expected_authority_root_sha256, "expected_authority_root_sha256"),
        "generation": legacy_index.get("generation"),
        "entries": pairs,
        "entry_count": len(pairs),
        "legacy_index_sha256": legacy_sha,
        "previous_index_sha256": _sha(
            legacy_index.get("previous_index_sha256"), "legacy_index.previous_index_sha256"
        ),
        "pair_identity_model": "FIRST_CLASS_COMMIT_IDEMPOTENCY_RECEIPT_REFERENCE",
        "receipt_reference_kind": "EXPECTED_RECEIPT_CANDIDATE_SHA256_SHADOW_ONLY",
        "write_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["index_sha256"] = sha256_obj(body)
    return body


def _verify_paired_index(
    index: Mapping[str, Any], expected_sha256: str, expected_root: str
) -> str:
    if not isinstance(index, Mapping) or index.get("schema") != PAIRED_INDEX_SCHEMA:
        raise HumanGateWriterFencingV2Error("paired_index_schema_mismatch")
    digest = _verify_hash(index, "index_sha256", "paired_index_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_paired_index_sha256"):
        raise HumanGateWriterFencingV2Error("paired_index_external_digest_mismatch")
    if index.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise HumanGateWriterFencingV2Error("paired_index_authority_root_mismatch")
    _verify_safety(index, "paired_index")
    _verify_effects(index, "paired_index")
    if index.get("pair_identity_model") != "FIRST_CLASS_COMMIT_IDEMPOTENCY_RECEIPT_REFERENCE":
        raise HumanGateWriterFencingV2Error("paired_index_identity_model_invalid")
    if index.get("receipt_reference_kind") != "EXPECTED_RECEIPT_CANDIDATE_SHA256_SHADOW_ONLY":
        raise HumanGateWriterFencingV2Error("paired_index_receipt_reference_kind_invalid")
    entries = tuple(index.get("entries") or ())
    if index.get("entry_count") != len(entries):
        raise HumanGateWriterFencingV2Error("paired_index_count_mismatch")
    normalized = tuple(_normalize_pair(entry, i) for i, entry in enumerate(entries))
    if len({row["commit_id"] for row in normalized}) != len(normalized):
        raise HumanGateWriterFencingV2Error("paired_index_commit_duplicate")
    if len({row["idempotency_key_sha256"] for row in normalized}) != len(normalized):
        raise HumanGateWriterFencingV2Error("paired_index_idempotency_duplicate")
    if len({row["receipt_reference_sha256"] for row in normalized}) != len(normalized):
        raise HumanGateWriterFencingV2Error("paired_index_receipt_reference_duplicate")
    _sha(index.get("legacy_index_sha256"), "paired_index.legacy_index_sha256")
    return digest


def _verify_lease(lease: Mapping[str, Any], expected_sha256: str, expected_root: str) -> str:
    if not isinstance(lease, Mapping) or lease.get("schema") != LEGACY_LEASE_SCHEMA:
        raise HumanGateWriterFencingV2Error("writer_lease_schema_mismatch")
    digest = _verify_hash(lease, "lease_sha256", "writer_lease_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_writer_lease_sha256"):
        raise HumanGateWriterFencingV2Error("writer_lease_external_digest_mismatch")
    if lease.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise HumanGateWriterFencingV2Error("writer_lease_authority_root_mismatch")
    _verify_safety(lease, "writer_lease")
    _verify_effects(lease, "writer_lease")
    if lease.get("live_lease_backend_proven") is not False or lease.get("lease_write_performed") is not False:
        raise HumanGateWriterFencingV2Error("writer_lease_live_or_write_overclaim")
    if lease.get("execution_authority") != "NONE":
        raise HumanGateWriterFencingV2Error("writer_lease_authority_breached")
    return digest


def build_writer_authority_root_anchor(
    writer_lease: Mapping[str, Any],
    legacy_receipt_index: Mapping[str, Any],
    paired_receipt_index: Mapping[str, Any],
    *,
    expected_writer_lease_sha256: str,
    expected_legacy_receipt_index_sha256: str,
    expected_paired_receipt_index_sha256: str,
    expected_authority_root_sha256: str,
    retained_at: str,
) -> dict[str, Any]:
    root = _sha(expected_authority_root_sha256, "expected_authority_root_sha256")
    lease_sha = _verify_lease(writer_lease, expected_writer_lease_sha256, root)
    legacy_sha = _verify_legacy_index(
        legacy_receipt_index, expected_legacy_receipt_index_sha256, root
    )
    paired_sha = _verify_paired_index(
        paired_receipt_index, expected_paired_receipt_index_sha256, root
    )
    if paired_receipt_index.get("legacy_index_sha256") != legacy_sha:
        raise HumanGateWriterFencingV2Error("authority_anchor_paired_legacy_index_mismatch")
    body = {
        "schema": AUTHORITY_ANCHOR_SCHEMA,
        "authority_root_sha256": root,
        "writer_lease_sha256": lease_sha,
        "legacy_receipt_index_sha256": legacy_sha,
        "paired_receipt_index_sha256": paired_sha,
        "anchor_scope": "WRITER_LEASE_AND_RECEIPT_INDEX_ONLY",
        "retained_reference_required": True,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "retained_at": _iso(retained_at, "retained_at"),
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["authority_anchor_sha256"] = sha256_obj(body)
    return body


def _verify_anchor(
    anchor: Mapping[str, Any],
    *,
    expected_anchor_sha256: str,
    expected_authority_root_sha256: str,
) -> str:
    if not isinstance(anchor, Mapping) or anchor.get("schema") != AUTHORITY_ANCHOR_SCHEMA:
        raise HumanGateWriterFencingV2Error("authority_anchor_schema_mismatch")
    digest = _verify_hash(anchor, "authority_anchor_sha256", "authority_anchor_hash_mismatch")
    if digest != _sha(expected_anchor_sha256, "expected_authority_anchor_sha256"):
        raise HumanGateWriterFencingV2Error("authority_anchor_external_digest_mismatch")
    if anchor.get("authority_root_sha256") != _sha(
        expected_authority_root_sha256, "expected_authority_root_sha256"
    ):
        raise HumanGateWriterFencingV2Error("authority_anchor_root_mismatch")
    _verify_safety(anchor, "authority_anchor")
    _verify_effects(anchor, "authority_anchor")
    if anchor.get("anchor_scope") != "WRITER_LEASE_AND_RECEIPT_INDEX_ONLY":
        raise HumanGateWriterFencingV2Error("authority_anchor_scope_invalid")
    if anchor.get("retained_reference_required") is not True:
        raise HumanGateWriterFencingV2Error("authority_anchor_retention_guard_missing")
    if anchor.get("current_truth_promotion_allowed") is not False or anchor.get("apply_allowed") is not False:
        raise HumanGateWriterFencingV2Error("authority_anchor_truth_or_apply_breached")
    if anchor.get("execution_authority") != "NONE":
        raise HumanGateWriterFencingV2Error("authority_anchor_authority_breached")
    return digest


def _verify_legacy_recovery(receipt: Mapping[str, Any], expected_sha256: str) -> str:
    if not isinstance(receipt, Mapping) or receipt.get("schema") != LEGACY_RECOVERY_SCHEMA:
        raise HumanGateWriterFencingV2Error("legacy_recovery_schema_mismatch")
    digest = _verify_hash(
        receipt, "recovery_verification_sha256", "legacy_recovery_hash_mismatch"
    )
    if digest != _sha(expected_sha256, "expected_legacy_recovery_sha256"):
        raise HumanGateWriterFencingV2Error("legacy_recovery_external_digest_mismatch")
    _verify_safety(receipt, "legacy_recovery")
    _verify_effects(receipt, "legacy_recovery")
    if receipt.get("protocol_status") != "FENCING_AND_CRASH_RECOVERY_VERIFIED_SHADOW_ONLY":
        raise HumanGateWriterFencingV2Error("legacy_recovery_status_invalid")
    if receipt.get("recovery_status") not in ALLOWED_RECOVERY:
        raise HumanGateWriterFencingV2Error("legacy_recovery_outcome_invalid")
    if receipt.get("split_brain_same_token_rejected") is not True or receipt.get("blind_retry_allowed") is not False:
        raise HumanGateWriterFencingV2Error("legacy_recovery_guard_missing")
    if receipt.get("live_writer_backend_proven") is not False or receipt.get("durable_commit_proven") is not False:
        raise HumanGateWriterFencingV2Error("legacy_recovery_durability_overclaim")
    if receipt.get("human_gate_write_performed") is not False or receipt.get("current_truth_promotion_allowed") is not False:
        raise HumanGateWriterFencingV2Error("legacy_recovery_write_or_truth_breached")
    if receipt.get("apply_allowed") is not False or receipt.get("execution_authority") != "NONE" or receipt.get("can_execute") is not False:
        raise HumanGateWriterFencingV2Error("legacy_recovery_apply_or_authority_breached")
    return digest


def build_crash_recovery_verification_v2(
    legacy_recovery: Mapping[str, Any],
    paired_receipt_index: Mapping[str, Any],
    authority_anchor: Mapping[str, Any],
    *,
    expected_legacy_recovery_sha256: str,
    expected_paired_receipt_index_sha256: str,
    expected_authority_anchor_sha256: str,
    expected_authority_root_sha256: str,
) -> dict[str, Any]:
    legacy_sha = _verify_legacy_recovery(legacy_recovery, expected_legacy_recovery_sha256)
    paired_sha = _verify_paired_index(
        paired_receipt_index,
        expected_paired_receipt_index_sha256,
        expected_authority_root_sha256,
    )
    anchor_sha = _verify_anchor(
        authority_anchor,
        expected_anchor_sha256=expected_authority_anchor_sha256,
        expected_authority_root_sha256=expected_authority_root_sha256,
    )
    if authority_anchor.get("writer_lease_sha256") != legacy_recovery.get("current_writer_lease_sha256"):
        raise HumanGateWriterFencingV2Error("recovery_v2_anchor_writer_lease_mismatch")
    if authority_anchor.get("legacy_receipt_index_sha256") != legacy_recovery.get("current_receipt_index_sha256"):
        raise HumanGateWriterFencingV2Error("recovery_v2_anchor_legacy_index_mismatch")
    if authority_anchor.get("paired_receipt_index_sha256") != paired_sha:
        raise HumanGateWriterFencingV2Error("recovery_v2_anchor_paired_index_mismatch")
    if paired_receipt_index.get("legacy_index_sha256") != legacy_recovery.get("current_receipt_index_sha256"):
        raise HumanGateWriterFencingV2Error("recovery_v2_paired_index_legacy_binding_mismatch")

    target_commit = _sha(legacy_recovery.get("commit_id"), "legacy_recovery.commit_id")
    target_key = _sha(
        legacy_recovery.get("idempotency_key_sha256"),
        "legacy_recovery.idempotency_key_sha256",
    )
    target_receipt = _sha(
        legacy_recovery.get("receipt_candidate_sha256"),
        "legacy_recovery.receipt_candidate_sha256",
    )
    entries = tuple(paired_receipt_index.get("entries") or ())
    matches = [
        entry
        for entry in entries
        if isinstance(entry, Mapping)
        and (entry.get("commit_id") == target_commit or entry.get("idempotency_key_sha256") == target_key)
    ]
    if legacy_recovery.get("receipt_indexed") is True:
        if len(matches) != 1:
            raise HumanGateWriterFencingV2Error("recovery_v2_indexed_pair_missing_or_ambiguous")
        row = matches[0]
        if row.get("commit_id") != target_commit or row.get("idempotency_key_sha256") != target_key:
            raise HumanGateWriterFencingV2Error("recovery_v2_indexed_pair_crossed")
        if row.get("receipt_reference_sha256") != target_receipt:
            raise HumanGateWriterFencingV2Error("recovery_v2_receipt_reference_mismatch")
    else:
        if matches:
            raise HumanGateWriterFencingV2Error("recovery_v2_unindexed_identity_present")

    body = {
        "schema": RECOVERY_V2_SCHEMA,
        "legacy_recovery_verification_sha256": legacy_sha,
        "paired_receipt_index_sha256": paired_sha,
        "authority_anchor_sha256": anchor_sha,
        "authority_root_sha256": _sha(
            expected_authority_root_sha256, "expected_authority_root_sha256"
        ),
        "current_writer_lease_sha256": legacy_recovery["current_writer_lease_sha256"],
        "legacy_current_receipt_index_sha256": legacy_recovery["current_receipt_index_sha256"],
        "case_id": legacy_recovery["case_id"],
        "case_sha256": legacy_recovery["case_sha256"],
        "challenge_id": legacy_recovery["challenge_id"],
        "approval_verification_sha256": legacy_recovery["approval_verification_sha256"],
        "atomic_consume_verification_sha256": legacy_recovery["atomic_consume_verification_sha256"],
        "receipt_candidate_sha256": target_receipt,
        "commit_id": target_commit,
        "idempotency_key_sha256": target_key,
        "receipt_indexed": legacy_recovery["receipt_indexed"],
        "recovery_status": legacy_recovery["recovery_status"],
        "recovery_action": legacy_recovery["recovery_action"],
        "paired_receipt_identity_verified": True,
        "authority_root_anchor_consumed": True,
        "cross_plane_anchor_scope": "CONTROL_CENTER_WRITER_LEASE_RECEIPT_INDEX",
        "protocol_status": "FENCING_AND_CRASH_RECOVERY_HARDENED_SHADOW_ONLY",
        "live_writer_backend_proven": False,
        "durable_commit_proven": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["recovery_verification_sha256"] = sha256_obj(body)
    return body
