from __future__ import annotations

import json
from pathlib import Path

from build_human_gate_packets import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> int:
    generated = load(DATA / "human_gate_packets.generated.v1.json")
    rebuilt = build(
        load(DATA / "command_queue.generated.v1.json"),
        load(DATA / "work_order_lifecycle.generated.v1.json"),
        load(DATA / "decision_effect_ledger.generated.v1.json"),
        load(DATA / "effect_readback_plane.generated.v1.json"),
    )
    if generated != rebuilt:
        print(json.dumps({"status": "FAIL", "error": "human_gate_packet_semantic_mismatch"}, indent=2))
        return 2

    packets = generated.get("packets", [])
    policy = generated.get("policy", {})
    summary = generated.get("summary", {})
    errors: list[str] = []
    if generated.get("schema") != "control_center.human_gate_packets.v1":
        errors.append("schema_mismatch")
    if generated.get("projection_kind") != "NON_AUTHORITY_PROJECTION":
        errors.append("projection_kind_mismatch")
    if policy.get("packet_grants_authority") is not False:
        errors.append("packet_authority_leak")
    if policy.get("generic_continuation_is_authorization") is not False:
        errors.append("generic_continuation_authority_leak")
    if policy.get("auto_apply") is not False or policy.get("auto_execute") is not False:
        errors.append("auto_effect_forbidden")
    if policy.get("self_approval") is not False or policy.get("self_application") is not False:
        errors.append("self_authority_forbidden")
    if policy.get("can_trade") is not False or policy.get("capital_permission") != "DENY" or policy.get("deploy_permission") != "DENY":
        errors.append("safety_ceiling_mismatch")
    if summary.get("human_now_commands") != summary.get("packets_total"):
        errors.append("human_now_packet_coverage_mismatch")
    if summary.get("effects_authorized") != 0 or summary.get("executions_authorized") != 0:
        errors.append("current_authority_must_be_zero")
    for packet in packets:
        if packet.get("status") != "OPEN_HUMAN_DECISION_REQUIRED":
            errors.append("unexpected_packet_status")
        if packet.get("executor_binding", {}).get("executor") is not None:
            errors.append("invented_executor")
        if packet.get("executor_binding", {}).get("state") != "UNBOUND_REQUIRES_SEPARATE_BINDING":
            errors.append("executor_binding_state_mismatch")
        if packet.get("effect_scope", {}).get("execution_ready") is not False:
            errors.append("packet_must_not_be_execution_ready")
        current = packet.get("current_state", {})
        if current.get("effect_authorized") is not False or current.get("execution_authorized") is not False:
            errors.append("packet_current_authority_leak")
        if current.get("execution_receipt") is not None or current.get("readback_receipt") is not None:
            errors.append("packet_invented_receipt")
        if packet.get("readback_contract", {}).get("closure_before_verified_readback") is not False:
            errors.append("closure_before_readback_forbidden")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 2
    print(json.dumps({"status": "PASS", "packets": len(packets), "execution_ready": summary.get("execution_ready_packets", 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
