from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROPOSAL = BASE / "data" / "continuityos_r52_binding_reconciliation.generated.v1.json"
QUEUE = BASE / "data" / "command_queue.generated.v1.json"
LIFECYCLE = BASE / "data" / "work_order_lifecycle.generated.v1.json"

EXPECTED_ZIP_SHA = "6d9a3bb3b31c91cefac0515d3dda1e52d079b0932e747da8b257b9e382851b30"
EXPECTED_HEAD = "b5436f373dcb19873a3b0908b26f8d0e22cb8125"
EXPECTED_TREE = "75224c68a7eb041bb34d1d87e6c429a98db57593"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(data: dict, queue: dict, lifecycle: dict) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "control_center.continuityos_r52_binding_reconciliation.v1":
        errors.append("schema_mismatch")
    if data.get("projection_kind") != "NON_AUTHORITY_SUPERSESSION_PROPOSAL":
        errors.append("projection_kind_mismatch")
    if data.get("proposal_status") != "SUPERSESSION_PROPOSAL_READY_NO_APPLY":
        errors.append("proposal_status_mismatch")

    current = data.get("current_binding", {})
    if current.get("work_order") != "CODEX01-R43-CONTINUITY-186-CLOSURE":
        errors.append("current_binding_not_r43")
    if not any(x.get("work_order") == current.get("work_order") for x in lifecycle.get("work_orders", [])):
        errors.append("current_r43_missing_from_lifecycle")
    if not any(x.get("work_order") == current.get("work_order") for x in queue.get("attention_routing", [])):
        errors.append("current_r43_missing_from_queue_attention")

    r52 = data.get("r52_exact_return", {})
    expected = {
        "work_order": "CODEX01-R52-CONTINUITYOS-CANONICAL-ADOPTION",
        "zip_bytes": 48065,
        "zip_sha256": EXPECTED_ZIP_SHA,
        "zip_sha256_recomputed_from_provider_bytes": True,
        "sidecar_exact_zip_binding": True,
        "ready_created_last": True,
        "entry_count": 55,
        "zip_crc": "PASS",
        "duplicate_entries": 0,
        "unsafe_entries": 0,
        "terminal_category": "LOCAL_CANONICAL_ADOPTION_PASS",
    }
    for key, value in expected.items():
        if r52.get(key) != value:
            errors.append(f"r52_exact_mismatch:{key}")
    git = r52.get("git", {})
    if git.get("head") != EXPECTED_HEAD or git.get("tree") != EXPECTED_TREE or git.get("clean") is not True:
        errors.append("r52_git_identity_mismatch")
    boundary = r52.get("effect_boundary", {})
    if boundary.get("runtime_activation") is not False or boundary.get("production_adopted") is not False:
        errors.append("r52_effect_boundary_expanded")
    if boundary.get("live_host_state_proven_now") is not False:
        errors.append("live_host_state_overclaim")

    transport = data.get("r55_transport_chain", {})
    if transport.get("registry_verification_status") != "VERIFIED_PASS":
        errors.append("r55_registry_not_verified")
    if transport.get("registry_predecessor_or_current") != "CURRENT_R52":
        errors.append("r55_not_current_r52")
    if transport.get("controller_readback") != "PASS" or transport.get("delivery_close") != "DELIVERY_CLOSED_PASS":
        errors.append("r55_delivery_chain_not_closed")
    if transport.get("delivery_ready_created_last") is not True:
        errors.append("r55_ready_not_last")

    newer = data.get("newer_scope_check", {})
    if newer.get("r57_work_order_states_local_adoption_already_passed") is not True:
        errors.append("r57_does_not_bind_r52_adoption")
    if newer.get("global_absence_claimed") is not False:
        errors.append("r57_global_absence_overclaim")
    if newer.get("later_verified_strict_return_must_supersede_r52") is not True:
        errors.append("future_strict_return_precedence_missing")

    proposal = data.get("supersession_proposal", {})
    if proposal.get("apply_now") is not False:
        errors.append("proposal_self_applies")
    if proposal.get("from_work_order") != "CODEX01-R43-CONTINUITY-186-CLOSURE":
        errors.append("proposal_from_mismatch")
    if proposal.get("to_work_order") != "CODEX01-R52-CONTINUITYOS-CANONICAL-ADOPTION":
        errors.append("proposal_to_mismatch")
    if proposal.get("proposed_to_state") != "CURRENT_VERIFIED_EVIDENCE_SEMANTIC_REVIEW_REQUIRED":
        errors.append("proposal_skips_semantic_review")
    if proposal.get("human_gate_created") is not False or proposal.get("effect_candidate_created") is not False:
        errors.append("proposal_creates_effect_or_human_gate")
    if proposal.get("live_host_readback_required_before_current_operational_health_claim") is not True:
        errors.append("live_host_readback_boundary_missing")

    for key, value in data.get("invariants", {}).items():
        if value is not False:
            errors.append(f"mutation_invariant_not_false:{key}")
    safety = data.get("safety", {})
    for key in (
        "routing_mutation_authorized", "dispatch_authorized", "apply_authorized",
        "execution_authorized", "deploy_authorized", "external_message_authorized",
        "runtime_activation_authorized", "can_trade", "self_application",
    ):
        if safety.get(key) is not False:
            errors.append(f"authority_leak:{key}")
    if safety.get("capital_permission") != "DENY":
        errors.append("capital_permission_not_deny")
    return errors


def self_test() -> None:
    data, queue, lifecycle = load(PROPOSAL), load(QUEUE), load(LIFECYCLE)
    assert validate(data, queue, lifecycle) == []

    x = copy.deepcopy(data); x["supersession_proposal"]["apply_now"] = True
    assert "proposal_self_applies" in validate(x, queue, lifecycle)
    x = copy.deepcopy(data); x["r52_exact_return"]["zip_sha256"] = "0" * 64
    assert "r52_exact_mismatch:zip_sha256" in validate(x, queue, lifecycle)
    x = copy.deepcopy(data); x["r52_exact_return"]["effect_boundary"]["live_host_state_proven_now"] = True
    assert "live_host_state_overclaim" in validate(x, queue, lifecycle)
    x = copy.deepcopy(data); x["newer_scope_check"]["global_absence_claimed"] = True
    assert "r57_global_absence_overclaim" in validate(x, queue, lifecycle)
    x = copy.deepcopy(data); x["supersession_proposal"]["proposed_to_state"] = "ACCEPTED"
    assert "proposal_skips_semantic_review" in validate(x, queue, lifecycle)
    x = copy.deepcopy(data); x["safety"]["dispatch_authorized"] = True
    assert "authority_leak:dispatch_authorized" in validate(x, queue, lifecycle)
    print("CONTINUITYOS_R52_BINDING_RECONCILIATION_ADVERSARIAL_TEST_PASS")


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test(); return 0
    errors = validate(load(PROPOSAL), load(QUEUE), load(LIFECYCLE))
    if errors:
        raise SystemExit(";".join(errors))
    print("CONTINUITYOS_R52_BINDING_RECONCILIATION_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
