from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SNAPSHOT_SCHEMA = "control_center.provider_snapshot.v1"
PROJECTION_SCHEMA = "control_center.current_control_plane_projection.v1"
R64 = {
    "generation": "R64",
    "status": "ACTIVE",
    "decision": "ACCEPT_R64_POINTER_PROMOTION",
    "pointer_sha256": "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef",
    "manifest_sha256": "41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d",
    "current_state_sha256": "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd",
    "role_index_sha256": "e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567",
    "role_views_sha256": "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148",
    "provider_readback": "all_exact",
    "r63_is_current": False,
}
TRUTH_DELTAS = {
    "BITEVO_PUBLIC_PRODUCTION_PROOF_SATISFIED",
    "AGENT_AUTHORITY_AUDIT_DEPENDENCY_CLEARED_INTERNAL_PREP_ONLY",
    "P0_D4_ALL_THREE_CLOSED",
    "CLAUDE_BITUNIX_SLOT_PRESENT_PENDING_OBSERVATION_WINDOW",
}


def by_id(rows: list[dict[str, Any]], key: str = "id") -> dict[str, dict[str, Any]]:
    return {str(row.get(key)): row for row in rows if isinstance(row, dict) and row.get(key)}


def validate_snapshot(s: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if s.get("schema") != SNAPSHOT_SCHEMA:
        errors.append("snapshot_schema_mismatch")
    if s.get("snapshot_kind") != "NON_AUTHORITY_PROVIDER_READBACK":
        errors.append("snapshot_must_be_non_authority")
    roots = s.get("canonical_roots", {})
    for key, expected in R64.items():
        if roots.get(key) != expected:
            errors.append(f"canonical_root_mismatch:{key}")
    rr = s.get("return_registry", {})
    if rr.get("schema") != "CONTROL_RETURN_REGISTRY_V4":
        errors.append("return_registry_schema_mismatch")
    if rr.get("stable_drive_file_id") != "1BXdqWzA74SvkgcygO_ktO_2uolqFshWm":
        errors.append("return_registry_identity_mismatch")
    b = s.get("github_lanes", {}).get("bitevo_public", {})
    if not (b.get("merged") is True and b.get("main_sha") == b.get("merge_sha") == b.get("vercel_github_commit_sha") and b.get("vercel_state") == "READY" and b.get("vercel_target") == "production"):
        errors.append("bitevo_public_production_proof_incomplete")
    if b.get("external_outreach_authorized") is not False:
        errors.append("outreach_must_remain_unauthorized")
    p0 = s.get("hanri_evidence", {})
    if not (p0.get("issue_state") == "closed" and p0.get("p0_1") == "CLOSED" and p0.get("p0_2") == "RE_CLOSED" and p0.get("p0_3") == "CLOSED" and p0.get("authority_expansion") is False):
        errors.append("p0_consolidated_closure_incomplete")
    return errors


def validate_projection(s: dict[str, Any], p: dict[str, Any]) -> list[str]:
    errors = validate_snapshot(s)
    if p.get("schema") != PROJECTION_SCHEMA or p.get("projection_kind") != "NON_AUTHORITY_PROJECTION":
        errors.append("projection_contract_mismatch")
    if p.get("projection_source") != "GENERATED_FROM_PROVIDER_SNAPSHOT" or p.get("observed_at") != s.get("observed_at"):
        errors.append("projection_provenance_mismatch")

    roots = s["canonical_roots"]
    current = p.get("canonical_current", {})
    if current.get("generation") != "R64" or current.get("status") != "ACTIVE" or current.get("canonical_decision") != roots["decision"]:
        errors.append("projection_r64_current_mismatch")
    if current.get("pointer", {}).get("sha256") != roots["pointer_sha256"] or current.get("pointer", {}).get("provider_readback") != "all_exact":
        errors.append("projection_pointer_mismatch")
    if current.get("predecessor_lineage", {}).get("is_current") is not False:
        errors.append("projection_r63_current_forbidden")

    safety = p.get("safety", {})
    if not (safety.get("can_trade") is False and safety.get("capital_permission") == "DENY" and safety.get("deploy_permission") == "DENY" and safety.get("self_application") is False and safety.get("external_messages_require_exact_send") is True):
        errors.append("projection_safety_ceiling_mismatch")

    projects = by_id(p.get("projects", []))
    expected_projects = {
        "bitevo-public": "PRODUCTION_V3_VERIFIED",
        "agent-authority-audit": "READY_INTERNAL_PREP_SEND_GATED",
        "p0-security": "D4_CLOSED_ALL_THREE",
        "hanri": "ACTIVE_PARALLEL_P0_CLOSED",
    }
    for pid, state in expected_projects.items():
        if projects.get(pid, {}).get("state") != state:
            errors.append(f"project_state_mismatch:{pid}")

    work = by_id(p.get("work_items", []))
    if work.get("AUDIT-WAVE1", {}).get("state") != "READY_INTERNAL_PREP" or work.get("AUDIT-WAVE1", {}).get("human_gate") != "EXACT_SEND_PER_MESSAGE":
        errors.append("audit_send_gate_mismatch")
    if work.get("HANRI-D4-P0", {}).get("state") != "RETURNED_CLOSED":
        errors.append("p0_return_work_mismatch")

    lanes = p.get("provider_lanes", {})
    if lanes.get("bitevo_public") != s.get("github_lanes", {}).get("bitevo_public") or lanes.get("hanri") != s.get("github_lanes", {}).get("hanri"):
        errors.append("provider_lane_mismatch")

    observations = by_id(p.get("return_registry_observations", []), "slot")
    for slot, source in s.get("return_registry", {}).get("slots", {}).items():
        row = observations.get(slot, {})
        if row.get("reported_state") != source.get("reported_state") or row.get("work_order") != source.get("work_order") or row.get("semantic_interpretation") != "NONE_REGISTRY_OBSERVATION_ONLY":
            errors.append(f"registry_observation_mismatch:{slot}")

    if set(p.get("current_truth_deltas", [])) != TRUTH_DELTAS:
        errors.append("truth_delta_mismatch")
    commercial = by_id(p.get("commercial", {}).get("active_sellable_lines", []))
    if len(commercial) != 2 or commercial.get("agent-authority-audit", {}).get("state") != "READY_INTERNAL_PREP_SEND_GATED":
        errors.append("commercial_lane_mismatch")
    gates = {x.get("id") for x in p.get("human_gates", []) if isinstance(x, dict)}
    if "SEND" not in gates or "MERGE_CONTROL_CENTER" not in gates:
        errors.append("required_human_gate_missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed binding check for provider-backed Control Center projection")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--check", type=Path, required=True)
    args = parser.parse_args()
    s = json.loads(args.snapshot.read_text(encoding="utf-8"))
    p = json.loads(args.check.read_text(encoding="utf-8"))
    errors = validate_projection(s, p)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors, "check": str(args.check)}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
