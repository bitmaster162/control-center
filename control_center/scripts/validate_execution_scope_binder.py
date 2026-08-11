from __future__ import annotations

import json
from pathlib import Path

from build_execution_scope_binder import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> int:
    expected = build(load(DATA / "execution_scope_sources.current.v1.json"), load(DATA / "command_queue.generated.v1.json"), load(DATA / "effect_readback_plane.generated.v1.json"))
    actual = load(DATA / "execution_scope_binder.generated.v1.json")
    errors = []
    if actual != expected:
        errors.append("execution_scope_binder_semantic_mismatch")
    if actual.get("verdict") != "NO_EXECUTABLE_GATE_RUNTIME_IDENTITY_VERIFIED_R43_HISTORICAL":
        errors.append("verdict_mismatch")
    binding = actual.get("binding", {})
    if binding.get("historical_gate_suppressed") is not True or binding.get("current_human_gate_count") != 0 or binding.get("current_effect_candidate_count") != 0:
        errors.append("stale_gate_suppression_mismatch")
    if binding.get("runtime_identity_bound") is not True or binding.get("provider_target_bound") is not True or binding.get("mutation_set_bound") is not True:
        errors.append("verified_runtime_binding_missing")
    if binding.get("execution_scope_bound") is not False or binding.get("executor_bound") is not False or binding.get("execution_authorized") is not False or binding.get("execution_ready") is not False:
        errors.append("execution_authority_leak")
    runtime = actual.get("canonical_runtime", {})
    if runtime.get("broker_status") != "INSTALLED_AND_WATCHING" or runtime.get("watcher_generation") != "R59":
        errors.append("canonical_runtime_mismatch")
    if runtime.get("runtime_deployment_readback") != "VERIFIED_DRIVE_RECEIPT" or runtime.get("runtime_head") != "f14ab9a8f4b7ba7b1cca80759f4683916b1dc785" or runtime.get("runtime_tree") != "4762b2cdad463823e34da29e09b22ec580c6e778":
        errors.append("runtime_identity_readback_mismatch")
    if runtime.get("current_process_liveness") != "NOT_DIRECTLY_VERIFIED_AT_BINDER_OBSERVED_AT" or runtime.get("receipt_pids_are_not_current_process_proof") is not True:
        errors.append("fresh_process_liveness_boundary_missing")
    impl = actual.get("implementation_binding", {})
    if impl.get("current_return_registry_reference_in_core") is not False or impl.get("direct_current_return_registry_edit_observed") is not False:
        errors.append("current_registry_mutation_claim_mismatch")
    if not any(x.get("id") == "BROKER_REGISTRY_MUTATION_CONTRACT_DIVERGENCE_CONFIRMED" for x in actual.get("source_divergences", [])):
        errors.append("source_divergence_missing")
    if actual.get("next_read_only_action") != "READ_ONLY_CURRENT_PROCESS_LIVENESS_AND_R59_REGISTRY_HEALTH_CHECK":
        errors.append("next_read_only_action_mismatch")
    print(json.dumps({"status":"PASS" if not errors else "FAIL","errors":errors,"verdict":actual.get("verdict")}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
