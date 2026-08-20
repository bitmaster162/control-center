from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

CHALLENGE_SCHEMA = "control_center.shadow_human_approval_challenge.v1"
CREDENTIAL_REGISTRY_SCHEMA = "control_center.shadow_human_credential_registry_snapshot.v1"
NONCE_REGISTRY_SCHEMA = "control_center.shadow_human_nonce_epoch_registry_snapshot.v1"
ASYMMETRIC_ASSERTION_SCHEMA = "control_center.shadow_asymmetric_authenticator_assertion.v1"
ASYMMETRIC_VERIFICATION_SCHEMA = "control_center.shadow_asymmetric_human_approval_verification.v1"

SUPPORTED_ALGORITHMS = {"ED25519", "ES256"}

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


class HumanAsymmetricCustodyError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanAsymmetricCustodyError(f"{field}_required")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HumanAsymmetricCustodyError(f"{field}_must_be_sha256")
    return text


def _iso(value: Any, field: str) -> tuple[str, float]:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise HumanAsymmetricCustodyError(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise HumanAsymmetricCustodyError(f"{field}_timezone_required")
    return text, parsed.timestamp()


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise HumanAsymmetricCustodyError(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise HumanAsymmetricCustodyError(code)
    return supplied


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise HumanAsymmetricCustodyError(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise HumanAsymmetricCustodyError(f"unsafe_{field}:{key}")


def _verify_no_effects(record: Mapping[str, Any], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(NO_EFFECTS):
        raise HumanAsymmetricCustodyError(f"{field}_effect_keys_mismatch")
    if any(value is not False for value in effects.values()):
        raise HumanAsymmetricCustodyError(f"{field}_effect_boundary_breached")


def _options(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise HumanAsymmetricCustodyError("options_must_be_sequence")
    clean = tuple(dict.fromkeys(_text(item, "option").upper() for item in value))
    if len(clean) < 2 or "WAIT" not in clean:
        raise HumanAsymmetricCustodyError("options_must_include_wait_and_alternative")
    return clean


def derive_reveal_intent_sha256(
    *,
    case_id: str,
    case_sha256: str,
    packet_sha256: str,
    twin_prediction_id: str,
    actual_choice: str,
    responded_at: str,
) -> str:
    response_text, _ = _iso(responded_at, "responded_at")
    return sha256_obj(
        {
            "case_id": _text(case_id, "case_id"),
            "case_sha256": _sha(case_sha256, "case_sha256"),
            "packet_sha256": _sha(packet_sha256, "packet_sha256"),
            "twin_prediction_id": _sha(twin_prediction_id, "twin_prediction_id"),
            "actual_choice": _text(actual_choice, "actual_choice").upper(),
            "responded_at": response_text,
        }
    )


def build_human_credential_registry_snapshot(
    *,
    registry_id: str,
    authority_root_sha256: str,
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise HumanAsymmetricCustodyError("credential_entries_must_be_sequence")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HumanAsymmetricCustodyError("credential_entry_must_be_object")
        credential_id = _sha(entry.get("credential_id_sha256"), "credential.credential_id_sha256")
        if credential_id in seen:
            raise HumanAsymmetricCustodyError("credential_duplicate_id")
        seen.add(credential_id)
        algorithm = _text(entry.get("algorithm"), "credential.algorithm").upper()
        if algorithm not in SUPPORTED_ALGORITHMS:
            raise HumanAsymmetricCustodyError("credential_algorithm_unsupported")
        key_epoch = entry.get("key_epoch")
        sign_count = entry.get("sign_count")
        if isinstance(key_epoch, bool) or not isinstance(key_epoch, int) or key_epoch < 1:
            raise HumanAsymmetricCustodyError("credential_key_epoch_invalid")
        if isinstance(sign_count, bool) or not isinstance(sign_count, int) or sign_count < 0:
            raise HumanAsymmetricCustodyError("credential_sign_count_invalid")
        not_before, not_before_epoch = _iso(entry.get("not_before"), "credential.not_before")
        not_after, not_after_epoch = _iso(entry.get("not_after"), "credential.not_after")
        if not_after_epoch <= not_before_epoch:
            raise HumanAsymmetricCustodyError("credential_validity_window_invalid")
        status = _text(entry.get("status"), "credential.status").upper()
        if status not in {"ACTIVE", "REVOKED", "RETIRED"}:
            raise HumanAsymmetricCustodyError("credential_status_invalid")
        revoked_at = entry.get("revoked_at")
        if status == "REVOKED":
            _iso(revoked_at, "credential.revoked_at")
        elif revoked_at is not None:
            raise HumanAsymmetricCustodyError("credential_revoked_at_without_revoked_status")
        normalized.append(
            {
                "human_subject_id": _text(entry.get("human_subject_id"), "credential.human_subject_id"),
                "device_id": _text(entry.get("device_id"), "credential.device_id"),
                "custody_provider_id": _text(entry.get("custody_provider_id"), "credential.custody_provider_id"),
                "credential_id_sha256": credential_id,
                "public_key_sha256": _sha(entry.get("public_key_sha256"), "credential.public_key_sha256"),
                "algorithm": algorithm,
                "key_epoch": key_epoch,
                "status": status,
                "not_before": not_before,
                "not_after": not_after,
                "revoked_at": revoked_at,
                "counter_supported": entry.get("counter_supported") is True,
                "sign_count": sign_count,
            }
        )
    body = {
        "schema": CREDENTIAL_REGISTRY_SCHEMA,
        "registry_id": _text(registry_id, "registry_id"),
        "authority_root_sha256": _sha(authority_root_sha256, "authority_root_sha256"),
        "entries": tuple(normalized),
        "entry_count": len(normalized),
        "write_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["registry_sha256"] = sha256_obj(body)
    return body


def build_nonce_epoch_registry_snapshot(
    *,
    registry_id: str,
    authority_root_sha256: str,
    epoch_number: int,
    epoch_started_at: str,
    epoch_expires_at: str,
    previous_epoch_sha256: str,
    used_nonce_sha256s: Sequence[str] = (),
    used_challenge_ids: Sequence[str] = (),
) -> dict[str, Any]:
    if isinstance(epoch_number, bool) or not isinstance(epoch_number, int) or epoch_number < 1:
        raise HumanAsymmetricCustodyError("nonce_epoch_number_invalid")
    started_text, started_epoch = _iso(epoch_started_at, "epoch_started_at")
    expires_text, expires_epoch = _iso(epoch_expires_at, "epoch_expires_at")
    if expires_epoch <= started_epoch:
        raise HumanAsymmetricCustodyError("nonce_epoch_window_invalid")
    nonces = tuple(dict.fromkeys(_sha(value, "used_nonce_sha256") for value in used_nonce_sha256s))
    challenges = tuple(dict.fromkeys(_sha(value, "used_challenge_id") for value in used_challenge_ids))
    if len(nonces) != len(tuple(used_nonce_sha256s)) or len(challenges) != len(tuple(used_challenge_ids)):
        raise HumanAsymmetricCustodyError("nonce_epoch_duplicate_history")
    body = {
        "schema": NONCE_REGISTRY_SCHEMA,
        "registry_id": _text(registry_id, "registry_id"),
        "authority_root_sha256": _sha(authority_root_sha256, "authority_root_sha256"),
        "epoch_number": epoch_number,
        "epoch_started_at": started_text,
        "epoch_expires_at": expires_text,
        "previous_epoch_sha256": _sha(previous_epoch_sha256, "previous_epoch_sha256"),
        "used_nonce_sha256s": nonces,
        "used_challenge_ids": challenges,
        "cumulative_history": True,
        "write_allowed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["registry_sha256"] = sha256_obj(body)
    return body


def _verify_challenge(challenge: Mapping[str, Any]) -> str:
    if not isinstance(challenge, Mapping) or challenge.get("schema") != CHALLENGE_SCHEMA:
        raise HumanAsymmetricCustodyError("challenge_schema_mismatch")
    challenge_sha = _verify_hash(challenge, "challenge_sha256", "challenge_hash_mismatch")
    if challenge.get("purpose") != "HUMAN_REVEAL_ONLY" or challenge.get("does_not_authorize_execution") is not True:
        raise HumanAsymmetricCustodyError("challenge_scope_invalid")
    if challenge.get("execution_authority") != "NONE" or challenge.get("can_execute") is not False:
        raise HumanAsymmetricCustodyError("challenge_authority_breached")
    _verify_safety(challenge, "challenge")
    # R5 challenge effect keys differ from R6 registries; only assert all supplied effects are false here.
    effects = challenge.get("effects")
    if not isinstance(effects, Mapping) or any(value is not False for value in effects.values()):
        raise HumanAsymmetricCustodyError("challenge_effect_boundary_breached")
    _options(challenge.get("options", ()))
    _iso(challenge.get("issued_at"), "challenge.issued_at")
    _iso(challenge.get("expires_at"), "challenge.expires_at")
    _sha(challenge.get("case_sha256"), "challenge.case_sha256")
    _sha(challenge.get("packet_sha256"), "challenge.packet_sha256")
    _sha(challenge.get("twin_prediction_id"), "challenge.twin_prediction_id")
    _sha(challenge.get("challenge_id"), "challenge.challenge_id")
    return challenge_sha


def _verify_registry_snapshot(record: Mapping[str, Any], *, schema: str, expected_sha256: str, expected_root: str, field: str) -> str:
    if not isinstance(record, Mapping) or record.get("schema") != schema:
        raise HumanAsymmetricCustodyError(f"{field}_schema_mismatch")
    digest = _verify_hash(record, "registry_sha256", f"{field}_hash_mismatch")
    if digest != _sha(expected_sha256, f"expected_{field}_sha256"):
        raise HumanAsymmetricCustodyError(f"{field}_external_digest_mismatch")
    if record.get("authority_root_sha256") != _sha(expected_root, "expected_authority_root_sha256"):
        raise HumanAsymmetricCustodyError(f"{field}_authority_root_mismatch")
    if record.get("write_allowed") is not False or record.get("apply_allowed") is not False or record.get("execution_authority") != "NONE":
        raise HumanAsymmetricCustodyError(f"{field}_authority_or_write_breached")
    _verify_safety(record, field)
    _verify_no_effects(record, field)
    return digest


def verify_asymmetric_human_approval(
    challenge: Mapping[str, Any],
    assertion: Mapping[str, Any],
    credential_registry: Mapping[str, Any],
    nonce_registry: Mapping[str, Any],
    *,
    expected_credential_registry_sha256: str,
    expected_nonce_registry_sha256: str,
    expected_authority_root_sha256: str,
    expected_human_subject_id: str,
    expected_custody_provider_id: str,
    expected_verifier_id: str,
    expected_verifier_key_id: str,
    expected_origin: str,
    expected_rp_id: str,
    expected_key_epoch: int,
    verified_at: str,
) -> dict[str, Any]:
    challenge_sha = _verify_challenge(challenge)
    credential_registry_sha = _verify_registry_snapshot(
        credential_registry,
        schema=CREDENTIAL_REGISTRY_SCHEMA,
        expected_sha256=expected_credential_registry_sha256,
        expected_root=expected_authority_root_sha256,
        field="credential_registry",
    )
    nonce_registry_sha = _verify_registry_snapshot(
        nonce_registry,
        schema=NONCE_REGISTRY_SCHEMA,
        expected_sha256=expected_nonce_registry_sha256,
        expected_root=expected_authority_root_sha256,
        field="nonce_registry",
    )

    if not isinstance(assertion, Mapping) or assertion.get("schema") != ASYMMETRIC_ASSERTION_SCHEMA:
        raise HumanAsymmetricCustodyError("assertion_schema_mismatch")
    assertion_sha = _verify_hash(assertion, "assertion_sha256", "assertion_hash_mismatch")
    _verify_safety(assertion, "assertion")
    _verify_no_effects(assertion, "assertion")

    subject = _text(expected_human_subject_id, "expected_human_subject_id")
    provider = _text(expected_custody_provider_id, "expected_custody_provider_id")
    verifier = _text(expected_verifier_id, "expected_verifier_id")
    verifier_key = _text(expected_verifier_key_id, "expected_verifier_key_id")
    origin = _text(expected_origin, "expected_origin")
    rp_id = _text(expected_rp_id, "expected_rp_id")
    if isinstance(expected_key_epoch, bool) or not isinstance(expected_key_epoch, int) or expected_key_epoch < 1:
        raise HumanAsymmetricCustodyError("expected_key_epoch_invalid")

    if assertion.get("challenge_id") != challenge.get("challenge_id") or assertion.get("challenge_sha256") != challenge_sha:
        raise HumanAsymmetricCustodyError("assertion_challenge_binding_mismatch")
    for field in ("case_id", "case_sha256", "packet_sha256", "twin_prediction_id", "session_id", "device_id", "custody_provider_id", "nonce"):
        if assertion.get(field) != challenge.get(field):
            raise HumanAsymmetricCustodyError(f"assertion_challenge_field_mismatch:{field}")
    if assertion.get("human_subject_id") != subject or challenge.get("human_subject_id") != subject:
        raise HumanAsymmetricCustodyError("human_subject_mismatch")
    if assertion.get("custody_provider_id") != provider:
        raise HumanAsymmetricCustodyError("custody_provider_mismatch")
    if assertion.get("verifier_id") != verifier or assertion.get("verifier_key_id") != verifier_key:
        raise HumanAsymmetricCustodyError("verifier_policy_mismatch")
    if assertion.get("origin") != origin or assertion.get("rp_id") != rp_id:
        raise HumanAsymmetricCustodyError("origin_or_rp_id_mismatch")

    algorithm = _text(assertion.get("algorithm"), "assertion.algorithm").upper()
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise HumanAsymmetricCustodyError("assertion_algorithm_unsupported")
    credential_id = _sha(assertion.get("credential_id_sha256"), "assertion.credential_id_sha256")
    public_key_sha = _sha(assertion.get("public_key_sha256"), "assertion.public_key_sha256")
    signature_sha = _sha(assertion.get("signature_sha256"), "assertion.signature_sha256")
    key_epoch = assertion.get("key_epoch")
    if key_epoch != expected_key_epoch:
        raise HumanAsymmetricCustodyError("key_epoch_mismatch")

    entries = credential_registry.get("entries")
    if not isinstance(entries, (list, tuple)) or credential_registry.get("entry_count") != len(entries):
        raise HumanAsymmetricCustodyError("credential_registry_count_mismatch")
    matches = [entry for entry in entries if isinstance(entry, Mapping) and entry.get("credential_id_sha256") == credential_id]
    if len(matches) != 1:
        raise HumanAsymmetricCustodyError("credential_not_unique_or_missing")
    credential = matches[0]
    for field, expected in (
        ("human_subject_id", subject),
        ("device_id", challenge.get("device_id")),
        ("custody_provider_id", provider),
        ("public_key_sha256", public_key_sha),
        ("algorithm", algorithm),
        ("key_epoch", expected_key_epoch),
    ):
        if credential.get(field) != expected:
            raise HumanAsymmetricCustodyError(f"credential_binding_mismatch:{field}")
    if credential.get("status") != "ACTIVE" or credential.get("revoked_at") is not None:
        raise HumanAsymmetricCustodyError("credential_not_active")

    responded_text, responded_epoch = _iso(assertion.get("responded_at"), "assertion.responded_at")
    verified_text, verified_epoch = _iso(verified_at, "verified_at")
    issued_text, issued_epoch = _iso(challenge.get("issued_at"), "challenge.issued_at")
    _, challenge_expiry = _iso(challenge.get("expires_at"), "challenge.expires_at")
    not_before_text, not_before_epoch = _iso(credential.get("not_before"), "credential.not_before")
    not_after_text, not_after_epoch = _iso(credential.get("not_after"), "credential.not_after")
    if not (issued_epoch <= responded_epoch <= challenge_expiry and responded_epoch <= verified_epoch):
        raise HumanAsymmetricCustodyError("challenge_response_window_invalid")
    if not (not_before_epoch <= responded_epoch <= not_after_epoch):
        raise HumanAsymmetricCustodyError("credential_not_valid_at_response")

    epoch_number = nonce_registry.get("epoch_number")
    if isinstance(epoch_number, bool) or not isinstance(epoch_number, int) or epoch_number < 1:
        raise HumanAsymmetricCustodyError("nonce_epoch_number_invalid")
    _, epoch_start = _iso(nonce_registry.get("epoch_started_at"), "nonce_registry.epoch_started_at")
    _, epoch_expiry = _iso(nonce_registry.get("epoch_expires_at"), "nonce_registry.epoch_expires_at")
    if not (epoch_start <= issued_epoch <= responded_epoch <= epoch_expiry):
        raise HumanAsymmetricCustodyError("challenge_outside_nonce_epoch")
    if nonce_registry.get("cumulative_history") is not True:
        raise HumanAsymmetricCustodyError("nonce_registry_must_be_cumulative")
    nonce_sha = sha256_text(_text(challenge.get("nonce"), "challenge.nonce"))
    used_nonces = tuple(nonce_registry.get("used_nonce_sha256s") or ())
    used_challenges = tuple(nonce_registry.get("used_challenge_ids") or ())
    if nonce_sha in used_nonces:
        raise HumanAsymmetricCustodyError("nonce_replay_detected")
    if challenge.get("challenge_id") in used_challenges:
        raise HumanAsymmetricCustodyError("challenge_replay_detected")

    if assertion.get("signature_verified") is not True:
        raise HumanAsymmetricCustodyError("asymmetric_signature_not_verified")
    if assertion.get("external_asymmetric_verifier_assertion") is not True:
        raise HumanAsymmetricCustodyError("external_asymmetric_verifier_assertion_missing")
    if assertion.get("local_signature_math_verified") is not False:
        raise HumanAsymmetricCustodyError("local_signature_math_overclaim")
    if assertion.get("user_present") is not True or assertion.get("user_verified") is not True:
        raise HumanAsymmetricCustodyError("authenticator_user_presence_or_verification_missing")
    if assertion.get("physical_human_presence_proven") is not False:
        raise HumanAsymmetricCustodyError("physical_human_presence_overclaim")
    if assertion.get("execution_authority") != "NONE" or assertion.get("can_execute") is not False:
        raise HumanAsymmetricCustodyError("assertion_authority_breached")

    choice = _text(assertion.get("actual_choice"), "assertion.actual_choice").upper()
    if choice not in _options(challenge.get("options", ())):
        raise HumanAsymmetricCustodyError("assertion_choice_outside_options")

    counter_supported = credential.get("counter_supported") is True
    if assertion.get("counter_supported") is not counter_supported:
        raise HumanAsymmetricCustodyError("counter_support_mismatch")
    prior_count = credential.get("sign_count")
    assertion_before = assertion.get("sign_count_before")
    assertion_after = assertion.get("sign_count_after")
    if counter_supported:
        if assertion_before != prior_count:
            raise HumanAsymmetricCustodyError("sign_count_prior_mismatch")
        if isinstance(assertion_after, bool) or not isinstance(assertion_after, int) or assertion_after <= assertion_before:
            raise HumanAsymmetricCustodyError("sign_count_not_monotonic")
    else:
        if assertion_before is not None or assertion_after is not None:
            raise HumanAsymmetricCustodyError("unsupported_counter_must_not_claim_counts")

    next_nonce_body = {k: v for k, v in nonce_registry.items() if k != "registry_sha256"}
    next_nonce_body["used_nonce_sha256s"] = tuple([*used_nonces, nonce_sha])
    next_nonce_body["used_challenge_ids"] = tuple([*used_challenges, challenge["challenge_id"]])
    next_nonce_registry = dict(next_nonce_body)
    next_nonce_registry["registry_sha256"] = sha256_obj(next_nonce_registry)

    next_credential_entries = []
    for entry in entries:
        row = dict(entry)
        if row.get("credential_id_sha256") == credential_id and counter_supported:
            row["sign_count"] = assertion_after
        next_credential_entries.append(row)
    next_credential_body = {k: v for k, v in credential_registry.items() if k not in {"entries", "entry_count", "registry_sha256"}}
    next_credential_body["entries"] = tuple(next_credential_entries)
    next_credential_body["entry_count"] = len(next_credential_entries)
    next_credential_registry = dict(next_credential_body)
    next_credential_registry["registry_sha256"] = sha256_obj(next_credential_registry)

    reveal_intent_sha = derive_reveal_intent_sha256(
        case_id=challenge["case_id"],
        case_sha256=challenge["case_sha256"],
        packet_sha256=challenge["packet_sha256"],
        twin_prediction_id=challenge["twin_prediction_id"],
        actual_choice=choice,
        responded_at=responded_text,
    )

    body = {
        "schema": ASYMMETRIC_VERIFICATION_SCHEMA,
        "challenge_id": challenge["challenge_id"],
        "challenge_sha256": challenge_sha,
        "case_id": challenge["case_id"],
        "case_sha256": challenge["case_sha256"],
        "packet_sha256": challenge["packet_sha256"],
        "twin_prediction_id": challenge["twin_prediction_id"],
        "human_subject_id": subject,
        "session_id": challenge["session_id"],
        "device_id": challenge["device_id"],
        "custody_provider_id": provider,
        "credential_id_sha256": credential_id,
        "public_key_sha256": public_key_sha,
        "algorithm": algorithm,
        "key_epoch": expected_key_epoch,
        "signature_sha256": signature_sha,
        "verifier_id": verifier,
        "verifier_key_id": verifier_key,
        "origin": origin,
        "rp_id": rp_id,
        "actual_choice": choice,
        "responded_at": responded_text,
        "verified_at": verified_text,
        "approved_reveal_intent_sha256": reveal_intent_sha,
        "signature_verified_by_external_asymmetric_verifier": True,
        "local_signature_math_verified": False,
        "user_present": True,
        "user_verified": True,
        "physical_human_presence_proven": False,
        "credential_status_verified": True,
        "credential_epoch_verified": True,
        "credential_counter_verified": counter_supported,
        "nonce_unused_in_expected_cumulative_registry": True,
        "challenge_unused_in_expected_cumulative_registry": True,
        "nonce_epoch_verified": True,
        "prior_credential_registry_sha256": credential_registry_sha,
        "next_credential_registry_candidate": next_credential_registry,
        "next_credential_registry_candidate_sha256": next_credential_registry["registry_sha256"],
        "prior_nonce_registry_sha256": nonce_registry_sha,
        "next_nonce_registry_candidate": next_nonce_registry,
        "next_nonce_registry_candidate_sha256": next_nonce_registry["registry_sha256"],
        "registry_write_performed": False,
        "approval_scope": "HUMAN_REVEAL_ONLY",
        "status": "ASYMMETRIC_HUMAN_APPROVAL_VERIFIED_SHADOW_ONLY",
        "human_identity_scope": "CREDENTIAL_SUBJECT_ASSERTION_ONLY",
        "cryptographic_property": "EXTERNAL_ASYMMETRIC_SIGNATURE_VERIFIER_ASSERTION",
        "execution_authority": "NONE",
        "can_execute": False,
        "apply_allowed": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["asymmetric_approval_verification_sha256"] = sha256_obj(body)
    return body
