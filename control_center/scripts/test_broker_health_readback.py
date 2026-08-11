from __future__ import annotations

import copy
import json
from pathlib import Path

from build_broker_health_readback import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def expect_fail(name: str, source: dict) -> None:
    try:
        build(source)
    except ValueError:
        return
    raise AssertionError(f"expected_fail::{name}")


def main() -> int:
    source = load(DATA / "broker_health_sources.current.v1.json")
    one = build(source)
    two = build(copy.deepcopy(source))
    assert one == two
    assert one["verdict"] == "HEALTHY_PROVIDER_EVIDENCE_PROCESS_LIVENESS_NOT_OBSERVABLE_RESEALED_ROOTS_ALIGNED"
    assert one["registry_health"]["master_entries"] == 9
    assert one["registry_health"]["live_index_entries"] == 9
    assert one["registry_health"]["historical_duplicate_groups"] == 2
    assert one["registry_health"]["historical_excess_rows"] == 4
    assert one["registry_health"]["post_df6_duplicate_regression_observed"] is False
    assert one["stable_registry_health"]["unchanged"] is True
    assert one["runtime"]["process_liveness"] == "NOT_PROVIDER_OBSERVABLE"
    assert one["runtime"]["receipt_pids_are_current_proof"] is False
    assert one["contract_resolution"]["status"] == "RESOLVED_BY_CANONICAL_REPAIR_AND_RESEAL"
    assert one["human_gate_required_for_root_repair"] == "NONE_REPAIR_ALREADY_APPLIED_AND_RESEALED"
    assert one["invariants"]["cross_layer_anchor_equality_required"] is True

    bad = copy.deepcopy(source); bad["authority_anchor"]["pointer_sha256"] = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
    expect_fail("pre_reseal_pointer_anchor", bad)

    bad = copy.deepcopy(source); bad["authority_anchor"]["current_state_sha256"] = "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd"
    expect_fail("pre_repair_state_anchor", bad)

    bad = copy.deepcopy(source); bad["runtime"]["head"] = "00" * 20
    expect_fail("runtime_head_tamper", bad)

    bad = copy.deepcopy(source); bad["r59_generation"]["live_index"]["entry_count"] = 8
    expect_fail("master_live_count_divergence", bad)

    bad = copy.deepcopy(source); bad["r59_generation"]["master_registry"]["historical_duplicate_groups"] = 0
    expect_fail("historical_duplicates_erased", bad)

    bad = copy.deepcopy(source); bad["activity"]["post_df6_duplicate_regression_observed"] = True
    expect_fail("post_df6_duplicate_regression", bad)

    bad = copy.deepcopy(source); bad["stable_current_return_registry"]["sha256"] = "11" * 32
    expect_fail("stable_registry_sha_changed", bad)

    bad = copy.deepcopy(source); bad["stable_current_return_registry"]["direct_broker_mutation_observed"] = True
    expect_fail("direct_stable_registry_mutation", bad)

    bad = copy.deepcopy(source); bad["r59_generation"]["controller_readback"]["readback_status"] = "FAIL"
    expect_fail("controller_readback_failure", bad)

    bad = copy.deepcopy(source); bad["r59_generation"]["controller_ready"]["created_last"] = False
    expect_fail("ready_not_last", bad)

    bad = copy.deepcopy(source); bad["contract_divergence"]["status"] = "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE"
    expect_fail("open_contract_divergence_reintroduced", bad)

    bad = copy.deepcopy(source); bad["contract_divergence"]["canonical_root_sentence"] = "Only the broker mutates CURRENT_RETURN_REGISTRY.json."
    expect_fail("stale_contract_sentence_reintroduced", bad)

    bad = copy.deepcopy(source); bad["safety"]["execution_authorized"] = True
    expect_fail("execution_authority_leak", bad)

    print(json.dumps({"status": "PASS", "verdict": one["verdict"], "adversarial_cases": 13}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
