from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
DIAGNOSTIC = BASE / "data" / "provider_refresh_controller_status.current.v1.json"
COMMAND_QUEUE = BASE / "data" / "command_queue.generated.v1.json"
OUTPUT = BASE / "data" / "provider_system_attention.generated.v1.json"

DRIFT_VERDICT = "HOLD_PROVIDER_DRIFT_DETECTED"
NEUTRAL_VERDICT = "NO_HOLD_DIAGNOSTIC_RECORDED"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_projection(diagnostic: dict[str, Any], command_queue: dict[str, Any]) -> dict[str, Any]:
    verdict = str(diagnostic.get("verdict", ""))
    human_now_count = len(command_queue.get("human_now", []))
    effect_candidates = int(command_queue.get("summary", {}).get("effect_candidates", 0))
    items: list[dict[str, Any]] = []

    if verdict == DRIFT_VERDICT:
        items.append(
            {
                "id": "SYSATTN::PROVIDER_DRIFT_HOLD",
                "state": "DRIFT_HOLD",
                "severity": "HIGH",
                "owner": "CONTROL_CENTER",
                "source_verdict": verdict,
                "requested_action": "READ_ONLY_PROVIDER_DRIFT_INVESTIGATION",
                "human_now": False,
                "human_gate": False,
                "effect_candidate": False,
                "dispatch_authorized": False,
                "apply_authorized": False,
                "execution_authorized": False,
                "write_authorized": False,
                "auto_fix": False,
                "controller_errors": diagnostic.get("controller_errors", []),
                "mismatches": diagnostic.get("mismatches", []),
                "note": "Provider drift requires bounded read-only investigation. This system-attention item grants no mutation or effect authority.",
            }
        )

    return {
        "schema": "control_center.provider_system_attention.v1",
        "projection_kind": "NON_AUTHORITY_OPERATOR_ATTENTION_PROJECTION",
        "source_chain": [
            "PROVIDER_REFRESH_CONTROLLER_STATUS",
            "COMMAND_QUEUE_INVARIANT_SNAPSHOT",
            "PROVIDER_SYSTEM_ATTENTION",
        ],
        "source_status_verdict": verdict,
        "source_projection_observed_at": command_queue.get("observed_at"),
        "absence_does_not_prove_no_drift": verdict == NEUTRAL_VERDICT,
        "summary": {
            "system_attention_count": len(items),
            "human_now_before": human_now_count,
            "human_now_after": human_now_count,
            "effect_candidates_before": effect_candidates,
            "effect_candidates_after": effect_candidates,
        },
        "system_attention": items,
        "invariants": {
            "command_queue_mutated": False,
            "human_now_unchanged": True,
            "effect_candidates_unchanged": True,
            "human_gate_created": False,
            "effect_candidate_created": False,
            "command_created": False,
            "system_attention_grants_authority": False,
        },
        "safety": {
            "provider_write_authorized": False,
            "root_write_authorized": False,
            "registry_write_authorized": False,
            "runtime_mutation_authorized": False,
            "routing_mutation_authorized": False,
            "dispatch_authorized": False,
            "apply_authorized": False,
            "execution_authorized": False,
            "deploy_authorized": False,
            "external_message_authorized": False,
            "can_trade": False,
            "capital_permission": "DENY",
            "self_application": False,
        },
    }


def serialize(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bounded provider-drift system-attention projection.")
    parser.add_argument("--check", action="store_true", help="Fail when committed projection differs from deterministic build")
    args = parser.parse_args()

    built = serialize(build_projection(load(DIAGNOSTIC), load(COMMAND_QUEUE)))
    if args.check:
        committed = OUTPUT.read_text(encoding="utf-8")
        if committed != built:
            raise SystemExit("provider_system_attention_generated_mismatch")
        print("PROVIDER_DRIFT_OPERATOR_ATTENTION_BUILD_CHECK_PASS")
        return 0

    OUTPUT.write_text(built, encoding="utf-8")
    print(str(OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
