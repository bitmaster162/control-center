from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

ASYMMETRIC_APPROVAL_SCHEMA_V2 = "control_center.shadow_asymmetric_human_approval_verification.v2"
GATE_STATE_SCHEMA = "control_center.shadow_human_gate_state_snapshot.v1"
PREPARE_SCHEMA = "control_center.shadow_human_gate_consume_prepare.v1"
COMPARE_SCHEMA = "control_center.shadow_human_gate_consume_compare.v1"
COMMIT_SCHEMA = "control_center.shadow_human_gate_consume_commit_candidate.v1"
VERIFICATION_SCHEMA = "control_center.shadow_human_gate_atomic_consume_verification.v1"

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
    "current_truth_apply": False,
    "decision_ledger_write": False,
    "command_queue_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}


class HumanGateAtomicConsumeError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanGateAtomicConsumeError(f"{field}_required")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HumanGateAtomicConsumeError(f"{field}_must_be_sha256")
    return text


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise HumanGateAtomicConsumeError(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise HumanGateAtomicConsumeError(code)
    return supplied


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise HumanGateAtomicConsumeError(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise HumanGateAtomicConsumeError(f"unsafe_{field}:{key}")


def _verify_no_effects(record: Mapping[str, Any], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(NO_EFFECTS):
        raise HumanGateAtomicConsumeError(f"{field}_effect_keys_mismatch")
    if any(value is not False for value in effects.values()):
        raise HumanGateAtomicConsumeError(f"{field}_effect_boundary_breached")


def _unique_shas(values: Sequence[str], field: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise HumanGateAtomicConsumeError(f"{field}_must_be_sequence")
    rows = tuple(_sha(value, field) for value in values)
    if len(set(rows)) != len(rows):
        raise HumanGateAtomicConsumeError(f"{field}_duplicates_forbidden")
    return rows


def _verify_approval(approval: Mapping[str, Any], expected_approval_sha256: str) -> tuple[str, str, str]:
    if not isinstance(approval, Mapping) or approval.get("schema") != ASYMMETRIC_APPROVAL_SCHEMA_V2:
        raise HumanGateAtomicConsumeError("approval_schema_mismatch")
    approval_sha = _verify_hash(approval, "asymmetric_approval_verification_sha256", "approval_hash_mismatch")
    if approval_sha != _sha(expected_approval_sha256, "expected_approval_sha256"):
        raise HumanGateAtomicConsumeError("approval_external_digest_mismatch")
    if approval.get("status") != "ASYMMETRIC_HUMAN_APPROVAL_VERIFIED_SHADOW_ONLY":
        raise HumanGateAtomicConsumeError("approval_status_invalid")
    if approval.get("approval_scope") != "HUMAN_REVEAL_ONLY":
        raise HumanGateAtomicConsumeError("approval_scope_invalid")
    if approval.get("external_assertion_digest_consumed") is not True:
        raise HumanGateAtomicConsumeError("approval_external_assertion_guard_missing")
    if approval.get("external_asymmetric_verifier_evidence") != "EXPECTED_DIGEST_BOUND":
        raise HumanGateAtomicConsumeError("approval_external_verifier_evidence_invalid")
    if approval.get("trust_upgrade") != "SELF_HASH_TO_INDEPENDENT_ASSERTION_DIGEST":
        raise HumanGateAtomicConsumeError("approval_trust_upgrade_invalid")
    if approval.get("registry_write_performed") is not False or approval.get("apply_allowed") is not False:
        raise HumanGateAtomicConsumeError("approval_write_or_apply_breached")
    if approval.get("execution_authority") != "NONE" or approval.get("can_execute") is not False:
        raise HumanGateAtomicConsumeError("approval_authority_breached")
    _verify_safety(approval, "approval")
    _verify_no_effects(approval, "approval")

    challenge_id = _sha(approval.get("challenge_id"), "approval.challenge_id")
    next_nonce = approval.get("next_nonce_registry_candidate")
    if not isinstance(next_nonce, Mapping):
        raise HumanGateAtomicConsumeError("approval_next_nonce_registry_missing")
    next_nonce_sha = _verify_hash(next_nonce, "registry_sha256", "approval_next_nonce_registry_hash_mismatch")
    if approval.get("next_nonce_registry_candidate_sha256") != next_nonce_sha:
        raise HumanGateAtomicConsumeError("approval_next_nonce_registry_binding_mismatch")
    used_challenges = tuple(next_nonce.get("used_challenge_ids") or ())
    used_nonces = tuple(next_nonce.get("used_nonce_sha256s") or ())
    if not used_challenges or not used_nonces:
        raise HumanGateAtomicConsumeError("approval_next_nonce_registry_consume_missing")
    if _sha(used_challenges[-1], "approval.next_nonce.last_challenge_id") != challenge_id:
        raise HumanGateAtomicConsumeError("approval_next_nonce_registry_challenge_mismatch")
    nonce_sha = _sha(used_nonces[-1], "approval.next_nonce.last_nonce_sha256")
    if challenge_id in tuple(used_challenges[:-1]) or nonce_sha in tuple(used_nonces[:-1]):
        raise HumanGateAtomicConsumeError("approval_next_nonce_registry_duplicate_consume")

    next_credential = approval.get("next_credential_registry_candidate")
    if not isinstance(next_credential, Mapping):
        raise HumanGateAtomicConsumeError("approval_next_credential_registry_missing")
    next_credential_sha = _verify_hash(next_credential, "registry_sha256", "approval_next_credential_registry_hash_mismatch")
    if approval.get("next_credential_registry_candidate_sha256") != next_credential_sha:
        raise HumanGateAtomicConsumeError("approval_next_credential_registry_binding_mismatch")
    return approval_sha, challenge_id, nonce_sha


def build_human_gate_state_snapshot(*, state_id: str, authority_root_sha256: str, generation: int,
    credential_registry_sha256: str, nonce_registry_sha256: str,
    consumed_challenge_ids: Sequence[str] = (), consumed_nonce_sha256s: Sequence[str] = (),
    previous_state_sha256: str) -> dict[str, Any]:
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise HumanGateAtomicConsumeError("state_generation_invalid")
    body = {
        "schema": GATE_STATE_SCHEMA,
        "state_id": _text(state_id, "state_id"),
        "authority_root_sha256": _sha(authority_root_sha256, "authority_root_sha256"),
        "generation": generation,
        "credential_registry_sha256": _sha(credential_registry_sha256, "credential_registry_sha256"),
        "nonce_registry_sha256": _sha(nonce_registry_sha256, "nonce_registry_sha256"),
        "consumed_challenge_ids": _unique_shas(consumed_challenge_ids, "consumed_challenge_id"),
        "consumed_nonce_sha256s": _unique_shas(consumed_nonce_sha256s, "consumed_nonce_sha256"),
        "previous_state_sha256": _sha(previous_state_sha256, "previous_state_sha256"),
        "write_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["state_sha256"] = sha256_obj(body)
    return body


def _verify_state(state: Mapping[str, Any], expected_state_sha256: str, field: str) -> str:
    if not isinstance(state, Mapping) or state.get("schema") != GATE_STATE_SCHEMA:
        raise HumanGateAtomicConsumeError(f"{field}_schema_mismatch")
    state_sha = _verify_hash(state, "state_sha256", f"{field}_hash_mismatch")
    if state_sha != _sha(expected_state_sha256, f"expected_{field}_sha256"):
        raise HumanGateAtomicConsumeError(f"{field}_external_digest_mismatch")
    if state.get("write_allowed") is not False or state.get("apply_allowed") is not False or state.get("execution_authority") != "NONE":
        raise HumanGateAtomicConsumeError(f"{field}_authority_or_write_breached")
    _verify_safety(state, field)
    _verify_no_effects(state, field)
    _unique_shas(tuple(state.get("consumed_challenge_ids") or ()), f"{field}.consumed_challenge_id")
    _unique_shas(tuple(state.get("consumed_nonce_sha256s") or ()), f"{field}.consumed_nonce_sha256")
    return state_sha


def build_human_gate_consume_prepare(approval: Mapping[str, Any], prior_state: Mapping[str, Any], *,
    expected_approval_sha256: str, expected_prior_state_sha256: str) -> dict[str, Any]:
    approval_sha, challenge_id, nonce_sha = _verify_approval(approval, expected_approval_sha256)
    state_sha = _verify_state(prior_state, expected_prior_state_sha256, "prior_state")
    if prior_state.get("credential_registry_sha256") != approval.get("prior_credential_registry_sha256"):
        raise HumanGateAtomicConsumeError("prepare_credential_registry_snapshot_mismatch")
    if prior_state.get("nonce_registry_sha256") != approval.get("prior_nonce_registry_sha256"):
        raise HumanGateAtomicConsumeError("prepare_nonce_registry_snapshot_mismatch")
    if challenge_id in tuple(prior_state.get("consumed_challenge_ids") or ()):
        raise HumanGateAtomicConsumeError("prepare_challenge_already_consumed")
    if nonce_sha in tuple(prior_state.get("consumed_nonce_sha256s") or ()):
        raise HumanGateAtomicConsumeError("prepare_nonce_already_consumed")
    body = {
        "schema": PREPARE_SCHEMA,
        "approval_verification_sha256": approval_sha,
        "external_assertion_sha256": _sha(approval.get("external_assertion_sha256"), "approval.external_assertion_sha256"),
        "case_id": _text(approval.get("case_id"), "approval.case_id"),
        "case_sha256": _sha(approval.get("case_sha256"), "approval.case_sha256"),
        "packet_sha256": _sha(approval.get("packet_sha256"), "approval.packet_sha256"),
        "challenge_id": challenge_id,
        "nonce_sha256": nonce_sha,
        "expected_prior_state_sha256": state_sha,
        "expected_prior_generation": prior_state.get("generation"),
        "expected_prior_credential_registry_sha256": _sha(approval.get("prior_credential_registry_sha256"), "approval.prior_credential_registry_sha256"),
        "expected_prior_nonce_registry_sha256": _sha(approval.get("prior_nonce_registry_sha256"), "approval.prior_nonce_registry_sha256"),
        "next_credential_registry_candidate_sha256": _sha(approval.get("next_credential_registry_candidate_sha256"), "approval.next_credential_registry_candidate_sha256"),
        "next_nonce_registry_candidate_sha256": _sha(approval.get("next_nonce_registry_candidate_sha256"), "approval.next_nonce_registry_candidate_sha256"),
        "consume_scope": "HUMAN_REVEAL_SINGLE_USE_ONLY",
        "cas_required": True,
        "prepare_only": True,
        "commit_authorized": False,
        "write_performed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["prepare_sha256"] = sha256_obj(body)
    return body


def build_human_gate_consume_compare(prepare: Mapping[str, Any], current_state: Mapping[str, Any], *,
    expected_current_state_sha256: str) -> dict[str, Any]:
    if not isinstance(prepare, Mapping) or prepare.get("schema") != PREPARE_SCHEMA:
        raise HumanGateAtomicConsumeError("compare_prepare_schema_mismatch")
    prepare_sha = _verify_hash(prepare, "prepare_sha256", "compare_prepare_hash_mismatch")
    _verify_safety(prepare, "prepare")
    _verify_no_effects(prepare, "prepare")
    current_sha = _verify_state(current_state, expected_current_state_sha256, "current_state")
    if current_sha != prepare.get("expected_prior_state_sha256"):
        raise HumanGateAtomicConsumeError("compare_and_swap_state_changed")
    if current_state.get("generation") != prepare.get("expected_prior_generation"):
        raise HumanGateAtomicConsumeError("compare_and_swap_generation_changed")
    if current_state.get("credential_registry_sha256") != prepare.get("expected_prior_credential_registry_sha256"):
        raise HumanGateAtomicConsumeError("compare_credential_registry_changed")
    if current_state.get("nonce_registry_sha256") != prepare.get("expected_prior_nonce_registry_sha256"):
        raise HumanGateAtomicConsumeError("compare_nonce_registry_changed")
    if prepare.get("challenge_id") in tuple(current_state.get("consumed_challenge_ids") or ()):
        raise HumanGateAtomicConsumeError("compare_challenge_already_consumed")
    if prepare.get("nonce_sha256") in tuple(current_state.get("consumed_nonce_sha256s") or ()):
        raise HumanGateAtomicConsumeError("compare_nonce_already_consumed")
    body = {
        "schema": COMPARE_SCHEMA,
        "prepare_sha256": prepare_sha,
        "compared_state_sha256": current_sha,
        "compared_generation": current_state["generation"],
        "challenge_id": prepare["challenge_id"],
        "nonce_sha256": prepare["nonce_sha256"],
        "cas_match": True,
        "compare_result": "MATCH_SHADOW_ONLY",
        "compare_only": True,
        "commit_authorized": False,
        "write_performed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["compare_sha256"] = sha256_obj(body)
    return body


def build_human_gate_consume_commit_candidate(prepare: Mapping[str, Any], compare: Mapping[str, Any],
    current_state: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(prepare, Mapping) or prepare.get("schema") != PREPARE_SCHEMA:
        raise HumanGateAtomicConsumeError("commit_prepare_schema_mismatch")
    prepare_sha = _verify_hash(prepare, "prepare_sha256", "commit_prepare_hash_mismatch")
    if not isinstance(compare, Mapping) or compare.get("schema") != COMPARE_SCHEMA:
        raise HumanGateAtomicConsumeError("commit_compare_schema_mismatch")
    compare_sha = _verify_hash(compare, "compare_sha256", "commit_compare_hash_mismatch")
    current_sha = _verify_hash(current_state, "state_sha256", "commit_current_state_hash_mismatch")
    if compare.get("prepare_sha256") != prepare_sha or compare.get("compared_state_sha256") != current_sha:
        raise HumanGateAtomicConsumeError("commit_compare_binding_mismatch")
    if compare.get("cas_match") is not True or compare.get("compare_result") != "MATCH_SHADOW_ONLY":
        raise HumanGateAtomicConsumeError("commit_compare_not_matched")
    if current_sha != prepare.get("expected_prior_state_sha256"):
        raise HumanGateAtomicConsumeError("commit_state_changed_after_compare")
    if current_state.get("generation") != prepare.get("expected_prior_generation"):
        raise HumanGateAtomicConsumeError("commit_generation_changed_after_compare")
    consumed_challenges = tuple(current_state.get("consumed_challenge_ids") or ())
    consumed_nonces = tuple(current_state.get("consumed_nonce_sha256s") or ())
    if prepare["challenge_id"] in consumed_challenges or prepare["nonce_sha256"] in consumed_nonces:
        raise HumanGateAtomicConsumeError("commit_subject_already_consumed")
    next_state = build_human_gate_state_snapshot(
        state_id=current_state["state_id"], authority_root_sha256=current_state["authority_root_sha256"],
        generation=current_state["generation"] + 1,
        credential_registry_sha256=prepare["next_credential_registry_candidate_sha256"],
        nonce_registry_sha256=prepare["next_nonce_registry_candidate_sha256"],
        consumed_challenge_ids=(*consumed_challenges, prepare["challenge_id"]),
        consumed_nonce_sha256s=(*consumed_nonces, prepare["nonce_sha256"]),
        previous_state_sha256=current_sha,
    )
    body = {
        "schema": COMMIT_SCHEMA,
        "prepare_sha256": prepare_sha,
        "compare_sha256": compare_sha,
        "cas_precondition_state_sha256": current_sha,
        "cas_generation_from": current_state["generation"],
        "cas_generation_to": current_state["generation"] + 1,
        "approval_verification_sha256": prepare["approval_verification_sha256"],
        "case_id": prepare["case_id"],
        "case_sha256": prepare["case_sha256"],
        "challenge_id": prepare["challenge_id"],
        "nonce_sha256": prepare["nonce_sha256"],
        "next_state_candidate": next_state,
        "next_state_candidate_sha256": next_state["state_sha256"],
        "protocol_result": "COMMITTABLE_IF_ATOMIC_CAS_WRITER_ACCEPTS",
        "commit_performed": False,
        "durable_single_use_enforced": False,
        "human_gate_write_performed": False,
        "commit_authorized": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["commit_candidate_sha256"] = sha256_obj(body)
    return body


def build_human_gate_atomic_consume_verification(prepare: Mapping[str, Any], compare: Mapping[str, Any],
    commit_candidate: Mapping[str, Any], *, expected_commit_candidate_sha256: str) -> dict[str, Any]:
    prepare_sha = _verify_hash(prepare, "prepare_sha256", "atomic_prepare_hash_mismatch")
    compare_sha = _verify_hash(compare, "compare_sha256", "atomic_compare_hash_mismatch")
    commit_sha = _verify_hash(commit_candidate, "commit_candidate_sha256", "atomic_commit_hash_mismatch")
    if commit_sha != _sha(expected_commit_candidate_sha256, "expected_commit_candidate_sha256"):
        raise HumanGateAtomicConsumeError("atomic_commit_external_digest_mismatch")
    for record, field in ((prepare, "prepare"), (compare, "compare"), (commit_candidate, "commit")):
        _verify_safety(record, field)
        _verify_no_effects(record, field)
    if compare.get("prepare_sha256") != prepare_sha or commit_candidate.get("prepare_sha256") != prepare_sha:
        raise HumanGateAtomicConsumeError("atomic_prepare_lineage_mismatch")
    if commit_candidate.get("compare_sha256") != compare_sha:
        raise HumanGateAtomicConsumeError("atomic_compare_lineage_mismatch")
    if commit_candidate.get("commit_performed") is not False or commit_candidate.get("durable_single_use_enforced") is not False:
        raise HumanGateAtomicConsumeError("atomic_durable_commit_overclaim")
    if commit_candidate.get("human_gate_write_performed") is not False or commit_candidate.get("execution_authority") != "NONE":
        raise HumanGateAtomicConsumeError("atomic_effect_or_authority_breached")
    body = {
        "schema": VERIFICATION_SCHEMA,
        "prepare_sha256": prepare_sha,
        "compare_sha256": compare_sha,
        "commit_candidate_sha256": commit_sha,
        "approval_verification_sha256": commit_candidate["approval_verification_sha256"],
        "case_id": commit_candidate["case_id"],
        "case_sha256": commit_candidate["case_sha256"],
        "challenge_id": commit_candidate["challenge_id"],
        "nonce_sha256": commit_candidate["nonce_sha256"],
        "prior_state_sha256": commit_candidate["cas_precondition_state_sha256"],
        "next_state_candidate_sha256": commit_candidate["next_state_candidate_sha256"],
        "cas_generation_from": commit_candidate["cas_generation_from"],
        "cas_generation_to": commit_candidate["cas_generation_to"],
        "toctou_guard_model": "COMPARE_AND_SWAP_PRECONDITION",
        "atomicity_status": "PROTOCOL_VERIFIED_NO_DURABLE_COMMIT",
        "single_use_status": "CANDIDATE_ONLY_NOT_DURABLY_ENFORCED",
        "commit_performed": False,
        "human_gate_write_performed": False,
        "current_truth_promotion_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["atomic_consume_verification_sha256"] = sha256_obj(body)
    return body
