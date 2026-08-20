from __future__ import annotations

import json
from pathlib import Path

from build_broker_health_readback import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> int:
    expected = build(load(DATA / "broker_health_sources.current.v1.json"))
    actual = load(DATA / "broker_health_readback.generated.v1.json")
    errors: list[str] = []
    if actual != expected:
        errors.append("broker_health_semantic_mismatch")
    if actual.get("verdict") != "HEALTHY_PROVIDER_EVIDENCE_PROCESS_LIVENESS_NOT_OBSERVABLE_RESEALED_ROOTS_ALIGNED":
        errors.append("health_verdict_mismatch")
    registry = actual.get("registry_health", {})
    if registry.get("master_entries") != 9 or registry.get("live_index_entries") != 9 or registry.get("master_live_count_match") is not True:
        errors.append("registry_health_mismatch")
    if registry.get("historical_duplicate_groups") != 2 or registry.get("historical_excess_rows") != 4 or registry.get("post_df6_duplicate_regression_observed") is not False:
        errors.append("dedup_history_mismatch")
    if actual.get("controller_health", {}).get("readback_status") != "PASS_MATCH" or actual.get("controller_health", {}).get("ready_created_last") is not True:
        errors.append("controller_health_mismatch")
    if actual.get("stable_registry_health", {}).get("unchanged") is not True or actual.get("stable_registry_health", {}).get("direct_broker_mutation_observed") is not False:
        errors.append("stable_registry_health_mismatch")
    if actual.get("runtime", {}).get("process_liveness") != "NOT_PROVIDER_OBSERVABLE" or actual.get("runtime", {}).get("receipt_pids_are_current_proof") is not False:
        errors.append("process_liveness_boundary_mismatch")
    resolution = actual.get("contract_resolution", {})
    if resolution.get("status") != "RESOLVED_BY_CANONICAL_REPAIR_AND_RESEAL" or resolution.get("previous_status") != "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE":
        errors.append("contract_resolution_mismatch")
    if actual.get("human_gate_required_for_root_repair") != "NONE_REPAIR_ALREADY_APPLIED_AND_RESEALED":
        errors.append("stale_root_repair_gate")
    invariants = actual.get("invariants", {})
    if invariants.get("cross_layer_anchor_equality_required") is not True or invariants.get("canonical_contract_divergence_resolved") is not True:
        errors.append("post_reseal_consistency_invariant_missing")
    policy = actual.get("policy", {})
    if any(policy.get(k) is not False for k in ("health_projection_grants_authority", "process_restart_authorized", "root_repair_authorized", "registry_mutation_authorized", "execution_authorized", "self_application")):
        errors.append("authority_leak")
    if policy.get("can_trade") is not False or policy.get("capital_permission") != "DENY" or policy.get("deploy_permission") != "DENY":
        errors.append("safety_ceiling_mismatch")
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors, "verdict": actual.get("verdict")}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
