from __future__ import annotations

import copy
from typing import Any, Mapping

from hanri.attention_governor import canonical_sha256
import hanri.continuous_attention_loop as _v1

POLICY_VERSION = "39.3.1-continuous-attention-loop-v2"
BASE_POLICY_VERSION = _v1.POLICY_VERSION
EVIDENCE_HASH_ALGORITHM = "SEMANTIC_ENVELOPE_V2"


def _without_hash(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {k: copy.deepcopy(v) for k, v in payload.items() if k != key}


def _verify_v2_state(prior_state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not prior_state:
        return None
    state = copy.deepcopy(dict(prior_state))
    if str(state.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(
            f"legacy_or_foreign_state_requires_migration expected={POLICY_VERSION} "
            f"actual={state.get('policy_version')}"
        )
    if str(state.get("evidence_hash_algorithm", "")) != EVIDENCE_HASH_ALGORITHM:
        raise ValueError("prior state evidence_hash_algorithm mismatch")
    expected = canonical_sha256(_without_hash(state, "state_sha256"))
    if str(state.get("state_sha256", "")) != expected:
        raise ValueError("prior state SHA mismatch")
    return state


def _to_v1_state(state: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if state is None:
        return None
    converted = copy.deepcopy(dict(state))
    converted["policy_version"] = BASE_POLICY_VERSION
    converted.pop("evidence_hash_algorithm", None)
    converted.pop("migration_note", None)
    converted["state_sha256"] = canonical_sha256(
        {k: v for k, v in converted.items() if k != "state_sha256"}
    )
    return converted


def _to_v1_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    converted = copy.deepcopy(dict(policy))
    if str(converted.get("policy_version", "")) != POLICY_VERSION:
        raise ValueError(f"expected policy_version={POLICY_VERSION}")
    converted["policy_version"] = BASE_POLICY_VERSION
    return converted


def advance_continuous_attention_loop_v2(
    *,
    producer_bundle: Mapping[str, Any],
    fabric_result: Mapping[str, Any],
    prior_state: Mapping[str, Any] | None,
    policy: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if str(fabric_result.get("envelope_hash_algorithm", "")) != EVIDENCE_HASH_ALGORITHM:
        raise ValueError("fabric semantic envelope hash algorithm required")

    prior_v2 = _verify_v2_state(prior_state)
    base = _v1.advance_continuous_attention_loop(
        producer_bundle=producer_bundle,
        fabric_result=fabric_result,
        prior_state=_to_v1_state(prior_v2),
        policy=_to_v1_policy(policy),
        generated_at=generated_at,
    )

    state = copy.deepcopy(base["state"])
    state["policy_version"] = POLICY_VERSION
    state["evidence_hash_algorithm"] = EVIDENCE_HASH_ALGORITHM
    state["migration_note"] = (
        "R39.3.0 volatile-observed_at lineage is not continued; "
        "legacy state requires explicit archival/reset."
    )
    state["state_sha256"] = canonical_sha256(
        {k: v for k, v in state.items() if k != "state_sha256"}
    )

    receipt = copy.deepcopy(base["receipt"])
    receipt["policy_version"] = POLICY_VERSION
    receipt["evidence_hash_algorithm"] = EVIDENCE_HASH_ALGORITHM
    receipt["state_sha256"] = state["state_sha256"]
    receipt["receipt_sha256"] = canonical_sha256(
        {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    )
    return {"state": state, "receipt": receipt}


__all__ = [
    "POLICY_VERSION",
    "BASE_POLICY_VERSION",
    "EVIDENCE_HASH_ALGORITHM",
    "advance_continuous_attention_loop_v2",
]
