from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "control_center.broker_health_readback.v1"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
EXPECTED_HEAD = "f14ab9a8f4b7ba7b1cca80759f4683916b1dc785"
EXPECTED_TREE = "4762b2cdad463823e34da29e09b22ec580c6e778"
EXPECTED_STABLE_REGISTRY_SHA = "ea0ff88fce2d02f664087ea2697e71688ad95cb6deb65e22df73af2081dfb03f"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build(source: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if source.get("schema") != "control_center.broker_health_sources.v1":
        errors.append("source_schema_mismatch")
    anchor = source.get("authority_anchor", {})
    if anchor.get("generation") != "R64" or anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA:
        errors.append("r64_anchor_mismatch")
    runtime = source.get("runtime", {})
    if runtime.get("generation") != "R59" or runtime.get("repository") != "bitmaster162/control-return-broker" or runtime.get("default_branch") != "gpt/github-ready-r1":
        errors.append("runtime_identity_mismatch")
    if runtime.get("head") != EXPECTED_HEAD or runtime.get("tree") != EXPECTED_TREE:
        errors.append("runtime_git_mismatch")
    if runtime.get("deploy_terminal") != "DF6_RUNTIME_DEPLOY_PASS" or runtime.get("current_process_liveness") != "NOT_PROVIDER_OBSERVABLE":
        errors.append("runtime_health_boundary_mismatch")

    r59 = source.get("r59_generation", {})
    master = r59.get("master_registry", {})
    live = r59.get("live_index", {})
    readback = r59.get("controller_readback", {})
    ready = r59.get("controller_ready", {})
    if master.get("entry_count") != 9 or live.get("entry_count") != 9:
        errors.append("registry_index_count_mismatch")
    if master.get("unique_exact_identities") != 5 or master.get("historical_duplicate_groups") != 2 or master.get("historical_excess_rows") != 4:
        errors.append("historical_duplicate_accounting_mismatch")
    if set(live.get("slots", [])) != {"ANTIGRAVITY", "CODEX-02", "CLAUDE-BITUNIX"}:
        errors.append("live_index_slots_mismatch")
    if live.get("latest_slot") != "CLAUDE-BITUNIX" or live.get("latest_physical_status") != "DELIVERY_VERIFIED":
        errors.append("latest_delivery_mismatch")
    if readback.get("readback_status") != "PASS_MATCH":
        errors.append("controller_readback_not_pass")
    if ready.get("status") != "READY_FOR_CONTROLLER_REVIEW" or ready.get("created_last") is not True:
        errors.append("controller_ready_mismatch")
    if readback.get("bundle_sha256") != ready.get("bundle_sha256"):
        errors.append("controller_bundle_sha_mismatch")

    stable = source.get("stable_current_return_registry", {})
    if stable.get("sha256") != EXPECTED_STABLE_REGISTRY_SHA or stable.get("unchanged_from_prior_control_center_readback") is not True or stable.get("direct_broker_mutation_observed") is not False:
        errors.append("stable_registry_changed_or_mutated")

    activity = source.get("activity", {})
    if activity.get("provider_liveness_class") != "INDIRECT_ACTIVITY_ONLY_PROCESS_NOT_OBSERVABLE":
        errors.append("provider_liveness_class_mismatch")
    if activity.get("post_df6_duplicate_regression_observed") is not False:
        errors.append("post_df6_duplicate_regression")
    if activity.get("later_broker_generated_artifact_observed") is not False:
        errors.append("unexpected_later_artifact_flag")

    divergence = source.get("contract_divergence", {})
    if divergence.get("status") != "CONFIRMED_OPEN_SEMANTIC_CONTRACT_DIVERGENCE":
        errors.append("contract_divergence_missing")
    safety = source.get("safety", {})
    if safety.get("read_only") is not True or safety.get("authority_granted") is not False or safety.get("execution_authorized") is not False or safety.get("auto_execute") is not False or safety.get("can_trade") is not False or safety.get("capital_permission") != "DENY" or safety.get("deploy_permission") != "DENY" or safety.get("self_application") is not False:
        errors.append("safety_boundary_mismatch")
    if errors:
        raise ValueError(";".join(errors))

    observed = parse_ts(source["observed_at"])
    latest_controller = parse_ts(ready["created_at_utc"])
    age_seconds = int((observed - latest_controller).total_seconds())
    return {
        "schema": SCHEMA,
        "projection_kind": "NON_AUTHORITY_READ_ONLY_HEALTH_PROJECTION",
        "observed_at": source["observed_at"],
        "authority_anchor": anchor,
        "verdict": "HEALTHY_PROVIDER_EVIDENCE_PROCESS_LIVENESS_NOT_OBSERVABLE",
        "runtime": {
            "generation": "R59",
            "repository": runtime["repository"],
            "default_branch": runtime["default_branch"],
            "head": runtime["head"],
            "tree": runtime["tree"],
            "target": runtime["target"],
            "deploy_terminal": runtime["deploy_terminal"],
            "process_liveness": "NOT_PROVIDER_OBSERVABLE",
            "watcher_pids_at_deploy_receipt": runtime["watcher_pids_at_deploy_receipt"],
            "receipt_pids_are_current_proof": False,
        },
        "registry_health": {
            "master_entries": master["entry_count"],
            "live_index_entries": live["entry_count"],
            "live_slots": live["slots"],
            "latest_slot": live["latest_slot"],
            "latest_physical_status": live["latest_physical_status"],
            "master_live_count_match": master["entry_count"] == live["entry_count"],
            "unique_exact_identities": master["unique_exact_identities"],
            "historical_duplicate_groups": master["historical_duplicate_groups"],
            "historical_excess_rows": master["historical_excess_rows"],
            "historical_duplicates_preserved_not_pruned": True,
            "post_df6_duplicate_regression_observed": False,
        },
        "controller_health": {
            "readback_status": readback["readback_status"],
            "ready_status": ready["status"],
            "ready_created_last": ready["created_last"],
            "bundle_sha256_match": readback["bundle_sha256"] == ready["bundle_sha256"],
            "last_controller_seal_at_utc": ready["created_at_utc"],
            "age_seconds_at_observation": age_seconds,
        },
        "stable_registry_health": {
            "drive_id": stable["drive_id"],
            "sha256": stable["sha256"],
            "payload_updated_at_utc": stable["payload_updated_at_utc"],
            "unchanged": stable["unchanged_from_prior_control_center_readback"],
            "direct_broker_mutation_observed": False,
        },
        "activity": {
            "latest_broker_generated_artifact_at_utc": activity["latest_broker_generated_artifact_at_utc"],
            "latest_known_registration_receipt_at_utc": activity["latest_known_registration_receipt_at_utc"],
            "later_broker_generated_artifact_observed": False,
            "liveness_evidence_class": "INDIRECT_ACTIVITY",
            "process_liveness_observable": False,
        },
        "contract_divergence": divergence,
        "next_action": "NO_RUNTIME_ACTION_REQUIRED; OBSERVE_OR_SEPARATELY_GATE_CANONICAL_CONTRACT_REPAIR",
        "human_gate_required_for_root_repair": "SEPARATE_EXPLICIT_CANONICAL_SEMANTIC_REPAIR_GATE",
        "policy": {
            "health_projection_grants_authority": False,
            "process_restart_authorized": False,
            "root_repair_authorized": False,
            "registry_mutation_authorized": False,
            "execution_authorized": False,
            "can_trade": False,
            "capital_permission": "DENY",
            "deploy_permission": "DENY",
            "self_application": False,
        },
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build Broker Health Readback V1")
    p.add_argument("source", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        out = build(load(args.source))
    except ValueError as exc:
        print(json.dumps({"status": "FAIL", "errors": str(exc).split(";")}, indent=2))
        return 2
    rendered = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
