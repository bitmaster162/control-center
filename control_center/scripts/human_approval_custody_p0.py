from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import json
from typing import Any, Mapping, Sequence

CHALLENGE_SCHEMA = "control_center.shadow_human_approval_challenge.v1"
ATTESTATION_SCHEMA = "control_center.shadow_human_custody_attestation.v1"
REGISTRY_SCHEMA = "control_center.shadow_human_approval_registry_snapshot.v1"
VERIFICATION_SCHEMA = "control_center.shadow_human_approval_verification.v1"

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
    "current_truth_apply": False,
    "decision_ledger_write": False,
    "command_queue_write": False,
    "runtime_activation": False,
    "executor_dispatch": False,
    "signal": False,
    "order": False,
    "capital_effect": False,
}


class HumanApprovalCustodyError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HumanApprovalCustodyError(f"{field}_required")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise HumanApprovalCustodyError(f"{field}_must_be_sha256")
    return text


def _iso(value: Any, field: str) -> tuple[str, float]:
    text = _text(value, field)
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise HumanApprovalCustodyError(f"{field}_must_be_iso8601") from exc
    if parsed.tzinfo is None:
        raise HumanApprovalCustodyError(f"{field}_timezone_required")
    return text, parsed.timestamp()


def _secret_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        secret = value
    elif isinstance(value, str):
        secret = value.encode("utf-8")
    else:
        raise HumanApprovalCustodyError("verifier_secret_required")
    if not secret:
        raise HumanApprovalCustodyError("verifier_secret_required")
    return secret


def _verify_safety(record: Mapping[str, Any], field: str) -> None:
    safety = record.get("safety") if isinstance(record, Mapping) else None
    if not isinstance(safety, Mapping):
        raise HumanApprovalCustodyError(f"{field}_safety_missing")
    for key, expected in REQUIRED_SAFETY.items():
        if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
            raise HumanApprovalCustodyError(f"unsafe_{field}:{key}")


def _verify_no_effects(record: Mapping[str, Any], field: str) -> None:
    effects = record.get("effects") if isinstance(record, Mapping) else None
    if not isinstance(effects, Mapping) or set(effects) != set(NO_EFFECTS):
        raise HumanApprovalCustodyError(f"{field}_effect_keys_mismatch")
    if any(value is not False for value in effects.values()):
        raise HumanApprovalCustodyError(f"{field}_effect_boundary_breached")


def _verify_hash(record: Mapping[str, Any], field: str, code: str) -> str:
    if not isinstance(record, Mapping):
        raise HumanApprovalCustodyError(code)
    supplied = _sha(record.get(field), field)
    expected = sha256_obj({k: v for k, v in record.items() if k != field})
    if supplied != expected:
        raise HumanApprovalCustodyError(code)
    return supplied


def _options(value: Sequence[str]) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise HumanApprovalCustodyError("options_must_be_sequence")
    clean = tuple(dict.fromkeys(_text(item, "option").upper() for item in value))
    if len(clean) < 2 or "WAIT" not in clean:
        raise HumanApprovalCustodyError("options_must_include_wait_and_alternative")
    return clean


