from __future__ import annotations

from copy import deepcopy

from current_authority_anchor import load_provider_snapshot
from validate_post_reseal_consistency import (
    PRE_REPAIR_CURRENT_STATE_SHA,
    PRE_RESEAL_POINTER_SHA,
    load_documents,
    validate,
)


def expect_marker(name: str, docs, marker: str, snapshot=None) -> None:
    errors = validate(snapshot=snapshot, documents=docs)
    if not any(marker in error for error in errors):
        raise AssertionError(f"{name}: expected {marker}, got {errors}")


def main() -> int:
    snapshot = load_provider_snapshot()
    docs = load_documents()
    baseline = validate(snapshot=snapshot, documents=docs)
    assert baseline == [], baseline

    bad = deepcopy(docs)
    bad["execution_scope_source"]["authority_anchor"]["pointer_sha256"] = PRE_RESEAL_POINTER_SHA
    expect_marker("old_execution_pointer", bad, "execution_scope_source_anchor_mismatch:pointer_sha256", snapshot)

    bad = deepcopy(docs)
    bad["broker_health_source"]["authority_anchor"]["current_state_sha256"] = PRE_REPAIR_CURRENT_STATE_SHA
    expect_marker("old_health_state", bad, "broker_health_current_state_mismatch", snapshot)

    bad = deepcopy(docs)
    bad["command_queue"]["authority_anchor"]["decision"] = "ACCEPT_R64_POINTER_PROMOTION"
    expect_marker("cross_layer_decision", bad, "command_queue_anchor_mismatch:decision", snapshot)

    bad = deepcopy(docs)
    bad["effect_readback"]["authority_anchor"]["pointer_sha256"] = PRE_RESEAL_POINTER_SHA
    expect_marker("cross_layer_effect_pointer", bad, "effect_readback_anchor_mismatch:pointer_sha256", snapshot)

    bad = deepcopy(docs)
    bad["execution_scope_source"]["known_divergences"][0]["status"] = "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE"
    expect_marker("open_divergence", bad, "execution_scope_open_contract_divergence", snapshot)

    bad = deepcopy(docs)
    bad["broker_health_source"]["contract_divergence"]["status"] = "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE"
    expect_marker("health_open_divergence", bad, "broker_health_contract_resolution_missing", snapshot)

    bad = deepcopy(docs)
    bad["current_projection"]["return_plane"]["canonical_runtime"]["registry_mutation_rule"] = "Only the broker mutates CURRENT_RETURN_REGISTRY.json."
    expect_marker("stale_broker_rule", bad, "current_broker_rule_not_repaired", snapshot)

    bad = deepcopy(docs)
    bad["effect_readback"]["summary"]["effect_candidates_total"] = 1
    expect_marker("effect_candidate", bad, "effect_candidates_not_zero", snapshot)

    bad = deepcopy(docs)
    bad["execution_scope"]["binding"]["execution_authorized"] = True
    expect_marker("execution_authority", bad, "execution_scope_authority_leak", snapshot)

    bad = deepcopy(docs)
    bad["broker_health"]["policy"]["root_repair_authorized"] = True
    expect_marker("root_repair_authority", bad, "broker_health_authority_leak:root_repair_authorized", snapshot)

    bad_snapshot = deepcopy(snapshot)
    bad_snapshot["canonical_roots"]["pointer_sha256"] = "11" * 32
    expect_marker("provider_anchor_change", deepcopy(docs), "anchor_mismatch:pointer_sha256", bad_snapshot)

    print("POST_RESEAL_CONSISTENCY_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
