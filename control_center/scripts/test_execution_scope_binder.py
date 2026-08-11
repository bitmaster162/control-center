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
    assert out["verdict"] == "NO_EXECUTABLE_GATE_STALE_R43_PREDECESSOR"
    assert out["binding"]["historical_gate_suppressed"] is True
    assert out["binding"]["execution_ready"] is False
    assert out["binding"]["execution_authorized"] is False
    assert out["canonical_runtime"]["runtime_liveness_current"] == "UNVERIFIED_PROVIDER_READBACK_REQUIRED"

    bad = copy.deepcopy(source); bad["canonical_current_state"]["watcher_generation"] = "R43"
    expect_fail("canonical_generation_tamper", bad, command, effect)

    bad = copy.deepcopy(command); bad["summary"]["human_now"] = 1
    expect_fail("stale_human_gate_reintroduced", source, bad, effect)

    bad = copy.deepcopy(effect); bad["summary"]["effect_candidates_total"] = 1
    expect_fail("fabricated_effect_candidate", source, command, bad)

    bad = copy.deepcopy(source); bad["safety"]["execution_authorized"] = True
    expect_fail("execution_authority_leak", bad, command, effect)

    bad = copy.deepcopy(source); bad["known_divergences"] = []
    expect_fail("divergence_suppressed", bad, command, effect)

    print(json.dumps({"status":"PASS","verdict":out["verdict"],"adversarial_cases":5}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
