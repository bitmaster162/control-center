from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

RECOVERY_V2_SCHEMA = "control_center.shadow_human_gate_crash_recovery_verification.v2"
LEASE_SCHEMA = "control_center.shadow_human_gate_writer_lease_snapshot.v1"
LEASE_LINEAGE_SCHEMA = "control_center.shadow_human_gate_lease_epoch_lineage.v1"
DUAL_COMMIT_SCHEMA = "control_center.shadow_human_gate_dual_state_commit_candidate.v1"
READBACK_SCHEMA = "control_center.shadow_human_gate_dual_state_readback_snapshot.v1"
ATOMICITY_SCHEMA = "control_center.shadow_human_gate_dual_state_atomicity_verification.v1"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

NO_EFFECTS = {
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

class DualStateAtomicityError(ValueError):
    pass

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DualStateAtomicityError(f"{field}_required")
    return value.strip()

def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise DualStateAtomicityError(f"{field}_must_be_sha256")
    return text

def _int(value: Any, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DualStateAtomicityError(f"{field}_invalid")
    return value

def _iso(value: Any, field: str) -> tuple[str, float]:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise DualStateAtomicityError(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise DualStateAtomicityError(f"{field}_timezone_required")
    return text, parsed.timestamp()

def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise DualStateAtomicityError(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise DualStateAtomicityError(code)
    return supplied

def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise DualStateAtomicityError(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise DualStateAtomicityError(f"unsafe_{field}:{key}")

def _verify_effects(record: Mapping[str, Any], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(NO_EFFECTS):
        raise DualStateAtomicityError(f"{field}_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in NO_EFFECTS):
        raise DualStateAtomicityError(f"{field}_effect_boundary_breached")

def _verify_lease(lease: Mapping[str, Any], expected_sha256: str, expected_root: str, field: str) -> str:
    if not isinstance(lease, Mapping) or lease.get("schema") != LEASE_SCHEMA:
        raise DualStateAtomicityError(f"{field}_schema_mismatch")
    digest = _verify_hash(lease, "lease_sha256", f"{field}_hash_mismatch")
    if digest != _sha(expected_sha256, f"expected_{field}_sha256"):
        raise DualStateAtomicityError(f"{field}_external_digest_mismatch")
    if lease.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise DualStateAtomicityError(f"{field}_authority_root_mismatch")
    _verify_safety(lease, field)
    _verify_effects(lease, field)
    if lease.get("live_lease_backend_proven") is not False or lease.get("lease_write_performed") is not False:
        raise DualStateAtomicityError(f"{field}_live_or_write_overclaim")
    if lease.get("execution_authority") != "NONE":
        raise DualStateAtomicityError(f"{field}_authority_breached")
    _int(lease.get("lease_epoch"), f"{field}.lease_epoch", 1)
    _int(lease.get("fencing_token"), f"{field}.fencing_token", 1)
    _int(lease.get("bound_generation"), f"{field}.bound_generation", 0)
    return digest

def _verify_recovery_v2(receipt: Mapping[str, Any], expected_sha256: str, expected_root: str) -> str:
    if not isinstance(receipt, Mapping) or receipt.get("schema") != RECOVERY_V2_SCHEMA:
        raise DualStateAtomicityError("recovery_v2_schema_mismatch")
    digest = _verify_hash(receipt, "recovery_verification_sha256", "recovery_v2_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_recovery_v2_sha256"):
        raise DualStateAtomicityError("recovery_v2_external_digest_mismatch")
    if receipt.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise DualStateAtomicityError("recovery_v2_authority_root_mismatch")
    _verify_safety(receipt, "recovery_v2")
    _verify_effects(receipt, "recovery_v2")
    if receipt.get("paired_receipt_identity_verified") is not True:
        raise DualStateAtomicityError("recovery_v2_paired_identity_missing")
    if receipt.get("authority_root_anchor_consumed") is not True:
        raise DualStateAtomicityError("recovery_v2_anchor_missing")
    if receipt.get("protocol_status") != "FENCING_AND_CRASH_RECOVERY_HARDENED_SHADOW_ONLY":
        raise DualStateAtomicityError("recovery_v2_status_invalid")
    if receipt.get("recovery_status") not in ALLOWED_RECOVERY:
        raise DualStateAtomicityError("recovery_v2_outcome_invalid")
    if receipt.get("live_writer_backend_proven") is not False or receipt.get("durable_commit_proven") is not False:
        raise DualStateAtomicityError("recovery_v2_durability_overclaim")
    if receipt.get("human_gate_write_performed") is not False or receipt.get("current_truth_promotion_allowed") is not False:
        raise DualStateAtomicityError("recovery_v2_write_or_truth_breached")
    if receipt.get("apply_allowed") is not False or receipt.get("execution_authority") != "NONE" or receipt.get("can_execute") is not False:
        raise DualStateAtomicityError("recovery_v2_apply_or_authority_breached")
    return digest

def build_lease_epoch_lineage(previous_lease: Mapping[str, Any], current_lease: Mapping[str, Any], *, expected_previous_lease_sha256: str, expected_current_lease_sha256: str, expected_authority_root_sha256: str, transition_kind: str) -> dict[str, Any]:
    root = _sha(expected_authority_root_sha256, "expected_authority_root_sha256")
    previous_sha = _verify_lease(previous_lease, expected_previous_lease_sha256, root, "previous_lease")
    current_sha = _verify_lease(current_lease, expected_current_lease_sha256, root, "current_lease")
    transition = _text(transition_kind, "transition_kind").upper()
    if transition not in {"RENEW", "REACQUIRE"}:
        raise DualStateAtomicityError("lease_transition_kind_invalid")
    if current_lease.get("previous_lease_sha256") != previous_sha:
        raise DualStateAtomicityError("lease_lineage_parent_mismatch")
    if current_lease.get("lease_epoch") != previous_lease.get("lease_epoch") + 1:
        raise DualStateAtomicityError("lease_epoch_not_monotonic_plus_one")
    if current_lease.get("fencing_token") <= previous_lease.get("fencing_token"):
        raise DualStateAtomicityError("fencing_token_not_strictly_monotonic")
    if current_lease.get("lease_id") == previous_lease.get("lease_id"):
        raise DualStateAtomicityError("lease_aba_same_lease_id_forbidden")
    if transition == "RENEW" and current_lease.get("writer_id") != previous_lease.get("writer_id"):
        raise DualStateAtomicityError("lease_renew_writer_changed")
    _, previous_issued = _iso(previous_lease.get("issued_at"), "previous_lease.issued_at")
    _, current_issued = _iso(current_lease.get("issued_at"), "current_lease.issued_at")
    if current_issued <= previous_issued:
        raise DualStateAtomicityError("lease_issue_time_not_monotonic")
    body = {
        "schema": LEASE_LINEAGE_SCHEMA,
        "authority_root_sha256": root,
        "previous_lease_sha256": previous_sha,
        "current_lease_sha256": current_sha,
        "previous_lease_id": _sha(previous_lease.get("lease_id"), "previous_lease.lease_id"),
        "current_lease_id": _sha(current_lease.get("lease_id"), "current_lease.lease_id"),
        "previous_writer_id": _text(previous_lease.get("writer_id"), "previous_lease.writer_id"),
        "current_writer_id": _text(current_lease.get("writer_id"), "current_lease.writer_id"),
        "previous_lease_epoch": previous_lease["lease_epoch"],
        "current_lease_epoch": current_lease["lease_epoch"],
        "previous_fencing_token": previous_lease["fencing_token"],
        "current_fencing_token": current_lease["fencing_token"],
        "transition_kind": transition,
        "epoch_transition": "EXACT_PLUS_ONE",
        "fencing_transition": "STRICTLY_INCREASING",
        "aba_guard": "LEASE_ID_CHANGES_AND_EPOCH_TOKEN_MONOTONIC",
        "lineage_verified": True,
        "lease_write_performed": False,
        "live_lease_backend_proven": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["lease_lineage_sha256"] = sha256_obj(body)
    return body

def _verify_lineage(lineage: Mapping[str, Any], expected_sha256: str, expected_root: str) -> str:
    if not isinstance(lineage, Mapping) or lineage.get("schema") != LEASE_LINEAGE_SCHEMA:
        raise DualStateAtomicityError("lease_lineage_schema_mismatch")
    digest = _verify_hash(lineage, "lease_lineage_sha256", "lease_lineage_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_lease_lineage_sha256"):
        raise DualStateAtomicityError("lease_lineage_external_digest_mismatch")
    if lineage.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise DualStateAtomicityError("lease_lineage_root_mismatch")
    _verify_safety(lineage, "lease_lineage")
    _verify_effects(lineage, "lease_lineage")
    if lineage.get("lineage_verified") is not True:
        raise DualStateAtomicityError("lease_lineage_not_verified")
    if lineage.get("epoch_transition") != "EXACT_PLUS_ONE" or lineage.get("fencing_transition") != "STRICTLY_INCREASING":
        raise DualStateAtomicityError("lease_lineage_monotonic_guard_missing")
    if lineage.get("aba_guard") != "LEASE_ID_CHANGES_AND_EPOCH_TOKEN_MONOTONIC":
        raise DualStateAtomicityError("lease_lineage_aba_guard_missing")
    if lineage.get("current_lease_epoch") != lineage.get("previous_lease_epoch") + 1:
        raise DualStateAtomicityError("lease_lineage_epoch_invalid")
    if lineage.get("current_fencing_token") <= lineage.get("previous_fencing_token"):
        raise DualStateAtomicityError("lease_lineage_fencing_invalid")
    if lineage.get("current_lease_id") == lineage.get("previous_lease_id"):
        raise DualStateAtomicityError("lease_lineage_aba_detected")
    if lineage.get("lease_write_performed") is not False or lineage.get("live_lease_backend_proven") is not False:
        raise DualStateAtomicityError("lease_lineage_live_or_write_overclaim")
    return digest

def build_dual_state_commit_candidate(recovery_v2: Mapping[str, Any], lease_lineage: Mapping[str, Any], *, expected_recovery_v2_sha256: str, expected_lease_lineage_sha256: str, expected_authority_root_sha256: str, prior_human_gate_state_sha256: str, next_human_gate_state_sha256: str, prior_paired_receipt_index_sha256: str, next_paired_receipt_index_sha256: str, prior_human_gate_generation: int, next_human_gate_generation: int, prior_receipt_index_generation: int, next_receipt_index_generation: int, backend_transaction_id_sha256: str) -> dict[str, Any]:
    root = _sha(expected_authority_root_sha256, "expected_authority_root_sha256")
    recovery_sha = _verify_recovery_v2(recovery_v2, expected_recovery_v2_sha256, root)
    lineage_sha = _verify_lineage(lease_lineage, expected_lease_lineage_sha256, root)
    if recovery_v2.get("current_writer_lease_sha256") != lease_lineage.get("current_lease_sha256"):
        raise DualStateAtomicityError("dual_commit_current_lease_binding_mismatch")
    prior_index = _sha(prior_paired_receipt_index_sha256, "prior_paired_receipt_index_sha256")
    if prior_index != recovery_v2.get("paired_receipt_index_sha256"):
        raise DualStateAtomicityError("dual_commit_prior_paired_index_mismatch")
    prior_hg = _sha(prior_human_gate_state_sha256, "prior_human_gate_state_sha256")
    next_hg = _sha(next_human_gate_state_sha256, "next_human_gate_state_sha256")
    next_index = _sha(next_paired_receipt_index_sha256, "next_paired_receipt_index_sha256")
    phg = _int(prior_human_gate_generation, "prior_human_gate_generation", 0)
    nhg = _int(next_human_gate_generation, "next_human_gate_generation", 1)
    pri = _int(prior_receipt_index_generation, "prior_receipt_index_generation", 0)
    nri = _int(next_receipt_index_generation, "next_receipt_index_generation", 1)
    if nhg != phg + 1:
        raise DualStateAtomicityError("dual_commit_human_gate_generation_must_increment_one")
    if nri != pri + 1:
        raise DualStateAtomicityError("dual_commit_receipt_index_generation_must_increment_one")
    write_set = {"human_gate_state_sha256": next_hg, "paired_receipt_index_sha256": next_index, "human_gate_generation": nhg, "receipt_index_generation": nri}
    precondition = {"authority_root_sha256": root, "human_gate_state_sha256": prior_hg, "paired_receipt_index_sha256": prior_index, "human_gate_generation": phg, "receipt_index_generation": pri, "lease_lineage_sha256": lineage_sha}
    body = {
        "schema": DUAL_COMMIT_SCHEMA,
        "recovery_verification_v2_sha256": recovery_sha,
        "lease_lineage_sha256": lineage_sha,
        "authority_root_sha256": root,
        "case_id": _text(recovery_v2.get("case_id"), "recovery_v2.case_id"),
        "case_sha256": _sha(recovery_v2.get("case_sha256"), "recovery_v2.case_sha256"),
        "challenge_id": _sha(recovery_v2.get("challenge_id"), "recovery_v2.challenge_id"),
        "current_writer_lease_sha256": recovery_v2["current_writer_lease_sha256"],
        "commit_id": _sha(recovery_v2.get("commit_id"), "recovery_v2.commit_id"),
        "idempotency_key_sha256": _sha(recovery_v2.get("idempotency_key_sha256"), "recovery_v2.idempotency_key_sha256"),
        "receipt_reference_sha256": _sha(recovery_v2.get("receipt_candidate_sha256"), "recovery_v2.receipt_candidate_sha256"),
        "prior_human_gate_state_sha256": prior_hg,
        "next_human_gate_state_sha256": next_hg,
        "prior_paired_receipt_index_sha256": prior_index,
        "next_paired_receipt_index_sha256": next_index,
        "prior_human_gate_generation": phg,
        "next_human_gate_generation": nhg,
        "prior_receipt_index_generation": pri,
        "next_receipt_index_generation": nri,
        "transaction_precondition_sha256": sha256_obj(precondition),
        "dual_write_set_sha256": sha256_obj(write_set),
        "backend_transaction_id_sha256": _sha(backend_transaction_id_sha256, "backend_transaction_id_sha256"),
        "atomic_write_model": "ONE_BACKEND_TRANSACTION_TWO_LOGICAL_RECORDS",
        "partial_commit_forbidden": True,
        "write_performed": False,
        "durable_commit_proven": False,
        "live_backend_observed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["dual_commit_candidate_sha256"] = sha256_obj(body)
    return body

def _verify_dual_commit(candidate: Mapping[str, Any], expected_sha256: str, expected_root: str) -> str:
    if not isinstance(candidate, Mapping) or candidate.get("schema") != DUAL_COMMIT_SCHEMA:
        raise DualStateAtomicityError("dual_commit_schema_mismatch")
    digest = _verify_hash(candidate, "dual_commit_candidate_sha256", "dual_commit_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_dual_commit_candidate_sha256"):
        raise DualStateAtomicityError("dual_commit_external_digest_mismatch")
    if candidate.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise DualStateAtomicityError("dual_commit_root_mismatch")
    _verify_safety(candidate, "dual_commit")
    _verify_effects(candidate, "dual_commit")
    if candidate.get("atomic_write_model") != "ONE_BACKEND_TRANSACTION_TWO_LOGICAL_RECORDS":
        raise DualStateAtomicityError("dual_commit_atomic_write_model_invalid")
    if candidate.get("partial_commit_forbidden") is not True:
        raise DualStateAtomicityError("dual_commit_partial_commit_guard_missing")
    if candidate.get("write_performed") is not False or candidate.get("durable_commit_proven") is not False or candidate.get("live_backend_observed") is not False:
        raise DualStateAtomicityError("dual_commit_durability_overclaim")
    if candidate.get("next_human_gate_generation") != candidate.get("prior_human_gate_generation") + 1:
        raise DualStateAtomicityError("dual_commit_human_gate_generation_invalid")
    if candidate.get("next_receipt_index_generation") != candidate.get("prior_receipt_index_generation") + 1:
        raise DualStateAtomicityError("dual_commit_receipt_generation_invalid")
    return digest

def build_dual_state_readback_snapshot(*, authority_root_sha256: str, human_gate_state_sha256: str, paired_receipt_index_sha256: str, human_gate_generation: int, receipt_index_generation: int, observed_at: str) -> dict[str, Any]:
    body = {
        "schema": READBACK_SCHEMA,
        "authority_root_sha256": _sha(authority_root_sha256, "authority_root_sha256"),
        "human_gate_state_sha256": _sha(human_gate_state_sha256, "human_gate_state_sha256"),
        "paired_receipt_index_sha256": _sha(paired_receipt_index_sha256, "paired_receipt_index_sha256"),
        "human_gate_generation": _int(human_gate_generation, "human_gate_generation", 0),
        "receipt_index_generation": _int(receipt_index_generation, "receipt_index_generation", 0),
        "observed_at": _iso(observed_at, "observed_at")[0],
        "live_backend_observed": False,
        "read_only": True,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["readback_sha256"] = sha256_obj(body)
    return body

def _verify_readback(readback: Mapping[str, Any], expected_sha256: str, expected_root: str) -> str:
    if not isinstance(readback, Mapping) or readback.get("schema") != READBACK_SCHEMA:
        raise DualStateAtomicityError("readback_schema_mismatch")
    digest = _verify_hash(readback, "readback_sha256", "readback_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_readback_sha256"):
        raise DualStateAtomicityError("readback_external_digest_mismatch")
    if readback.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise DualStateAtomicityError("readback_root_mismatch")
    _verify_safety(readback, "readback")
    _verify_effects(readback, "readback")
    if readback.get("live_backend_observed") is not False or readback.get("read_only") is not True:
        raise DualStateAtomicityError("readback_live_or_mutation_overclaim")
    return digest

def build_dual_state_atomicity_verification(dual_commit_candidate: Mapping[str, Any], readback: Mapping[str, Any], *, expected_dual_commit_candidate_sha256: str, expected_readback_sha256: str, expected_authority_root_sha256: str, crash_point: str) -> dict[str, Any]:
    root = _sha(expected_authority_root_sha256, "expected_authority_root_sha256")
    candidate_sha = _verify_dual_commit(dual_commit_candidate, expected_dual_commit_candidate_sha256, root)
    readback_sha = _verify_readback(readback, expected_readback_sha256, root)
    crash = _text(crash_point, "crash_point").upper()
    if crash not in {"BEFORE_ATOMIC_DUAL_WRITE", "AFTER_ATOMIC_DUAL_WRITE_BEFORE_ACK"}:
        raise DualStateAtomicityError("dual_state_crash_point_invalid")
    prior_pair = (dual_commit_candidate["prior_human_gate_state_sha256"], dual_commit_candidate["prior_paired_receipt_index_sha256"], dual_commit_candidate["prior_human_gate_generation"], dual_commit_candidate["prior_receipt_index_generation"])
    next_pair = (dual_commit_candidate["next_human_gate_state_sha256"], dual_commit_candidate["next_paired_receipt_index_sha256"], dual_commit_candidate["next_human_gate_generation"], dual_commit_candidate["next_receipt_index_generation"])
    observed_pair = (readback["human_gate_state_sha256"], readback["paired_receipt_index_sha256"], readback["human_gate_generation"], readback["receipt_index_generation"])
    if observed_pair not in {prior_pair, next_pair}:
        raise DualStateAtomicityError("dual_state_split_or_unknown_readback_detected")
    if crash == "BEFORE_ATOMIC_DUAL_WRITE" and observed_pair != prior_pair:
        raise DualStateAtomicityError("before_atomic_write_readback_conflict")
    if crash == "AFTER_ATOMIC_DUAL_WRITE_BEFORE_ACK" and observed_pair != next_pair:
        raise DualStateAtomicityError("after_atomic_write_readback_conflict")
    if observed_pair == prior_pair:
        state = "PRE_COMMIT_PAIR_OBSERVED"
        recovery_action = "FRESH_COMPARE_REQUIRED_BEFORE_NEW_CANDIDATE"
    else:
        state = "POST_COMMIT_PAIR_OBSERVED_SHADOW_ONLY"
        recovery_action = "DEDUP_RECONCILE_NO_SECOND_WRITE"
    body = {
        "schema": ATOMICITY_SCHEMA,
        "dual_commit_candidate_sha256": candidate_sha,
        "readback_sha256": readback_sha,
        "authority_root_sha256": root,
        "recovery_verification_v2_sha256": dual_commit_candidate["recovery_verification_v2_sha256"],
        "lease_lineage_sha256": dual_commit_candidate["lease_lineage_sha256"],
        "case_id": dual_commit_candidate["case_id"],
        "case_sha256": dual_commit_candidate["case_sha256"],
        "challenge_id": dual_commit_candidate["challenge_id"],
        "current_writer_lease_sha256": dual_commit_candidate["current_writer_lease_sha256"],
        "commit_id": dual_commit_candidate["commit_id"],
        "idempotency_key_sha256": dual_commit_candidate["idempotency_key_sha256"],
        "prior_human_gate_state_sha256": dual_commit_candidate["prior_human_gate_state_sha256"],
        "next_human_gate_state_sha256": dual_commit_candidate["next_human_gate_state_sha256"],
        "prior_paired_receipt_index_sha256": dual_commit_candidate["prior_paired_receipt_index_sha256"],
        "next_paired_receipt_index_sha256": dual_commit_candidate["next_paired_receipt_index_sha256"],
        "crash_point": crash,
        "observed_pair_state": state,
        "recovery_action": recovery_action,
        "dual_state_atomicity_model": "ONE_TRANSACTION_TWO_LOGICAL_RECORDS",
        "split_state_rejected": True,
        "lease_epoch_lineage_verified": True,
        "aba_guard_verified": True,
        "durability_status": "PROTOCOL_VERIFIED_NO_DURABLE_BACKEND",
        "protocol_status": "DUAL_STATE_ATOMICITY_VERIFIED_SHADOW_ONLY",
        "write_performed": False,
        "durable_commit_proven": False,
        "live_backend_observed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["atomicity_verification_sha256"] = sha256_obj(body)
    return body
