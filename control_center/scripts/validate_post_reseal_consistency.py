from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from current_authority_anchor import append_anchor_errors, canonical_authority_anchor, canonical_roots, load_provider_snapshot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

PRE_RESEAL_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
PRE_REPAIR_CURRENT_STATE_SHA = "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd"

ANCHOR_DOCUMENTS = {
    "agent_control": "agent_control_plane.generated.v1.json",
    "work_lifecycle": "work_order_lifecycle.generated.v1.json",
    "decision_ledger": "decision_effect_ledger.generated.v1.json",
    "effect_readback": "effect_readback_plane.generated.v1.json",
    "command_queue": "command_queue.generated.v1.json",
    "human_gate": "human_gate_packets.generated.v1.json",
    "execution_scope_source": "execution_scope_sources.current.v1.json",
    "execution_scope": "execution_scope_binder.generated.v1.json",
    "broker_health_source": "broker_health_sources.current.v1.json",
    "broker_health": "broker_health_readback.generated.v1.json",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_documents() -> dict[str, dict[str, Any]]:
    docs = {name: load(DATA / filename) for name, filename in ANCHOR_DOCUMENTS.items()}
    docs["current_projection"] = load(DATA / "current_control_plane.generated.v1.json")
    return docs


def validate(
    snapshot: dict[str, Any] | None = None,
    documents: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    provider = snapshot or load_provider_snapshot()
    roots = canonical_roots(provider)
    expected_anchor = canonical_authority_anchor(provider)
    docs = deepcopy(documents) if documents is not None else load_documents()

    current = docs["current_projection"].get("canonical_current", {})
    pointer = current.get("pointer", {})
    root_hashes = current.get("root_hashes", {})
    if current.get("generation") != roots["generation"] or current.get("status") != roots["status"]:
        errors.append("current_projection_generation_status_mismatch")
    if current.get("canonical_decision") != roots["decision"]:
        errors.append("current_projection_decision_mismatch")
    if current.get("accepted_manifest_sha256") != roots["manifest_sha256"]:
        errors.append("current_projection_manifest_mismatch")
    if pointer.get("drive_file_id") != roots["pointer_drive_file_id"] or pointer.get("sha256") != roots["pointer_sha256"] or pointer.get("provider_readback") != "all_exact":
        errors.append("current_projection_pointer_mismatch")
    for filename, canonical_key in {
        "CURRENT_STATE.json": "current_state_sha256",
        "ROLE_INDEX.json": "role_index_sha256",
        "ROLE_VIEWS.json": "role_views_sha256",
    }.items():
        if root_hashes.get(filename) != roots[canonical_key]:
            errors.append(f"current_projection_root_mismatch:{filename}")

    for name in ANCHOR_DOCUMENTS:
        append_anchor_errors(name, docs[name].get("authority_anchor", {}), errors, provider)

    execution_source = docs["execution_scope_source"]
    if execution_source.get("canonical_current_state", {}).get("sha256") != roots["current_state_sha256"]:
        errors.append("execution_scope_current_state_mismatch")
    if execution_source.get("canonical_role_views", {}).get("sha256") != roots["role_views_sha256"]:
        errors.append("execution_scope_role_views_mismatch")
    if any(x.get("status") == "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE" for x in execution_source.get("known_divergences", [])):
        errors.append("execution_scope_open_contract_divergence")
    if not any(x.get("status") == "RESOLVED_CANONICAL_TEXT_MATCHES_VERIFIED_IMPLEMENTATION" for x in execution_source.get("known_divergences", [])):
        errors.append("execution_scope_contract_resolution_missing")

    health_source = docs["broker_health_source"]
    health_anchor = health_source.get("authority_anchor", {})
    if health_anchor.get("current_state_sha256") != roots["current_state_sha256"]:
        errors.append("broker_health_current_state_mismatch")
    if health_anchor.get("role_views_sha256") != roots["role_views_sha256"]:
        errors.append("broker_health_role_views_mismatch")
    if health_source.get("contract_divergence", {}).get("status") != "RESOLVED_BY_CANONICAL_REPAIR_AND_RESEAL":
        errors.append("broker_health_contract_resolution_missing")

    current_rule = str(current.get("generation") and docs["current_projection"].get("return_plane", {}).get("canonical_runtime", {}).get("registry_mutation_rule", ""))
    if "generation-scoped return-broker state" not in current_rule or "does not directly mutate CURRENT_RETURN_REGISTRY.json" not in current_rule:
        errors.append("current_broker_rule_not_repaired")

    for name in ("execution_scope_source", "execution_scope", "broker_health_source", "broker_health"):
        serialized = json.dumps(docs[name], sort_keys=True)
        if PRE_RESEAL_POINTER_SHA in serialized:
            errors.append(f"pre_reseal_pointer_leak:{name}")
        if PRE_REPAIR_CURRENT_STATE_SHA in serialized:
            errors.append(f"pre_repair_state_leak:{name}")

    if docs["command_queue"].get("summary", {}).get("human_now") != 0:
        errors.append("human_now_not_zero")
    if docs["human_gate"].get("summary", {}).get("packets_total") != 0:
        errors.append("human_gate_packets_not_zero")
    if docs["effect_readback"].get("summary", {}).get("effect_candidates_total") != 0:
        errors.append("effect_candidates_not_zero")
    if docs["execution_scope"].get("binding", {}).get("execution_authorized") is not False or docs["execution_scope"].get("binding", {}).get("execution_ready") is not False:
        errors.append("execution_scope_authority_leak")
    health_policy = docs["broker_health"].get("policy", {})
    for key in ("health_projection_grants_authority", "process_restart_authorized", "root_repair_authorized", "registry_mutation_authorized", "execution_authorized", "self_application"):
        if health_policy.get(key) is not False:
            errors.append(f"broker_health_authority_leak:{key}")
    if health_policy.get("can_trade") is not False or health_policy.get("capital_permission") != "DENY" or health_policy.get("deploy_permission") != "DENY":
        errors.append("broker_health_safety_ceiling_mismatch")

    for name in ANCHOR_DOCUMENTS:
        anchor = docs[name].get("authority_anchor", {})
        for key, value in expected_anchor.items():
            if anchor.get(key) != value:
                # append_anchor_errors already records exact detail; this marker keeps the
                # end-to-end invariant visible as one aggregate failure class.
                errors.append(f"cross_layer_anchor_divergence:{name}:{key}")

    return errors


def main() -> int:
    try:
        errors = validate()
    except ValueError as exc:
        errors = str(exc).split(";")
    print(json.dumps({
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "guard": "POST_RESEAL_CONSISTENCY_V1",
        "anchor": canonical_authority_anchor(),
    }, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
