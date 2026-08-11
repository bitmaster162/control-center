from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_SCHEMA = "control_center.source_envelope.v1"
EXPECTED_REGISTRY_SCHEMA = "CONTROL_RETURN_REGISTRY_V4"
EXPECTED_REGISTRY_ID = "CONTROL_CANTER_RETURN_REGISTRY"
EXPECTED_STABLE_FILE_ID = "1BXdqWzA74SvkgcygO_ktO_2uolqFshWm"


def _load_bytes(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("registry_root_must_be_object")
    return raw, payload


def validate_registry(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != EXPECTED_REGISTRY_SCHEMA:
        errors.append(f"schema_mismatch:{payload.get('schema')}")
    if payload.get("registry_id") != EXPECTED_REGISTRY_ID:
        errors.append(f"registry_id_mismatch:{payload.get('registry_id')}")
    if payload.get("stable_drive_file_id") != EXPECTED_STABLE_FILE_ID:
        errors.append(f"stable_file_id_mismatch:{payload.get('stable_drive_file_id')}")
    if not isinstance(payload.get("slots"), dict):
        errors.append("slots_must_be_object")

    rules = payload.get("rules")
    if not isinstance(rules, dict):
        errors.append("rules_must_be_object")
    else:
        if rules.get("read_registry_before_drive_search") is not True:
            errors.append("read_registry_before_drive_search_must_be_true")
        if rules.get("rerun_completed_work") is not False:
            errors.append("rerun_completed_work_must_be_false")
        if rules.get("source_mutation") is not False:
            errors.append("source_mutation_must_be_false")
        if rules.get("can_trade") is not False:
            errors.append("can_trade_must_be_false")
        if rules.get("capital_permission") != "DENY":
            errors.append("capital_permission_must_be_DENY")

    return errors


def _slot_observation(slot: str, row: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    artifact_sha = row.get("zip_sha256") or row.get("result_zip_sha256")
    return {
        "slot": slot,
        "registered": True,
        "reported_state": row.get("state"),
        "work_order": row.get("work_order"),
        "project": row.get("project"),
        "artifact_sha256": artifact_sha,
        "registry_generation_label": registry.get("generation"),
        "registry_last_updated_utc": registry.get("last_updated_utc") or registry.get("updated_at_utc"),
        "semantic_interpretation": "NONE_TRANSPORT_REGISTRY_OBSERVATION_ONLY",
    }


def adapt(path: Path, *, observed_at: str, freshness: str) -> dict[str, Any]:
    if freshness not in {"CURRENT", "STALE"}:
        raise ValueError("freshness_must_be_CURRENT_or_STALE")
    if not observed_at:
        raise ValueError("observed_at_required")

    raw, registry = _load_bytes(path)
    errors = validate_registry(registry)
    if errors:
        raise ValueError(";".join(errors))

    raw_sha256 = hashlib.sha256(raw).hexdigest()
    claims: list[dict[str, Any]] = [
        {
            "claim_key": "return_registry.metadata",
            "claim_class": "RETURN_TRANSPORT",
            "value": {
                "schema": registry.get("schema"),
                "registry_id": registry.get("registry_id"),
                "stable_drive_file_id": registry.get("stable_drive_file_id"),
                "registry_generation_label": registry.get("generation"),
                "updated_at_utc": registry.get("updated_at_utc"),
                "last_updated_utc": registry.get("last_updated_utc"),
                "actual_file_sha256": raw_sha256,
                "declared_registry_content_sha256": registry.get("registry_content_sha256"),
                "semantic_interpretation": "NONE_TRANSPORT_REGISTRY_OBSERVATION_ONLY",
            },
            "evidence_state": "HASH_VERIFIED",
        }
    ]

    for slot in sorted(registry["slots"]):
        row = registry["slots"][slot]
        if not isinstance(row, dict):
            raise ValueError(f"slot_not_object:{slot}")
        claims.append({
            "claim_key": f"return_registry.slot.{slot}.observation",
            "claim_class": "RETURN_TRANSPORT",
            "value": _slot_observation(slot, row, registry),
            "evidence_state": "RECEIPTED",
        })

    return {
        "schema": SOURCE_SCHEMA,
        "source_id": f"current-return-registry-v4:{raw_sha256[:16]}",
        "source_kind": "RETURN_BROKER",
        "observed_at": observed_at,
        "freshness": freshness,
        "precedence": 90,
        "claims": claims,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only adapter for exact CURRENT_RETURN_REGISTRY.json V4 bytes")
    parser.add_argument("registry", type=Path)
    parser.add_argument("--observed-at", required=True)
    parser.add_argument("--freshness", choices=["CURRENT", "STALE"], required=True)
    args = parser.parse_args()

    try:
        envelope = adapt(args.registry, observed_at=args.observed_at, freshness=args.freshness)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
