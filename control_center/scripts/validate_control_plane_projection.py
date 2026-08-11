from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECTION = ROOT / "control_center" / "data" / "current_control_plane.seed.v1.json"

TRANSPORT = {"DISCOVERED", "STAGED", "VERIFIED", "DELIVERED", "ACKNOWLEDGED", "QUARANTINED"}
CONTENT = {"UNREVIEWED", "ACCEPTED", "HOLD", "REJECTED"}
APPLY = {"NOT_APPLIED", "APPLIED"}

R64_CANONICAL_DECISION = "ACCEPT_R64_POINTER_PROMOTION"
R64_POINTER_SHA256 = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
R64_MANIFEST_SHA256 = "41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d"
R64_ROOT_HASHES = {
    "CURRENT_STATE.json": "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd",
    "ROLE_INDEX.json": "e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567",
    "ROLE_VIEWS.json": "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148",
}


def fail(errors: list[str], code: str) -> None:
    errors.append(code)


def validate(payload: dict) -> list[str]:
    errors: list[str] = []

    if payload.get("schema") != "control_center.current_control_plane_projection.v1":
        fail(errors, "schema_mismatch")
    if payload.get("projection_kind") != "NON_AUTHORITY_PROJECTION":
        fail(errors, "projection_must_be_non_authority")

    current = payload.get("canonical_current", {})
    if current.get("generation") != "R64":
        fail(errors, "current_generation_must_be_R64")
    if current.get("status") != "ACTIVE":
        fail(errors, "R64_current_status_must_be_ACTIVE")
    if current.get("canonical_decision") != R64_CANONICAL_DECISION:
        fail(errors, "R64_promotion_decision_mismatch")
    if current.get("accepted_manifest_sha256") != R64_MANIFEST_SHA256:
        fail(errors, "R64_manifest_sha_mismatch")

    pointer = current.get("pointer", {})
    if pointer.get("locator") != "Control canter/00_CONTROL_CURRENT/CURRENT_POINTER.json":
        fail(errors, "R64_pointer_locator_mismatch")
    if pointer.get("accepted_artifact") != "CURRENT_POINTER_R64_ACTIVE.json":
        fail(errors, "R64_pointer_artifact_mismatch")
    if pointer.get("sha256") != R64_POINTER_SHA256:
        fail(errors, "R64_pointer_sha_mismatch")
    if pointer.get("provider_readback") != "all_exact":
        fail(errors, "R64_provider_readback_must_be_all_exact")
    if current.get("root_hashes") != R64_ROOT_HASHES:
        fail(errors, "R64_root_hashes_mismatch")

    predecessor = current.get("predecessor_lineage", {})
    if predecessor.get("generation") != "R63":
        fail(errors, "predecessor_generation_must_be_R63")
    if predecessor.get("is_current") is not False:
        fail(errors, "R63_must_not_be_current")
    if "SUPERSEDED_AS_CURRENT" not in str(predecessor.get("status", "")):
        fail(errors, "R63_predecessor_status_must_mark_supersession")

    safety = payload.get("safety", {})
    if safety.get("can_trade") is not False:
        fail(errors, "can_trade_must_be_false")
    if safety.get("capital_permission") != "DENY":
        fail(errors, "capital_permission_must_be_DENY")
    if safety.get("deploy_permission") != "DENY":
        fail(errors, "deploy_permission_must_be_DENY")
    if safety.get("self_application") is not False:
        fail(errors, "self_application_must_be_false")
    if safety.get("external_messages_require_exact_send") is not True:
        fail(errors, "external_messages_must_require_exact_send")

    owners = {row.get("owner") for row in payload.get("owner_map", [])}
    projects = payload.get("projects", [])
    project_ids = {row.get("id") for row in projects}
    for row in projects:
        if not row.get("id") or not row.get("owner") or not row.get("state") or not row.get("next"):
            fail(errors, f"project_incomplete:{row.get('id')}")
        if row.get("owner") not in owners:
            fail(errors, f"project_owner_not_registered:{row.get('id')}:{row.get('owner')}")

    work_ids: set[str] = set()
    for row in payload.get("work_items", []):
        work_id = row.get("id")
        if not work_id:
            fail(errors, "work_item_missing_id")
            continue
        if work_id in work_ids:
            fail(errors, f"duplicate_work_id:{work_id}")
        work_ids.add(work_id)
        if row.get("project") not in project_ids:
            fail(errors, f"work_unknown_project:{work_id}")
        if not row.get("owner") or not row.get("state") or not row.get("effect_class") or not row.get("human_gate"):
            fail(errors, f"work_item_incomplete:{work_id}")
        if row.get("effect_class") == "EXTERNAL_MESSAGE" and row.get("human_gate") != "EXACT_SEND_PER_MESSAGE":
            fail(errors, f"external_message_gate_invalid:{work_id}")

    return_ids: set[str] = set()
    for row in payload.get("returns", []):
        return_id = row.get("return_id")
        if not return_id:
            fail(errors, "return_missing_id")
            continue
        if return_id in return_ids:
            fail(errors, f"duplicate_return_id:{return_id}")
        return_ids.add(return_id)
        if row.get("transport_status") not in TRANSPORT:
            fail(errors, f"invalid_transport_status:{return_id}")
        if row.get("content_status") not in CONTENT:
            fail(errors, f"invalid_content_status:{return_id}")
        if row.get("apply_status") not in APPLY:
            fail(errors, f"invalid_apply_status:{return_id}")
        if row.get("apply_status") == "APPLIED" and row.get("content_status") != "ACCEPTED":
            fail(errors, f"applied_without_acceptance:{return_id}")

    broker = payload.get("return_plane", {})
    if broker.get("authority_boundary") != "TRANSPORT_ONLY":
        fail(errors, "broker_must_remain_transport_only")
    machine = broker.get("state_machine", {})
    if set(machine.get("transport", [])) != TRANSPORT:
        fail(errors, "broker_transport_state_machine_mismatch")
    if set(machine.get("semantic", [])) != CONTENT:
        fail(errors, "broker_semantic_state_machine_mismatch")
    if set(machine.get("apply", [])) != APPLY:
        fail(errors, "broker_apply_state_machine_mismatch")

    decisions = payload.get("decisions", [])
    if len(decisions) > 3:
        fail(errors, "operator_decision_surface_exceeds_three")
    for row in decisions:
        if row.get("state") not in {"ACCEPTED", "HOLD", "REJECTED", "HUMAN_DECISION_REQUIRED"}:
            fail(errors, f"invalid_decision_state:{row.get('id')}")
        if not row.get("next_readback"):
            fail(errors, f"decision_missing_readback:{row.get('id')}")

    commercial = payload.get("commercial", {})
    active = commercial.get("active_sellable_lines", [])
    if len(active) != 2:
        fail(errors, "sellable_lines_must_equal_two")
    sprint = commercial.get("operator_sprint", {})
    if sprint.get("self_pilot_counts_toward_mvp") is not False:
        fail(errors, "self_pilot_must_not_count_toward_external_mvp")

    invariants = set(payload.get("invariants", []))
    required = {
        "CURRENT_CANONICAL_GENERATION == R64",
        "R63 != CURRENT",
        "RETURNED != ACCEPTED",
        "DELIVERED != APPLIED",
        "BROKER_TRANSPORT != SEMANTIC_AUTHORITY",
        "DASHBOARD != TRUTH_OWNER",
        "ONE_PERSISTENT_WRITER_PER_PROJECT",
        "NO_AUTO_SUCCESSOR_WORK_ORDERS",
        "NO_SELF_APPROVAL",
        "NO_SELF_MERGE",
        "NO_SELF_DEPLOY",
    }
    if not required.issubset(invariants):
        fail(errors, "required_invariants_missing")

    return errors


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    path = Path(argv[0]) if argv else DEFAULT_PROJECTION
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(payload)
    result = {"status": "PASS" if not errors else "FAIL", "projection": str(path), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
