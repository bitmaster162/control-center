from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

TRANSACTION_SCHEMA = "bitevo.unified_shadow_transaction.v2"
PROJECTION_SCHEMA = "control_center.unified_shadow_projection.v1"
EXPECTED_REGISTRY_COUNT = 63

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

REQUIRED_FALSE_EFFECTS = (
    "executor_enabled",
    "current_truth_apply",
    "continuity_write",
    "runtime_registration",
    "external_model_call",
    "exchange_call",
    "signal",
    "order",
    "credential_mutation",
    "merge",
    "deploy",
)


class ShadowProjectionError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hex64(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ShadowProjectionError(f"{field}_must_be_sha256")
    text = value.lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ShadowProjectionError(f"{field}_must_be_sha256")
    return text


def validate_unified_shadow_transaction(transaction: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(transaction, Mapping):
        return ["transaction_must_be_object"]
    if transaction.get("schema") != TRANSACTION_SCHEMA:
        errors.append("transaction_schema_mismatch")

    for field in (
        "trade_case_sha256",
        "decision_packet_sha256",
        "federation_sha256",
        "route_sha256",
        "control_plane_sha256",
    ):
        try:
            _hex64(transaction.get(field), field)
        except ShadowProjectionError as exc:
            errors.append(str(exc))

    try:
        tx_sha = _hex64(transaction.get("transaction_sha256"), "transaction_sha256")
        expected = sha256_obj({k: v for k, v in transaction.items() if k != "transaction_sha256"})
        if tx_sha != expected:
            errors.append("transaction_hash_mismatch")
    except ShadowProjectionError as exc:
        errors.append(str(exc))

    if transaction.get("registered_node_count") != EXPECTED_REGISTRY_COUNT:
        errors.append("registry_count_mismatch")

    safety = transaction.get("safety")
    if not isinstance(safety, Mapping):
        errors.append("safety_missing")
    else:
        for key, expected in REQUIRED_SAFETY.items():
            if safety.get(key) != expected or type(safety.get(key)) is not type(expected):
                errors.append(f"unsafe_transaction:{key}")

    effects = transaction.get("effect_boundary")
    if not isinstance(effects, Mapping):
        errors.append("effect_boundary_missing")
    else:
        for key in REQUIRED_FALSE_EFFECTS:
            if effects.get(key) is not False:
                errors.append(f"effect_boundary_not_false:{key}")

    gate = transaction.get("control_gate")
    action = transaction.get("control_plane_action")
    freshness = transaction.get("hanri_freshness")
    attention = transaction.get("hanri_attention_required")
    if gate not in {"PASS_SHADOW", "HOLD"}:
        errors.append("control_gate_invalid")
    if freshness not in {"FRESH", "STALE"}:
        errors.append("hanri_freshness_invalid")
    if not isinstance(attention, bool):
        errors.append("hanri_attention_not_bool")
    if gate == "HOLD" and action != "WAIT":
        errors.append("hold_must_force_wait")
    if freshness == "STALE":
        if gate != "HOLD":
            errors.append("stale_freshness_must_hold")
        if attention is not True:
            errors.append("stale_freshness_requires_attention")
    if attention is True and gate != "HOLD":
        errors.append("attention_requires_hold")

    return errors


def build_unified_shadow_projection(transaction: Mapping[str, Any]) -> dict[str, Any]:
    errors = validate_unified_shadow_transaction(transaction)
    if errors:
        raise ShadowProjectionError(";".join(errors))

    gate = str(transaction["control_gate"])
    freshness = str(transaction["hanri_freshness"])
    disposition = "HOLD_NO_APPLY" if gate == "HOLD" else "SHADOW_REVIEW_ONLY"

    body = {
        "schema": PROJECTION_SCHEMA,
        "projection_kind": "NON_AUTHORITY_SHADOW_PROJECTION",
        "source_transaction_sha256": transaction["transaction_sha256"],
        "case_id": transaction.get("case_id"),
        "registered_node_count": transaction["registered_node_count"],
        "authority_reference": dict(R64_AUTHORITY),
        "authority_freshness": {
            "provider_backed_status": freshness,
            "continuous_freshness_claimed": False,
            "attention_required": transaction["hanri_attention_required"],
        },
        "decision_view": {
            "system_recommendation": transaction.get("system_recommendation"),
            "control_gate": gate,
            "control_plane_action": transaction.get("control_plane_action"),
            "disposition": disposition,
        },
        "mutations": {
            "current_truth": False,
            "command_queue": False,
            "decision_ledger": False,
            "return_registry": False,
            "human_gate": False,
            "runtime": False,
            "trading": False,
            "capital": False,
        },
        "human_sovereign": True,
        "apply": False,
        "effect_candidates_created": 0,
        "executions_authorized": 0,
        "semantics": {
            "projection_is_not_current_truth": True,
            "provider_readback_is_not_authority": True,
            "stale_provider_evidence_cannot_be_promoted": True,
            "shadow_review_creates_no_effect_permission": True,
        },
        "safety": dict(REQUIRED_SAFETY),
    }
    body["projection_sha256"] = sha256_obj(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and project one BitEvo P0 unified shadow transaction without applying it.")
    parser.add_argument("transaction", type=Path)
    args = parser.parse_args()

    transaction = json.loads(args.transaction.read_text(encoding="utf-8"))
    try:
        projection = build_unified_shadow_projection(transaction)
    except ShadowProjectionError as exc:
        print(json.dumps({"status": "FAIL", "errors": str(exc).split(";")}, indent=2))
        return 2
    print(json.dumps({"status": "PASS", "projection": projection}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
