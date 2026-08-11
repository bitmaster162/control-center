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
    assert one["verdict"] == "HEALTHY_PROVIDER_EVIDENCE_PROCESS_LIVENESS_NOT_OBSERVABLE"
    assert one["registry_health"]["master_entries"] == 9
    assert one["registry_health"]["live_index_entries"] == 9
    assert one["registry_health"]["historical_duplicate_groups"] == 2
    assert one["registry_health"]["historical_excess_rows"] == 4
    assert one["registry_health"]["post_df6_duplicate_regression_observed"] is False
    assert one["stable_registry_health"]["unchanged"] is True
    assert one["runtime"]["process_liveness"] == "NOT_PROVIDER_OBSERVABLE"
    assert one["runtime"]["receipt_pids_are_current_proof"] is False

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

    bad = copy.deepcopy(source); bad["contract_divergence"]["status"] = "RESOLVED"
    expect_fail("contract_divergence_silently_resolved", bad)

    bad = copy.deepcopy(source); bad["safety"]["execution_authorized"] = True
    expect_fail("execution_authority_leak", bad)

    print(json.dumps({"status": "PASS", "verdict": one["verdict"], "adversarial_cases": 10}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