def build_human_approval_challenge(
    *,
    case_id: str,
    case_sha256: str,
    packet_sha256: str,
    twin_prediction_id: str,
    options: Sequence[str],
    human_subject_id: str,
    session_id: str,
    device_id: str,
    custody_provider_id: str,
    nonce: str,
    issued_at: str,
    expires_at: str,
) -> dict[str, Any]:
    issued_text, issued_epoch = _iso(issued_at, "issued_at")
    expires_text, expires_epoch = _iso(expires_at, "expires_at")
    if expires_epoch <= issued_epoch:
        raise HumanApprovalCustodyError("challenge_expiry_must_follow_issue")
    body = {
        "schema": CHALLENGE_SCHEMA,
        "case_id": _text(case_id, "case_id"),
        "case_sha256": _sha(case_sha256, "case_sha256"),
        "packet_sha256": _sha(packet_sha256, "packet_sha256"),
        "twin_prediction_id": _sha(twin_prediction_id, "twin_prediction_id"),
        "options": _options(options),
        "human_subject_id": _text(human_subject_id, "human_subject_id"),
        "session_id": _text(session_id, "session_id"),
        "device_id": _text(device_id, "device_id"),
        "custody_provider_id": _text(custody_provider_id, "custody_provider_id"),
        "nonce": _text(nonce, "nonce"),
        "issued_at": issued_text,
        "expires_at": expires_text,
        "purpose": "HUMAN_REVEAL_ONLY",
        "does_not_authorize_execution": True,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["challenge_id"] = sha256_obj(
        {
            "case_id": body["case_id"],
            "case_sha256": body["case_sha256"],
            "packet_sha256": body["packet_sha256"],
            "twin_prediction_id": body["twin_prediction_id"],
            "human_subject_id": body["human_subject_id"],
            "session_id": body["session_id"],
            "device_id": body["device_id"],
            "custody_provider_id": body["custody_provider_id"],
            "nonce": body["nonce"],
            "issued_at": body["issued_at"],
            "expires_at": body["expires_at"],
        }
    )
    body["challenge_sha256"] = sha256_obj(body)
    return body


def build_human_approval_registry_snapshot(
    *,
    registry_id: str,
    authority_root_sha256: str,
    entries: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise HumanApprovalCustodyError("registry_entries_must_be_sequence")
    normalized = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HumanApprovalCustodyError("registry_entry_must_be_object")
        challenge_id = _sha(entry.get("challenge_id"), "registry.challenge_id")
        if challenge_id in seen:
            raise HumanApprovalCustodyError("registry_duplicate_challenge_id")
        seen.add(challenge_id)
        normalized.append(
            {
                "challenge_id": challenge_id,
                "challenge_sha256": _sha(entry.get("challenge_sha256"), "registry.challenge_sha256"),
                "attestation_sha256": _sha(entry.get("attestation_sha256"), "registry.attestation_sha256"),
            }
        )
    body = {
        "schema": REGISTRY_SCHEMA,
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


def _attestation_mac_payload(attestation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(attestation, Mapping):
        raise HumanApprovalCustodyError("attestation_must_be_object")
    return {k: v for k, v in attestation.items() if k not in {"attestation_mac", "attestation_sha256"}}


def compute_custody_attestation_mac(attestation: Mapping[str, Any], verifier_secret: Any) -> str:
    """Return HMAC for an external custody attestation; production verifier keys must remain out-of-band."""
    payload = canonical_json(_attestation_mac_payload(attestation)).encode("utf-8")
    return hmac.new(_secret_bytes(verifier_secret), payload, hashlib.sha256).hexdigest()


def _verify_challenge(challenge: Mapping[str, Any]) -> str:
    if not isinstance(challenge, Mapping) or challenge.get("schema") != CHALLENGE_SCHEMA:
        raise HumanApprovalCustodyError("challenge_schema_mismatch")
    challenge_sha = _verify_hash(challenge, "challenge_sha256", "challenge_hash_mismatch")
    _verify_safety(challenge, "challenge")
    _verify_no_effects(challenge, "challenge")
    if challenge.get("purpose") != "HUMAN_REVEAL_ONLY" or challenge.get("does_not_authorize_execution") is not True:
        raise HumanApprovalCustodyError("challenge_scope_invalid")
    if challenge.get("execution_authority") != "NONE" or challenge.get("can_execute") is not False:
        raise HumanApprovalCustodyError("challenge_authority_breached")
    _sha(challenge.get("case_sha256"), "challenge.case_sha256")
    _sha(challenge.get("packet_sha256"), "challenge.packet_sha256")
    _sha(challenge.get("twin_prediction_id"), "challenge.twin_prediction_id")
    _options(challenge.get("options", ()))
    issued_text, issued_epoch = _iso(challenge.get("issued_at"), "challenge.issued_at")
    expires_text, expires_epoch = _iso(challenge.get("expires_at"), "challenge.expires_at")
    if expires_epoch <= issued_epoch:
        raise HumanApprovalCustodyError("challenge_expiry_invalid")
    expected_id = sha256_obj(
        {
            "case_id": _text(challenge.get("case_id"), "challenge.case_id"),
            "case_sha256": challenge["case_sha256"],
            "packet_sha256": challenge["packet_sha256"],
            "twin_prediction_id": challenge["twin_prediction_id"],
            "human_subject_id": _text(challenge.get("human_subject_id"), "challenge.human_subject_id"),
            "session_id": _text(challenge.get("session_id"), "challenge.session_id"),
            "device_id": _text(challenge.get("device_id"), "challenge.device_id"),
            "custody_provider_id": _text(challenge.get("custody_provider_id"), "challenge.custody_provider_id"),
            "nonce": _text(challenge.get("nonce"), "challenge.nonce"),
            "issued_at": issued_text,
            "expires_at": expires_text,
        }
    )
    if challenge.get("challenge_id") != expected_id:
        raise HumanApprovalCustodyError("challenge_id_binding_mismatch")
    return challenge_sha


def _verify_registry(
    registry: Mapping[str, Any],
    *,
    expected_registry_sha256: str,
    expected_authority_root_sha256: str,
) -> str:
    if not isinstance(registry, Mapping) or registry.get("schema") != REGISTRY_SCHEMA:
        raise HumanApprovalCustodyError("registry_schema_mismatch")
    registry_sha = _verify_hash(registry, "registry_sha256", "registry_hash_mismatch")
    if registry_sha != _sha(expected_registry_sha256, "expected_registry_sha256"):
        raise HumanApprovalCustodyError("registry_external_digest_mismatch")
    if registry.get("authority_root_sha256") != _sha(expected_authority_root_sha256, "expected_authority_root_sha256"):
        raise HumanApprovalCustodyError("registry_authority_root_mismatch")
    _verify_safety(registry, "registry")
    _verify_no_effects(registry, "registry")
    if registry.get("write_allowed") is not False or registry.get("apply_allowed") is not False:
        raise HumanApprovalCustodyError("registry_effect_boundary_breached")
    if registry.get("execution_authority") != "NONE":
        raise HumanApprovalCustodyError("registry_authority_breached")
    entries = registry.get("entries")
    if not isinstance(entries, (list, tuple)) or registry.get("entry_count") != len(entries):
        raise HumanApprovalCustodyError("registry_entry_count_mismatch")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HumanApprovalCustodyError("registry_entry_invalid")
        challenge_id = _sha(entry.get("challenge_id"), "registry.challenge_id")
        _sha(entry.get("challenge_sha256"), "registry.challenge_sha256")
        _sha(entry.get("attestation_sha256"), "registry.attestation_sha256")
        if challenge_id in seen:
            raise HumanApprovalCustodyError("registry_duplicate_challenge_id")
        seen.add(challenge_id)
    return registry_sha


def verify_human_custody_approval(
    challenge: Mapping[str, Any],
    attestation: Mapping[str, Any],
    registry_snapshot: Mapping[str, Any],
    *,
    expected_registry_sha256: str,
    expected_authority_root_sha256: str,
    expected_human_subject_id: str,
    expected_verifier_id: str,
    expected_verifier_key_id: str,
    verifier_secret: Any,
    verified_at: str,
) -> dict[str, Any]:
    challenge_sha = _verify_challenge(challenge)
    registry_sha = _verify_registry(
        registry_snapshot,
        expected_registry_sha256=expected_registry_sha256,
        expected_authority_root_sha256=expected_authority_root_sha256,
    )
    if challenge["challenge_id"] in {entry["challenge_id"] for entry in registry_snapshot["entries"]}:
        raise HumanApprovalCustodyError("challenge_replay_detected")

    if not isinstance(attestation, Mapping) or attestation.get("schema") != ATTESTATION_SCHEMA:
        raise HumanApprovalCustodyError("attestation_schema_mismatch")
    attestation_sha = _verify_hash(attestation, "attestation_sha256", "attestation_hash_mismatch")
    _verify_safety(attestation, "attestation")
    _verify_no_effects(attestation, "attestation")
    if attestation.get("proof_type") != "HMAC_SHA256_EXTERNAL_CUSTODY_V1":
        raise HumanApprovalCustodyError("attestation_proof_type_invalid")
    supplied_mac = _sha(attestation.get("attestation_mac"), "attestation_mac")
    expected_mac = compute_custody_attestation_mac(attestation, verifier_secret)
    if not hmac.compare_digest(supplied_mac, expected_mac):
        raise HumanApprovalCustodyError("attestation_mac_invalid")
    if attestation.get("challenge_sha256") != challenge_sha:
        raise HumanApprovalCustodyError("attestation_challenge_hash_mismatch")
    if attestation.get("challenge_id") != challenge["challenge_id"] or attestation.get("nonce") != challenge["nonce"]:
        raise HumanApprovalCustodyError("attestation_challenge_identity_mismatch")

    expected_subject = _text(expected_human_subject_id, "expected_human_subject_id")
    if challenge.get("human_subject_id") != expected_subject or attestation.get("human_subject_id") != expected_subject:
        raise HumanApprovalCustodyError("human_subject_mismatch")
    if attestation.get("session_id") != challenge["session_id"]:
        raise HumanApprovalCustodyError("session_custody_mismatch")
    if attestation.get("device_id") != challenge["device_id"]:
        raise HumanApprovalCustodyError("device_custody_mismatch")
    if attestation.get("custody_provider_id") != challenge["custody_provider_id"]:
        raise HumanApprovalCustodyError("custody_provider_mismatch")
    if attestation.get("verifier_id") != _text(expected_verifier_id, "expected_verifier_id"):
        raise HumanApprovalCustodyError("verifier_id_mismatch")
    if attestation.get("verifier_key_id") != _text(expected_verifier_key_id, "expected_verifier_key_id"):
        raise HumanApprovalCustodyError("verifier_key_id_mismatch")
    if attestation.get("physical_human_presence_proven") is not False:
        raise HumanApprovalCustodyError("physical_presence_overclaim")
    if attestation.get("execution_authority") != "NONE" or attestation.get("can_execute") is not False:
        raise HumanApprovalCustodyError("attestation_authority_breached")

    choice = _text(attestation.get("actual_choice"), "attestation.actual_choice").upper()
    if choice not in tuple(challenge["options"]):
        raise HumanApprovalCustodyError("attestation_choice_outside_options")
    responded_text, responded_epoch = _iso(attestation.get("responded_at"), "attestation.responded_at")
    _, issued_epoch = _iso(challenge["issued_at"], "challenge.issued_at")
    _, expires_epoch = _iso(challenge["expires_at"], "challenge.expires_at")
    if responded_epoch + 1e-6 < issued_epoch or responded_epoch - 1e-6 > expires_epoch:
        raise HumanApprovalCustodyError("attestation_response_outside_challenge_window")
    verified_text, verified_epoch = _iso(verified_at, "verified_at")
    if verified_epoch + 1e-6 < responded_epoch:
        raise HumanApprovalCustodyError("verification_precedes_response")

    reveal_intent_sha = derive_reveal_intent_sha256(
        case_id=challenge["case_id"],
        case_sha256=challenge["case_sha256"],
        packet_sha256=challenge["packet_sha256"],
        twin_prediction_id=challenge["twin_prediction_id"],
        actual_choice=choice,
        responded_at=responded_text,
    )
    next_registry = build_human_approval_registry_snapshot(
        registry_id=registry_snapshot["registry_id"],
        authority_root_sha256=registry_snapshot["authority_root_sha256"],
        entries=tuple(
            [
                *registry_snapshot["entries"],
                {
                    "challenge_id": challenge["challenge_id"],
                    "challenge_sha256": challenge_sha,
                    "attestation_sha256": attestation_sha,
                },
            ]
        ),
    )

    body = {
        "schema": VERIFICATION_SCHEMA,
        "case_id": challenge["case_id"],
        "case_sha256": challenge["case_sha256"],
        "packet_sha256": challenge["packet_sha256"],
        "twin_prediction_id": challenge["twin_prediction_id"],
        "challenge_id": challenge["challenge_id"],
        "challenge_sha256": challenge_sha,
        "attestation_sha256": attestation_sha,
        "prior_registry_sha256": registry_sha,
        "next_registry_candidate": next_registry,
        "next_registry_candidate_sha256": next_registry["registry_sha256"],
        "human_subject_id": expected_subject,
        "session_id": challenge["session_id"],
        "device_id": challenge["device_id"],
        "custody_provider_id": challenge["custody_provider_id"],
        "verifier_id": attestation["verifier_id"],
        "verifier_key_id": attestation["verifier_key_id"],
        "actual_choice": choice,
        "responded_at": responded_text,
        "verified_at": verified_text,
        "approved_reveal_intent_sha256": reveal_intent_sha,
        "custody_mac_verified": True,
        "challenge_window_verified": True,
        "challenge_unused_in_expected_registry": True,
        "single_use_status": "ADMITTABLE_UNUSED_CHALLENGE_SHADOW_ONLY",
        "human_identity_scope": "CUSTODY_PROVIDER_SUBJECT_ASSERTION_ONLY",
        "cryptographic_property": "HMAC_SHA256_VERIFIER_KEY_POSSESSION",
        "physical_human_presence_proven": False,
        "approval_scope": "HUMAN_REVEAL_ONLY",
        "status": "HUMAN_CUSTODY_APPROVAL_VERIFIED_SHADOW_ONLY",
        "registry_write_performed": False,
        "apply_allowed": False,
        "execution_authority": "NONE",
        "can_execute": False,
        "safety": dict(REQUIRED_SAFETY),
        "effects": dict(NO_EFFECTS),
    }
    body["approval_verification_sha256"] = sha256_obj(body)
    return body
