from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "control_center.execution_scope_binder.v1"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
EXPECTED_CURRENT_STATE_SHA = "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd"
EXPECTED_ROLE_VIEWS_SHA = "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148"
EXPECTED_BROKER_HEAD = "f14ab9a8f4b7ba7b1cca80759f4683916b1dc785"
EXPECTED_BROKER_TREE = "4762b2cdad463823e34da29e09b22ec580c6e778"
EXPECTED_TARGET = "C:\\PROJECTS\\control_return_broker"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(source: dict[str, Any], command: dict[str, Any], effect: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if source.get("schema") != "control_center.execution_scope_sources.v1":
        errors.append("source_schema_mismatch")
    anchor = source.get("authority_anchor", {})
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE" or anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA or anchor.get("provider_readback") != "all_exact":
        errors.append("r64_anchor_mismatch")
    state = source.get("canonical_current_state", {})
    role = source.get("canonical_role_views", {})
    if state.get("sha256") != EXPECTED_CURRENT_STATE_SHA or state.get("broker_status") != "INSTALLED_AND_WATCHING" or state.get("watcher_generation") != "R59":
        errors.append("canonical_broker_state_mismatch")
    if role.get("sha256") != EXPECTED_ROLE_VIEWS_SHA or role.get("codex07_lane") != "Return Plane / broker hardening" or not str(role.get("codex07_state", "")).startswith("R59_"):
        errors.append("canonical_role_view_mismatch")
    if command.get("schema") != "control_center.command_queue.v1" or command.get("summary", {}).get("human_now") != 0 or command.get("queues", {}).get("HUMAN_NOW") != []:
        errors.append("command_queue_must_have_no_human_gate")
    if command.get("queues", {}).get("HISTORICAL_QUEUE") != ["CMD::CODEX07-R43-RETURN-PLANE-V2"]:
        errors.append("historical_r43_binding_missing")
    if effect.get("schema") != "control_center.effect_readback_plane.v1" or effect.get("summary", {}).get("effect_candidates_total") != 0 or effect.get("effect_candidates") != []:
        errors.append("effect_plane_must_have_zero_candidates")

    provider = source.get("provider_readback", {})
    runtime = provider.get("runtime_receipt", {})
    activity = provider.get("post_deploy_broker_activity", {})
    github = provider.get("github_live", {})
    dashboard = provider.get("current_dashboard_snapshot", {})
    impl = provider.get("installed_implementation_semantics", {})
    if runtime.get("drive_file_id") != "1bkSWEPeNXdSHT09XMLJBk6MFHFwS46gD" or runtime.get("terminal") != "DF6_RUNTIME_DEPLOY_PASS" or runtime.get("target") != EXPECTED_TARGET or runtime.get("generation") != "R59":
        errors.append("runtime_receipt_identity_mismatch")
    if runtime.get("accepted_head") != EXPECTED_BROKER_HEAD or runtime.get("accepted_tree") != EXPECTED_BROKER_TREE or runtime.get("baseline_tests") != "PASS" or runtime.get("df6_tests") != "PASS":
        errors.append("runtime_receipt_git_or_test_mismatch")
    if runtime.get("control_center_stable_root_mutation") is not False or runtime.get("content_acceptance_claimed") is not False:
        errors.append("runtime_receipt_authority_leak")
    if activity.get("broker_head") != EXPECTED_BROKER_HEAD or activity.get("broker_tree") != EXPECTED_BROKER_TREE or activity.get("physical_status") != "DELIVERY_VERIFIED" or int(activity.get("accepted_entries", 0)) < 9:
        errors.append("post_deploy_activity_mismatch")
    if activity.get("direct_current_return_registry_edit") is not False or activity.get("semantic_acceptance_claimed") is not False:
        errors.append("post_deploy_activity_authority_leak")
    if github.get("repository") != "bitmaster162/control-return-broker" or github.get("default_branch") != "gpt/github-ready-r1" or github.get("head") != EXPECTED_BROKER_HEAD or github.get("tree") != EXPECTED_BROKER_TREE or github.get("pr") != 1 or github.get("pr_merged") is not True or github.get("merge_verified") is not True:
        errors.append("github_live_identity_mismatch")
    if dashboard.get("return_broker_status") != "DF6_CLOSED_MONITOR":
        errors.append("dashboard_broker_status_mismatch")
    if impl.get("repository_ref") != EXPECTED_BROKER_HEAD or impl.get("current_return_registry_reference_in_core") is not False or impl.get("publish_receipt_central_registry_mutated") is not False or impl.get("direct_current_return_registry_edit_observed") is not False:
        errors.append("installed_mutation_semantics_mismatch")
    for key, expected in {
        "registry_jsonl": "R59/MASTER_RETURN_REGISTRY_R59.jsonl",
        "registry_projection": "R59/MASTER_RETURN_REGISTRY_R59.json",
        "live_index": "R59/LIVE_INDEX_R59.json",
    }.items():
        if impl.get(key) != expected:
            errors.append(f"installed_mutation_path_mismatch:{key}")

    safety = source.get("safety", {})
    if safety.get("execution_authorized") is not False or safety.get("auto_execute") is not False or safety.get("can_trade") is not False or safety.get("capital_permission") != "DENY" or safety.get("deploy_permission") != "DENY" or safety.get("self_application") is not False:
        errors.append("safety_ceiling_mismatch")
    divergences = source.get("known_divergences", [])
    if not any(x.get("id") == "BROKER_REGISTRY_MUTATION_CONTRACT_DIVERGENCE_CONFIRMED" for x in divergences):
        errors.append("required_contract_divergence_missing")
    if errors:
        raise ValueError(";".join(errors))

    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_READ_ONLY_BINDING",
        "observed_at": source.get("observed_at"),
        "authority_anchor": anchor,
        "verdict": "NO_EXECUTABLE_GATE_RUNTIME_IDENTITY_VERIFIED_R43_HISTORICAL",
        "canonical_runtime": {
            "broker_status": state.get("broker_status"),
            "watcher_generation": state.get("watcher_generation"),
            "role_lane": role.get("codex07_lane"),
            "role_state": role.get("codex07_state"),
            "runtime_deployment_readback": "VERIFIED_DRIVE_RECEIPT",
            "runtime_target": runtime.get("target"),
            "runtime_head": runtime.get("accepted_head"),
            "runtime_tree": runtime.get("accepted_tree"),
            "watcher_start_terminal": runtime.get("terminal"),
            "watcher_pids_at_receipt": runtime.get("live_watcher_pids_at_receipt", []),
            "watcher_interval_seconds": runtime.get("interval_seconds"),
            "post_deploy_activity": "VERIFIED_BROKER_REGISTRATION_AFTER_DEPLOY",
            "post_deploy_activity_at_utc": activity.get("recorded_at_utc"),
            "post_deploy_accepted_entries": activity.get("accepted_entries"),
            "current_dashboard_as_of": dashboard.get("as_of"),
            "current_dashboard_status": dashboard.get("return_broker_status"),
            "current_process_liveness": "NOT_DIRECTLY_VERIFIED_AT_BINDER_OBSERVED_AT",
            "receipt_pids_are_not_current_process_proof": True,
        },
        "implementation_binding": {
            "repository": github.get("repository"),
            "default_branch": github.get("default_branch"),
            "head": github.get("head"),
            "tree": github.get("tree"),
            "target": runtime.get("target"),
            "return_root": runtime.get("return_root"),
            "generation": runtime.get("generation"),
            "mutation_paths": {
                "registry_jsonl": impl.get("registry_jsonl"),
                "registry_projection": impl.get("registry_projection"),
                "live_index": impl.get("live_index"),
            },
            "current_return_registry_reference_in_core": False,
            "direct_current_return_registry_edit_observed": False,
        },
        "binding": {
            "historical_work_order": "CODEX07-R43-RETURN-PLANE-V2",
            "historical_gate_suppressed": True,
            "current_human_gate_count": 0,
            "current_effect_candidate_count": 0,
            "runtime_identity_bound": True,
            "execution_scope_bound": False,
            "provider_target_bound": True,
            "mutation_set_bound": True,
            "executor_bound": False,
            "execution_authorized": False,
            "execution_ready": False,
            "blockers": [
                "NO_CURRENT_EFFECT_GATE",
                "R43_IS_HISTORICAL_PREDECESSOR",
                "CURRENT_PROCESS_LIVENESS_NOT_DIRECTLY_PROBED",
                "CANONICAL_ROOT_MUTATION_CONTRACT_DIVERGENCE_UNRESOLVED"
            ]
        },
        "source_precedence": [
            "R64_AUTHORITY_POLICY_AND_ROUTING",
            "VERIFIED_PROVIDER_RUNTIME_FACTS",
            "CURRENT_CONTROL_PROJECTIONS",
            "HISTORICAL_IMPLEMENTATION_EVIDENCE",
            "RETURN_REGISTRY_OBSERVATION"
        ],
        "precedence_note": "Canonical R64 controls authority boundaries; verified provider readback controls observed runtime/code facts. Their mutation-contract conflict is recorded, not silently reconciled.",
        "historical_evidence": source.get("historical_evidence", []),
        "source_divergences": divergences,
        "next_read_only_action": "READ_ONLY_CURRENT_PROCESS_LIVENESS_AND_R59_REGISTRY_HEALTH_CHECK",
        "next_readback_requirements": [
            "CURRENT_BROKER_PROCESS_OR_WATCHER_LIVENESS",
            "CURRENT_PROCESS_COMMAND_LINE_OR_START_SCRIPT_IDENTITY",
            "C:\\PROJECTS\\control_return_broker_HEAD_TREE_STILL_MATCH_ACCEPTED",
            "R59_MASTER_REGISTRY_AND_LIVE_INDEX_HEALTH",
            "CURRENT_RETURN_REGISTRY_UNCHANGED_BY_BROKER_IMPLEMENTATION",
            "NO_MUTATION_PERFORMED_DURING_READBACK"
        ],
        "policy": {
            "binder_grants_authority": False,
            "readback_grants_execution_authority": False,
            "auto_execute": False,
            "auto_apply": False,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
            "deploy_permission": "DENY"
        },
        "invariants": {
            "canonical_authority_and_provider_runtime_facts_are_distinct": True,
            "historical_gate_never_execution_ready": True,
            "verified_runtime_identity_does_not_grant_execution_authority": True,
            "receipt_pids_are_not_current_liveness": True,
            "contract_divergence_preserved": True,
            "no_scope_invention": True
        }
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build read-only Execution Scope Binder V1.")
    p.add_argument("source", type=Path); p.add_argument("command_queue", type=Path); p.add_argument("effect_plane", type=Path); p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        out = build(load(args.source), load(args.command_queue), load(args.effect_plane))
    except ValueError as exc:
        print(json.dumps({"status":"FAIL","errors":str(exc).split(";")}, indent=2)); return 2
    rendered = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output: args.output.write_text(rendered, encoding="utf-8")
    else: print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
