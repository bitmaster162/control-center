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
    if actual.get("verdict") != "NO_EXECUTABLE_GATE_STALE_R43_PREDECESSOR":
        errors.append("verdict_mismatch")
    binding = actual.get("binding", {})
    if binding.get("historical_gate_suppressed") is not True or binding.get("current_human_gate_count") != 0 or binding.get("current_effect_candidate_count") != 0:
        errors.append("stale_gate_suppression_mismatch")
    if any(binding.get(k) is not False for k in ("execution_scope_bound","provider_target_bound","mutation_set_bound","executor_bound","execution_authorized","execution_ready")):
        errors.append("scope_or_authority_leak")
    runtime = actual.get("canonical_runtime", {})
    if runtime.get("broker_status") != "INSTALLED_AND_WATCHING" or runtime.get("watcher_generation") != "R59":
        errors.append("canonical_runtime_mismatch")
    if runtime.get("runtime_liveness_current") != "UNVERIFIED_PROVIDER_READBACK_REQUIRED":
        errors.append("fresh_liveness_boundary_missing")
    if not any(x.get("id") == "BROKER_REGISTRY_MUTATION_SEMANTICS_DIVERGENCE" for x in actual.get("source_divergences", [])):
        errors.append("source_divergence_missing")
    if actual.get("next_read_only_action") != "READ_ONLY_CURRENT_BROKER_RUNTIME_AND_REPO_IDENTITY_READBACK":
        errors.append("next_read_only_action_mismatch")
    print(json.dumps({"status":"PASS" if not errors else "FAIL","errors":errors,"verdict":actual.get("verdict")}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
