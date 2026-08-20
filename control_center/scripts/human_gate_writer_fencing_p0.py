from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

ATOMIC_CONSUME_SCHEMA = "control_center.shadow_human_gate_atomic_consume_verification.v1"
LEASE_SCHEMA = "control_center.shadow_human_gate_writer_lease_snapshot.v1"
RECEIPT_INDEX_SCHEMA = "control_center.shadow_human_gate_commit_receipt_index_snapshot.v1"
ATTEMPT_SCHEMA = "control_center.shadow_human_gate_fenced_commit_attempt.v1"
RECEIPT_CANDIDATE_SCHEMA = "control_center.shadow_human_gate_durable_commit_receipt_candidate.v1"
RECOVERY_SCHEMA = "control_center.shadow_human_gate_crash_recovery_verification.v1"

REQUIRED_SAFETY = {
    "mode": "SHADOW",
    "execution_authority": "NONE",
    "can_trade": False,
    "capital_permission": "DENY",
    "orders_allowed": False,
    "signals_allowed": False,
}

R7_EFFECTS = {
    "human_gate_write": False,
    "credential_registry_write": False,
    "nonce_registry_write": False,
    "current_truth_apply": False,
    "decision_ledger_write": False,
    "command_queue_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
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

CRASH_POINTS = {
    "BEFORE_WRITE",
    "AFTER_WRITE_BEFORE_RECEIPT",
    "AFTER_RECEIPT_BEFORE_ACK",
}


class HumanGateWriterFencingError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanGateWriterFencingError(f"{field}_required")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HumanGateWriterFencingError(f"{field}_must_be_sha256")
    return text


def _iso(value: Any, field: str) -> tuple[str, float]:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise HumanGateWriterFencingError(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise HumanGateWriterFencingError(f"{field}_timezone_required")
    return text, parsed.timestamp()


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HumanGateWriterFencingError(f"{field}_must_be_positive_int")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HumanGateWriterFencingError(f"{field}_must_be_nonnegative_int")
    return value


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise HumanGateWriterFencingError(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise HumanGateWriterFencingError(code)
    return supplied


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise HumanGateWriterFencingError(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise HumanGateWriterFencingError(f"unsafe_{field}:{key}")


def _verify_false_effects(record: Mapping[str, Any], expected: Mapping[str, bool], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(expected):
        raise HumanGateWriterFencingError(f"{field}_effect_keys_mismatch")
    if any(effects.get(key) is not False for key in expected):
        raise HumanGateWriterFencingError(f"{field}_effect_boundary_breached")


def _unique_shas(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise HumanGateWriterFencingError(f"{field}_must_be_sequence")
    rows = tuple(_sha(value, field) for value in values)
    if len(rows) != len(set(rows)):
        raise HumanGateWriterFencingError(f"{field}_duplicates_forbidden")
    return rows


def _verify_atomic(receipt: Mapping[str, Any], expected_sha256: str) -> str:
    if not isinstance(receipt, Mapping) or receipt.get("schema") != ATOMIC_CONSUME_SCHEMA:
        raise HumanGateWriterFencingError("atomic_consume_schema_mismatch")
    digest = _verify_hash(receipt, "atomic_consume_verification_sha256", "atomic_consume_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_atomic_consume_sha256"):
        raise HumanGateWriterFencingError("atomic_consume_external_digest_mismatch")
    _verify_safety(receipt, "atomic_consume")
    _verify_false_effects(receipt, R7_EFFECTS, "atomic_consume")
    if receipt.get("toctou_guard_model") != "COMPARE_AND_SWAP_PRECONDITION":
        raise HumanGateWriterFencingError("atomic_consume_cas_guard_missing")
    if receipt.get("atomicity_status") != "PROTOCOL_VERIFIED_NO_DURABLE_COMMIT":
        raise HumanGateWriterFencingError("atomic_consume_status_invalid")
    if receipt.get("single_use_status") != "CANDIDATE_ONLY_NOT_DURABLY_ENFORCED":
        raise HumanGateWriterFencingError("atomic_consume_single_use_status_invalid")
    if receipt.get("commit_performed") is not False or receipt.get("human_gate_write_performed") is not False:
        raise HumanGateWriterFencingError("atomic_consume_write_overclaim")
    if receipt.get("execution_authority") != "NONE" or receipt.get("can_execute") is not False:
        raise HumanGateWriterFencingError("atomic_consume_authority_breached")
    generation_from = _nonnegative_int(receipt.get("cas_generation_from"), "atomic.cas_generation_from")
    generation_to = _positive_int(receipt.get("cas_generation_to"), "atomic.cas_generation_to")
    if generation_to != generation_from + 1:
        raise HumanGateWriterFencingError("atomic_consume_generation_transition_invalid")
    _sha(receipt.get("prior_state_sha256"), "atomic.prior_state_sha256")
    _sha(receipt.get("next_state_candidate_sha256"), "atomic.next_state_candidate_sha256")
    return digest


def build_writer_lease_snapshot(
    *,
    lease_id: str,
    authority_root_sha256: str,
    writer_id: str,
    lease_epoch: int,
    fencing_token: int,
    bound_state_sha256: str,
    bound_generation: int,
    issued_at: str,
    expires_at: str,
    previous_lease_sha256: str,
) -> dict[str, Any]:
    issued_text, issued_epoch = _iso(issued_at, "issued_at")
    expires_text, expires_epoch = _iso(expires_at, "expires_at")
    if expires_epoch <= issued_epoch:
        raise HumanGateWriterFencingError("lease_window_invalid")
    body = {
        "schema": LEASE_SCHEMA,
        "lease_id": _sha(lease_id, "lease_id"),
        "authority_root_sha256": _sha(authority_root_sha256, "authority_root_sha256"),
        "writer_id": _text(writer_id, "writer_id"),
        "lease_epoch": _positive_int(lease_epoch, "lease_epoch"),
        "fencing_token": _positive_int(fencing_token, "fencing_token"),
        "bound_state_sha256": _sha(bound_state_sha256, "bound_state_sha256"),
        "bound_generation": _nonnegative_int(bound_generation, "bound_generation"),
        "issued_at": issued_text,
        "expires_at": expires_text,
        "previous_lease_sha256": _sha(previous_lease_sha256, "previous_lease_sha256"),
        "lease_status": "ACTIVE_SHADOW_LEASE_SNAPSHOT",
        "single_active_writer_claim": True,
        "live_lease_backend_proven": False,
        "lease_write_performed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["lease_sha256"] = sha256_obj(body)
    return body


def _verify_lease(lease: Mapping[str, Any], expected_sha256: str, field: str) -> str:
    if not isinstance(lease, Mapping) or lease.get("schema") != LEASE_SCHEMA:
        raise HumanGateWriterFencingError(f"{field}_schema_mismatch")
    digest = _verify_hash(lease, "lease_sha256", f"{field}_hash_mismatch")
    if digest != _sha(expected_sha256, f"expected_{field}_sha256"):
        raise HumanGateWriterFencingError(f"{field}_external_digest_mismatch")
    _verify_safety(lease, field)
    _verify_false_effects(lease, R8_EFFECTS, field)
    if lease.get("lease_status") != "ACTIVE_SHADOW_LEASE_SNAPSHOT" or lease.get("single_active_writer_claim") is not True:
        raise HumanGateWriterFencingError(f"{field}_status_invalid")
    if lease.get("live_lease_backend_proven") is not False or lease.get("lease_write_performed") is not False:
        raise HumanGateWriterFencingError(f"{field}_live_or_write_overclaim")
    if lease.get("execution_authority") != "NONE":
        raise HumanGateWriterFencingError(f"{field}_authority_breached")
    _positive_int(lease.get("lease_epoch"), f"{field}.lease_epoch")
    _positive_int(lease.get("fencing_token"), f"{field}.fencing_token")
    _nonnegative_int(lease.get("bound_generation"), f"{field}.bound_generation")
    _, start = _iso(lease.get("issued_at"), f"{field}.issued_at")
    _, end = _iso(lease.get("expires_at"), f"{field}.expires_at")
    if end <= start:
        raise HumanGateWriterFencingError(f"{field}_window_invalid")
    return digest


def build_commit_receipt_index_snapshot(
    *,
    index_id: str,
    authority_root_sha256: str,
    generation: int,
    commit_ids: Sequence[str] = (),
    idempotency_key_sha256s: Sequence[str] = (),
    previous_index_sha256: str,
) -> dict[str, Any]:
    commits = _unique_shas(commit_ids, "commit_id")
    keys = _unique_shas(idempotency_key_sha256s, "idempotency_key_sha256")
    if len(commits) != len(keys):
        raise HumanGateWriterFencingError("receipt_index_commit_and_idempotency_count_mismatch")
    body = {
        "schema": RECEIPT_INDEX_SCHEMA,
        "index_id": _text(index_id, "index_id"),
        "authority_root_sha256": _sha(authority_root_sha256, "authority_root_sha256"),
        "generation": _nonnegative_int(generation, "generation"),
        "commit_ids": commits,
        "idempotency_key_sha256s": keys,
        "entry_count": len(commits),
        "previous_index_sha256": _sha(previous_index_sha256, "previous_index_sha256"),
        "write_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["index_sha256"] = sha256_obj(body)
    return body


def _verify_index(index: Mapping[str, Any], expected_sha256: str, field: str) -> str:
    if not isinstance(index, Mapping) or index.get("schema") != RECEIPT_INDEX_SCHEMA:
        raise HumanGateWriterFencingError(f"{field}_schema_mismatch")
    digest = _verify_hash(index, "index_sha256", f"{field}_hash_mismatch")
    if digest != _sha(expected_sha256, f"expected_{field}_sha256"):
        raise HumanGateWriterFencingError(f"{field}_external_digest_mismatch")
    _verify_safety(index, field)
    _verify_false_effects(index, R8_EFFECTS, field)
    if index.get("write_allowed") is not False or index.get("apply_allowed") is not False or index.get("execution_authority") != "NONE":
        raise HumanGateWriterFencingError(f"{field}_write_or_authority_breached")
    commits = _unique_shas(tuple(index.get("commit_ids") or ()), f"{field}.commit_id")
    keys = _unique_shas(tuple(index.get("idempotency_key_sha256s") or ()), f"{field}.idempotency_key_sha256")
    if len(commits) != len(keys) or index.get("entry_count") != len(commits):
        raise HumanGateWriterFencingError(f"{field}_count_mismatch")
    _nonnegative_int(index.get("generation"), f"{field}.generation")
    return digest


def build_fenced_commit_attempt(
    atomic_consume_verification: Mapping[str, Any],
    writer_lease: Mapping[str, Any],
    receipt_index: Mapping[str, Any],
    *,
    expected_atomic_consume_sha256: str,
    expected_writer_lease_sha256: str,
    expected_receipt_index_sha256: str,
    commit_id: str,
    idempotency_key_sha256: str,
    attempted_at: str,
) -> dict[str, Any]:
    atomic_sha = _verify_atomic(atomic_consume_verification, expected_atomic_consume_sha256)
    lease_sha = _verify_lease(writer_lease, expected_writer_lease_sha256, "writer_lease")
    index_sha = _verify_index(receipt_index, expected_receipt_index_sha256, "receipt_index")
    if writer_lease.get("bound_state_sha256") != atomic_consume_verification.get("prior_state_sha256"):
        raise HumanGateWriterFencingError("writer_lease_state_binding_mismatch")
    if writer_lease.get("bound_generation") != atomic_consume_verification.get("cas_generation_from"):
        raise HumanGateWriterFencingError("writer_lease_generation_binding_mismatch")
    attempted_text, attempted_epoch = _iso(attempted_at, "attempted_at")
    _, issued_epoch = _iso(writer_lease.get("issued_at"), "writer_lease.issued_at")
    _, expiry_epoch = _iso(writer_lease.get("expires_at"), "writer_lease.expires_at")
    if not (issued_epoch <= attempted_epoch <= expiry_epoch):
        raise HumanGateWriterFencingError("writer_lease_expired_or_not_started_at_attempt")
    commit = _sha(commit_id, "commit_id")
    idem = _sha(idempotency_key_sha256, "idempotency_key_sha256")
    if commit in tuple(receipt_index.get("commit_ids") or ()):
        raise HumanGateWriterFencingError("commit_id_replay_detected")
    if idem in tuple(receipt_index.get("idempotency_key_sha256s") or ()):
        raise HumanGateWriterFencingError("idempotency_key_replay_detected")
    body = {
        "schema": ATTEMPT_SCHEMA,
        "atomic_consume_verification_sha256": atomic_sha,
        "case_id": _text(atomic_consume_verification.get("case_id"), "atomic.case_id"),
        "case_sha256": _sha(atomic_consume_verification.get("case_sha256"), "atomic.case_sha256"),
        "challenge_id": _sha(atomic_consume_verification.get("challenge_id"), "atomic.challenge_id"),
        "approval_verification_sha256": _sha(atomic_consume_verification.get("approval_verification_sha256"), "atomic.approval_verification_sha256"),
        "prior_state_sha256": _sha(atomic_consume_verification.get("prior_state_sha256"), "atomic.prior_state_sha256"),
        "next_state_candidate_sha256": _sha(atomic_consume_verification.get("next_state_candidate_sha256"), "atomic.next_state_candidate_sha256"),
        "generation_from": atomic_consume_verification["cas_generation_from"],
        "generation_to": atomic_consume_verification["cas_generation_to"],
        "writer_lease_sha256": lease_sha,
        "lease_id": _sha(writer_lease.get("lease_id"), "writer_lease.lease_id"),
        "writer_id": _text(writer_lease.get("writer_id"), "writer_lease.writer_id"),
        "lease_epoch": writer_lease["lease_epoch"],
        "fencing_token": writer_lease["fencing_token"],
        "lease_expires_at": writer_lease["expires_at"],
        "receipt_index_sha256": index_sha,
        "commit_id": commit,
        "idempotency_key_sha256": idem,
        "attempted_at": attempted_text,
        "fencing_precondition": "TOKEN_EQUALS_CURRENT_LEASE",
        "lease_window_verified": True,
        "blind_retry_allowed": False,
        "commit_receipt_required": True,
        "attempt_only": True,
        "write_performed": False,
        "durable_commit_proven": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["attempt_sha256"] = sha256_obj(body)
    return body


def _verify_attempt(attempt: Mapping[str, Any], expected_sha256: str) -> str:
    if not isinstance(attempt, Mapping) or attempt.get("schema") != ATTEMPT_SCHEMA:
        raise HumanGateWriterFencingError("attempt_schema_mismatch")
    digest = _verify_hash(attempt, "attempt_sha256", "attempt_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_attempt_sha256"):
        raise HumanGateWriterFencingError("attempt_external_digest_mismatch")
    _verify_safety(attempt, "attempt")
    _verify_false_effects(attempt, R8_EFFECTS, "attempt")
    if attempt.get("fencing_precondition") != "TOKEN_EQUALS_CURRENT_LEASE" or attempt.get("lease_window_verified") is not True:
        raise HumanGateWriterFencingError("attempt_fencing_or_lease_guard_missing")
    if attempt.get("blind_retry_allowed") is not False or attempt.get("commit_receipt_required") is not True:
        raise HumanGateWriterFencingError("attempt_retry_or_receipt_policy_invalid")
    if attempt.get("attempt_only") is not True or attempt.get("write_performed") is not False or attempt.get("durable_commit_proven") is not False:
        raise HumanGateWriterFencingError("attempt_write_or_durability_overclaim")
    if attempt.get("execution_authority") != "NONE":
        raise HumanGateWriterFencingError("attempt_authority_breached")
    if attempt.get("generation_to") != attempt.get("generation_from") + 1:
        raise HumanGateWriterFencingError("attempt_generation_transition_invalid")
    return digest


def build_durable_commit_receipt_candidate(
    fenced_commit_attempt: Mapping[str, Any],
    *,
    expected_attempt_sha256: str,
    backend_id: str,
    backend_transaction_id_sha256: str,
    accepted_at: str,
) -> dict[str, Any]:
    attempt_sha = _verify_attempt(fenced_commit_attempt, expected_attempt_sha256)
    accepted_text, accepted_epoch = _iso(accepted_at, "accepted_at")
    _, attempted_epoch = _iso(fenced_commit_attempt.get("attempted_at"), "attempt.attempted_at")
    _, expiry_epoch = _iso(fenced_commit_attempt.get("lease_expires_at"), "attempt.lease_expires_at")
    if not (attempted_epoch <= accepted_epoch <= expiry_epoch):
        raise HumanGateWriterFencingError("receipt_candidate_accept_time_outside_lease")
    body = {
        "schema": RECEIPT_CANDIDATE_SCHEMA,
        "attempt_sha256": attempt_sha,
        "case_id": fenced_commit_attempt["case_id"],
        "case_sha256": fenced_commit_attempt["case_sha256"],
        "challenge_id": fenced_commit_attempt["challenge_id"],
        "commit_id": fenced_commit_attempt["commit_id"],
        "idempotency_key_sha256": fenced_commit_attempt["idempotency_key_sha256"],
        "writer_lease_sha256": fenced_commit_attempt["writer_lease_sha256"],
        "lease_id": fenced_commit_attempt["lease_id"],
        "writer_id": fenced_commit_attempt["writer_id"],
        "fencing_token": fenced_commit_attempt["fencing_token"],
        "prior_state_sha256": fenced_commit_attempt["prior_state_sha256"],
        "next_state_candidate_sha256": fenced_commit_attempt["next_state_candidate_sha256"],
        "generation_from": fenced_commit_attempt["generation_from"],
        "generation_to": fenced_commit_attempt["generation_to"],
        "backend_id": _text(backend_id, "backend_id"),
        "backend_transaction_id_sha256": _sha(backend_transaction_id_sha256, "backend_transaction_id_sha256"),
        "accepted_at": accepted_text,
        "required_backend_semantics": "ATOMIC_CAS_PLUS_FENCING_TOKEN",
        "read_after_write_required": True,
        "receipt_kind": "EXPECTED_DURABLE_RECEIPT_SHAPE_ONLY",
        "receipt_issued": False,
        "write_performed": False,
        "durable_commit_proven": False,
        "live_backend_observed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["receipt_candidate_sha256"] = sha256_obj(body)
    return body


def _verify_receipt_candidate(candidate: Mapping[str, Any], expected_sha256: str) -> str:
    if not isinstance(candidate, Mapping) or candidate.get("schema") != RECEIPT_CANDIDATE_SCHEMA:
        raise HumanGateWriterFencingError("receipt_candidate_schema_mismatch")
    digest = _verify_hash(candidate, "receipt_candidate_sha256", "receipt_candidate_hash_mismatch")
    if digest != _sha(expected_sha256, "expected_receipt_candidate_sha256"):
        raise HumanGateWriterFencingError("receipt_candidate_external_digest_mismatch")
    _verify_safety(candidate, "receipt_candidate")
    _verify_false_effects(candidate, R8_EFFECTS, "receipt_candidate")
    if candidate.get("receipt_kind") != "EXPECTED_DURABLE_RECEIPT_SHAPE_ONLY":
        raise HumanGateWriterFencingError("receipt_candidate_kind_invalid")
    if candidate.get("required_backend_semantics") != "ATOMIC_CAS_PLUS_FENCING_TOKEN" or candidate.get("read_after_write_required") is not True:
        raise HumanGateWriterFencingError("receipt_candidate_backend_semantics_invalid")
    if candidate.get("receipt_issued") is not False or candidate.get("write_performed") is not False:
        raise HumanGateWriterFencingError("receipt_candidate_issuance_or_write_overclaim")
    if candidate.get("durable_commit_proven") is not False or candidate.get("live_backend_observed") is not False:
        raise HumanGateWriterFencingError("receipt_candidate_durability_overclaim")
    if candidate.get("execution_authority") != "NONE":
        raise HumanGateWriterFencingError("receipt_candidate_authority_breached")
    return digest


def build_crash_recovery_verification(
    fenced_commit_attempt: Mapping[str, Any],
    receipt_candidate: Mapping[str, Any],
    current_writer_lease: Mapping[str, Any],
    current_receipt_index: Mapping[str, Any],
    *,
    expected_attempt_sha256: str,
    expected_receipt_candidate_sha256: str,
    expected_current_writer_lease_sha256: str,
    expected_current_receipt_index_sha256: str,
    crash_point: str,
    readback_state_sha256: str,
    readback_generation: int,
    observed_at: str,
) -> dict[str, Any]:
    attempt_sha = _verify_attempt(fenced_commit_attempt, expected_attempt_sha256)
    receipt_sha = _verify_receipt_candidate(receipt_candidate, expected_receipt_candidate_sha256)
    lease_sha = _verify_lease(current_writer_lease, expected_current_writer_lease_sha256, "current_writer_lease")
    index_sha = _verify_index(current_receipt_index, expected_current_receipt_index_sha256, "current_receipt_index")
    if receipt_candidate.get("attempt_sha256") != attempt_sha:
        raise HumanGateWriterFencingError("recovery_receipt_attempt_binding_mismatch")
    for field in ("case_id", "case_sha256", "challenge_id", "commit_id", "idempotency_key_sha256", "prior_state_sha256", "next_state_candidate_sha256"):
        if receipt_candidate.get(field) != fenced_commit_attempt.get(field):
            raise HumanGateWriterFencingError(f"recovery_receipt_attempt_field_mismatch:{field}")

    crash = _text(crash_point, "crash_point").upper()
    if crash not in CRASH_POINTS:
        raise HumanGateWriterFencingError("crash_point_invalid")
    observed_text, observed_epoch = _iso(observed_at, "observed_at")
    readback_state = _sha(readback_state_sha256, "readback_state_sha256")
    readback_gen = _nonnegative_int(readback_generation, "readback_generation")

    attempt_token = _positive_int(fenced_commit_attempt.get("fencing_token"), "attempt.fencing_token")
    current_token = _positive_int(current_writer_lease.get("fencing_token"), "current_lease.fencing_token")
    if current_token < attempt_token:
        raise HumanGateWriterFencingError("recovery_lease_fencing_token_regressed")
    same_lease = current_writer_lease.get("lease_id") == fenced_commit_attempt.get("lease_id")
    same_writer = current_writer_lease.get("writer_id") == fenced_commit_attempt.get("writer_id")
    if current_token == attempt_token and (not same_lease or not same_writer):
        raise HumanGateWriterFencingError("split_brain_same_fencing_token_detected")
    stale_writer_fenced = current_token > attempt_token

    _, lease_start = _iso(current_writer_lease.get("issued_at"), "current_writer_lease.issued_at")
    _, lease_end = _iso(current_writer_lease.get("expires_at"), "current_writer_lease.expires_at")
    current_lease_live = same_lease and same_writer and current_token == attempt_token and lease_start <= observed_epoch <= lease_end

    commits = tuple(current_receipt_index.get("commit_ids") or ())
    keys = tuple(current_receipt_index.get("idempotency_key_sha256s") or ())
    commit_seen = fenced_commit_attempt["commit_id"] in commits
    key_seen = fenced_commit_attempt["idempotency_key_sha256"] in keys
    if commit_seen is not key_seen:
        raise HumanGateWriterFencingError("receipt_index_partial_commit_identity_detected")
    receipt_indexed = commit_seen and key_seen

    prior_state = fenced_commit_attempt["prior_state_sha256"]
    next_state = fenced_commit_attempt["next_state_candidate_sha256"]
    generation_from = fenced_commit_attempt["generation_from"]
    generation_to = fenced_commit_attempt["generation_to"]

    if stale_writer_fenced:
        recovery_status = "STALE_WRITER_FENCED_REACQUIRE_REQUIRED"
        recovery_action = "REACQUIRE_LEASE_AND_RECOMPARE"
        retry_allowed = False
    elif crash == "BEFORE_WRITE":
        if readback_state != prior_state or readback_gen != generation_from or receipt_indexed:
            raise HumanGateWriterFencingError("before_write_readback_or_receipt_conflict")
        recovery_status = "NO_WRITE_OBSERVED_RETRY_REQUIRES_FRESH_CAS"
        recovery_action = "RECOMPARE_BEFORE_ANY_RETRY"
        retry_allowed = current_lease_live
    elif crash == "AFTER_WRITE_BEFORE_RECEIPT":
        if readback_state != next_state or readback_gen != generation_to or receipt_indexed:
            raise HumanGateWriterFencingError("post_write_pre_receipt_readback_conflict")
        recovery_status = "WRITE_OBSERVED_RECEIPT_ABSENT_HOLD"
        recovery_action = "HOLD_AND_RECONCILE_EXTERNAL_BACKEND"
        retry_allowed = False
    else:
        if readback_state != next_state or readback_gen != generation_to or not receipt_indexed:
            raise HumanGateWriterFencingError("post_receipt_readback_or_index_conflict")
        recovery_status = "RECEIPT_INDEXED_DEDUP_NO_RETRY"
        recovery_action = "DEDUP_AND_ACK_ONLY"
        retry_allowed = False

    body = {
        "schema": RECOVERY_SCHEMA,
        "attempt_sha256": attempt_sha,
        "receipt_candidate_sha256": receipt_sha,
        "current_writer_lease_sha256": lease_sha,
        "current_receipt_index_sha256": index_sha,
        "case_id": fenced_commit_attempt["case_id"],
        "case_sha256": fenced_commit_attempt["case_sha256"],
        "challenge_id": fenced_commit_attempt["challenge_id"],
        "approval_verification_sha256": fenced_commit_attempt["approval_verification_sha256"],
        "atomic_consume_verification_sha256": fenced_commit_attempt["atomic_consume_verification_sha256"],
        "commit_id": fenced_commit_attempt["commit_id"],
        "idempotency_key_sha256": fenced_commit_attempt["idempotency_key_sha256"],
        "attempt_writer_lease_sha256": fenced_commit_attempt["writer_lease_sha256"],
        "attempt_fencing_token": attempt_token,
        "current_fencing_token": current_token,
        "stale_writer_fenced": stale_writer_fenced,
        "split_brain_same_token_rejected": True,
        "crash_point": crash,
        "readback_state_sha256": readback_state,
        "readback_generation": readback_gen,
        "receipt_indexed": receipt_indexed,
        "current_lease_live": current_lease_live,
        "recovery_status": recovery_status,
        "recovery_action": recovery_action,
        "retry_allowed": retry_allowed,
        "blind_retry_allowed": False,
        "fencing_model": "MONOTONIC_FENCING_TOKEN_PLUS_LEASE_DIGEST",
        "crash_recovery_protocol": "READBACK_PLUS_RECEIPT_INDEX_DEDUP",
        "protocol_status": "FENCING_AND_CRASH_RECOVERY_VERIFIED_SHADOW_ONLY",
        "live_writer_backend_proven": False,
        "durable_commit_proven": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "observed_at": observed_text,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(R8_EFFECTS),
    }
    body["recovery_verification_sha256"] = sha256_obj(body)
    return body
