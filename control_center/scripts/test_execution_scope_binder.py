from __future__ import annotations

import copy
import json
from pathlib import Path

from build_execution_scope_binder import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def expect_fail(name: str, source, command, effect) -> None:
    try:
        build(source, command, effect)
    except ValueError:
        return
    raise AssertionError(f"expected_fail::{name}")


def main() -> int:
    source = load(DATA / "execution_scope_sources.current.v1.json")
    command = load(DATA / "command_queue.generated.v1.json")
    effect = load(DATA / "effect_readback_plane.generated.v1.json")
    out = build(source, command, effect)
    assert out["verdict"] == "NO_EXECUTABLE_GATE_RUNTIME_IDENTITY_VERIFIED_R43_HISTORICAL_RESEALED_ROOTS_ALIGNED"
    assert out["binding"]["historical_gate_suppressed"] is True
    assert out["binding"]["runtime_identity_bound"] is True
    assert out["binding"]["provider_target_bound"] is True
    assert out["binding"]["mutation_set_bound"] is True
    assert out["binding"]["execution_scope_bound"] is False
    assert out["binding"]["execution_ready"] is False
    assert out["binding"]["execution_authorized"] is False
    assert "CANONICAL_ROOT_MUTATION_CONTRACT_DIVERGENCE_UNRESOLVED" not in out["binding"]["blockers"]
    assert out["canonical_runtime"]["runtime_deployment_readback"] == "VERIFIED_DRIVE_RECEIPT"
    assert out["canonical_runtime"]["runtime_head"] == "f14ab9a8f4b7ba7b1cca80759f4683916b1dc785"
    assert out["canonical_runtime"]["runtime_tree"] == "4762b2cdad463823e34da29e09b22ec580c6e778"
    assert out["canonical_runtime"]["current_process_liveness"] == "NOT_DIRECTLY_VERIFIED_AT_BINDER_OBSERVED_AT"
    assert out["canonical_runtime"]["receipt_pids_are_not_current_process_proof"] is True
    assert out["implementation_binding"]["current_return_registry_reference_in_core"] is False
    assert out["implementation_binding"]["direct_current_return_registry_edit_observed"] is False
    assert out["invariants"]["cross_layer_anchor_equality_required"] is True
    assert out["invariants"]["canonical_contract_divergence_resolved"] is True

    bad = copy.deepcopy(source); bad["canonical_current_state"]["watcher_generation"] = "R43"
    expect_fail("canonical_generation_tamper", bad, command, effect)

    bad = copy.deepcopy(source); bad["authority_anchor"]["pointer_sha256"] = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
    expect_fail("pre_reseal_source_anchor", bad, command, effect)

    bad = copy.deepcopy(command); bad["authority_anchor"]["pointer_sha256"] = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
    expect_fail("cross_layer_command_anchor", source, bad, effect)

    bad = copy.deepcopy(effect); bad["authority_anchor"]["pointer_sha256"] = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
    expect_fail("cross_layer_effect_anchor", source, command, bad)

    bad = copy.deepcopy(command); bad["summary"]["human_now"] = 1
    expect_fail("stale_human_gate_reintroduced", source, bad, effect)

    bad = copy.deepcopy(effect); bad["summary"]["effect_candidates_total"] = 1
    expect_fail("fabricated_effect_candidate", source, command, bad)

    bad = copy.deepcopy(source); bad["safety"]["execution_authorized"] = True
    expect_fail("execution_authority_leak", bad, command, effect)

    bad = copy.deepcopy(source); bad["known_divergences"] = []
    expect_fail("resolution_history_suppressed", bad, command, effect)

    bad = copy.deepcopy(source); bad["known_divergences"][0]["status"] = "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE"
    expect_fail("stale_open_divergence_reintroduced", bad, command, effect)

    bad = copy.deepcopy(source); bad["provider_readback"]["runtime_receipt"]["accepted_head"] = "00" * 20
    expect_fail("runtime_head_tamper", bad, command, effect)

    bad = copy.deepcopy(source); bad["provider_readback"]["post_deploy_broker_activity"]["direct_current_return_registry_edit"] = True
    expect_fail("forged_current_registry_edit", bad, command, effect)

    bad = copy.deepcopy(source); bad["provider_readback"]["installed_implementation_semantics"]["current_return_registry_reference_in_core"] = True
    expect_fail("invented_current_registry_reference", bad, command, effect)

    bad = copy.deepcopy(source); bad["provider_readback"]["github_live"]["tree"] = "11" * 20
    expect_fail("github_tree_tamper", bad, command, effect)

    print(json.dumps({"status": "PASS", "verdict": out["verdict"], "adversarial_cases": 13}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
