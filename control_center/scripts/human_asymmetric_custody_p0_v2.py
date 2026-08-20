from __future__ import annotations

from typing import Any, Mapping

from control_center.scripts.human_asymmetric_custody_p0 import (
    ASYMMETRIC_ASSERTION_SCHEMA,
    ASYMMETRIC_VERIFICATION_SCHEMA,
    HumanAsymmetricCustodyError,
    sha256_obj,
    verify_asymmetric_human_approval,
)

ASYMMETRIC_VERIFICATION_SCHEMA_V2 = "control_center.shadow_asymmetric_human_approval_verification.v2"


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
        raise HumanAsymmetricCustodyError(f"{field}_must_be_sha256")
    return value.lower()


def _verify_external_assertion_digest(assertion: Mapping[str, Any], expected_assertion_sha256: str) -> str:
    if not isinstance(assertion, Mapping) or assertion.get("schema") != ASYMMETRIC_ASSERTION_SCHEMA:
        raise HumanAsymmetricCustodyError("assertion_schema_mismatch")
    supplied = _sha(assertion.get("assertion_sha256"), "assertion_sha256")
    computed = sha256_obj({k: v for k, v in assertion.items() if k != "assertion_sha256"})
    if supplied != computed:
        raise HumanAsymmetricCustodyError("assertion_hash_mismatch")
    if supplied != _sha(expected_assertion_sha256, "expected_assertion_sha256"):
        raise HumanAsymmetricCustodyError("assertion_external_digest_mismatch")
    return supplied


def verify_asymmetric_human_approval_v2(
    challenge: Mapping[str, Any],
    assertion: Mapping[str, Any],
    credential_registry: Mapping[str, Any],
    nonce_registry: Mapping[str, Any],
    *,
    expected_assertion_sha256: str,
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
    """R6.1 hardening: require the external asymmetric verifier assertion digest out-of-band.

    The v1 R6 verifier validated an assertion self-hash plus verifier-policy fields, but a party able to
    construct the entire assertion could also recompute that self-hash. V2 therefore requires an
    independently retained expected assertion digest before any semantic verification is accepted.
    """
    assertion_sha = _verify_external_assertion_digest(assertion, expected_assertion_sha256)

    v1 = verify_asymmetric_human_approval(
        challenge,
        assertion,
        credential_registry,
        nonce_registry,
        expected_credential_registry_sha256=expected_credential_registry_sha256,
        expected_nonce_registry_sha256=expected_nonce_registry_sha256,
        expected_authority_root_sha256=expected_authority_root_sha256,
        expected_human_subject_id=expected_human_subject_id,
        expected_custody_provider_id=expected_custody_provider_id,
        expected_verifier_id=expected_verifier_id,
        expected_verifier_key_id=expected_verifier_key_id,
        expected_origin=expected_origin,
        expected_rp_id=expected_rp_id,
        expected_key_epoch=expected_key_epoch,
        verified_at=verified_at,
    )
    if v1.get("schema") != ASYMMETRIC_VERIFICATION_SCHEMA:
        raise HumanAsymmetricCustodyError("prior_asymmetric_verification_schema_mismatch")
    prior_sha = _sha(v1.get("asymmetric_approval_verification_sha256"), "prior_asymmetric_approval_verification_sha256")
    if prior_sha != sha256_obj({k: v for k, v in v1.items() if k != "asymmetric_approval_verification_sha256"}):
        raise HumanAsymmetricCustodyError("prior_asymmetric_verification_hash_mismatch")

    body = {k: v for k, v in v1.items() if k not in {"schema", "asymmetric_approval_verification_sha256"}}
    body.update(
        {
            "schema": ASYMMETRIC_VERIFICATION_SCHEMA_V2,
            "prior_asymmetric_approval_verification_sha256": prior_sha,
            "external_assertion_sha256": assertion_sha,
            "external_assertion_digest_consumed": True,
            "external_asymmetric_verifier_evidence": "EXPECTED_DIGEST_BOUND",
            "trust_upgrade": "SELF_HASH_TO_INDEPENDENT_ASSERTION_DIGEST",
        }
    )
    body["asymmetric_approval_verification_sha256"] = sha256_obj(body)
    return body
