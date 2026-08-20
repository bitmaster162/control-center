from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "data" / "canonical_contract_repair_proposal.generated.v1.json"

EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
EXPECTED_CURRENT_STATE_SHA = "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd"
EXPECTED_CURRENT_VALUE = "Only the broker mutates CURRENT_RETURN_REGISTRY.json; agents publish via Publish-Agent-Return.ps1; controller decisions gate slot registration."
EXPECTED_PROPOSED_VALUE = "Only the broker mutates generation-scoped return-broker state for the active watcher generation (for R59: MASTER_RETURN_REGISTRY_R59.jsonl, MASTER_RETURN_REGISTRY_R59.json, and LIVE_INDEX_R59.json); agents publish via Publish-Agent-Return.ps1; controller decisions gate slot registration. The installed R59/DF6 broker does not directly mutate CURRENT_RETURN_REGISTRY.json."
EXPECTED_GATE = "APPLY_R64_BROKER_MUTATION_RULE_REPAIR_V1"


def validate(p: dict) -> list[str]:
    errors: list[str] = []
    if p.get("schema") != "control_center.canonical_contract_repair_proposal.v1":
        errors.append("schema_mismatch")
    if p.get("projection_kind") != "NON_AUTHORITY_REVIEW_ONLY_PROPOSAL":
        errors.append("projection_kind_mismatch")

    anchor = p.get("authority_anchor", {})
    if anchor.get("generation") != "R64" or anchor.get("status") != "ACTIVE":
        errors.append("authority_anchor_generation_status_mismatch")
    if anchor.get("pointer_sha256") != EXPECTED_POINTER_SHA:
        errors.append("pointer_sha_mismatch")
    if anchor.get("current_state_sha256") != EXPECTED_CURRENT_STATE_SHA:
        errors.append("current_state_sha_mismatch")

    target = p.get("target", {})
    if target.get("file") != "CURRENT_STATE.json":
        errors.append("target_file_mismatch")
    if target.get("json_pointer") != "/broker_plane/registry_mutation_rule":
        errors.append("target_pointer_mismatch")
    if target.get("field_scope_count") != 1:
        errors.append("repair_must_be_one_field")
    if target.get("current_value") != EXPECTED_CURRENT_VALUE:
        errors.append("current_value_mismatch")

    repair = p.get("repair", {})
    if repair.get("proposed_value") != EXPECTED_PROPOSED_VALUE:
        errors.append("proposed_value_mismatch")
    patch = repair.get("json_patch")
    if not isinstance(patch, list) or len(patch) != 2:
        errors.append("json_patch_shape_mismatch")
    else:
        if patch[0] != {"op": "test", "path": "/broker_plane/registry_mutation_rule", "value": EXPECTED_CURRENT_VALUE}:
            errors.append("json_patch_test_mismatch")
        if patch[1] != {"op": "replace", "path": "/broker_plane/registry_mutation_rule", "value": EXPECTED_PROPOSED_VALUE}:
            errors.append("json_patch_replace_mismatch")
    for key in ("changes_runtime_state", "changes_routing", "changes_effect_authority", "changes_execution_authority", "changes_trading_authority"):
        if repair.get(key) is not False:
            errors.append(f"repair_authority_or_runtime_leak::{key}")

    evidence = p.get("evidence", {})
    df6 = evidence.get("df6_runtime_receipt", {})
    if df6.get("terminal") != "DF6_RUNTIME_DEPLOY_PASS" or df6.get("generation") != "R59":
        errors.append("df6_evidence_mismatch")
    if df6.get("stable_root_mutation") is not False:
        errors.append("df6_stable_root_mutation_claim_mismatch")
    if [df6.get("generation_registry_jsonl"), df6.get("generation_registry_projection"), df6.get("generation_live_index")] != [
        "R59/MASTER_RETURN_REGISTRY_R59.jsonl", "R59/MASTER_RETURN_REGISTRY_R59.json", "R59/LIVE_INDEX_R59.json"
    ]:
        errors.append("generation_scoped_paths_mismatch")

    d1 = evidence.get("d1_registration_receipt", {})
    if d1.get("operation") != "BROKER_OWNED_SLOT_REGISTRATION" or d1.get("physical_status") != "DELIVERY_VERIFIED":
        errors.append("d1_evidence_mismatch")
    if d1.get("direct_current_return_registry_edit") is not False or d1.get("semantic_acceptance_claimed") is not False:
        errors.append("d1_authority_or_stable_registry_mismatch")

    stable = evidence.get("stable_return_registry", {})
    if stable.get("drive_file_id") != "1BXdqWzA74SvkgcygO_ktO_2uolqFshWm":
        errors.append("stable_registry_id_mismatch")
    if stable.get("observed_sha256") != "ea0ff88fce2d02f664087ea2697e71688ad95cb6deb65e22df73af2081dfb03f":
        errors.append("stable_registry_sha_mismatch")
    if stable.get("unchanged_by_r59_df6_observation") is not True:
        errors.append("stable_registry_unchanged_evidence_missing")

    gate = p.get("gate", {})
    if gate.get("proposal_applied") is not False or gate.get("root_bytes_mutated") is not False:
        errors.append("proposal_must_not_be_applied")
    if gate.get("required_gate_class") != "SEPARATE_EXPLICIT_CANONICAL_SEMANTIC_REPAIR_GATE":
        errors.append("gate_class_mismatch")
    if gate.get("exact_authorization_phrase") != EXPECTED_GATE:
        errors.append("exact_gate_phrase_mismatch")
    if gate.get("generic_go_is_authorization") is not False or gate.get("auto_apply") is not False or gate.get("self_application") is not False:
        errors.append("gate_authority_leak")

    safety = p.get("safety", {})
    for key in ("no_live_root_write", "no_return_registry_mutation", "no_runtime_mutation", "no_agent_dispatch", "no_external_message"):
        if safety.get(key) is not True:
            errors.append(f"safety_missing::{key}")
    if safety.get("can_trade") is not False or safety.get("capital_permission") != "DENY" or safety.get("deploy_permission") != "DENY":
        errors.append("safety_ceiling_mismatch")
    return errors


def adversarial_cases(base: dict) -> list[str]:
    failures: list[str] = []
    cases = []

    bad = copy.deepcopy(base); bad["target"]["field_scope_count"] = 2; cases.append(("scope_expansion", bad))
    bad = copy.deepcopy(base); bad["target"]["json_pointer"] = "/broker_plane/status"; cases.append(("wrong_target", bad))
    bad = copy.deepcopy(base); bad["gate"]["proposal_applied"] = True; cases.append(("silent_apply", bad))
    bad = copy.deepcopy(base); bad["gate"]["generic_go_is_authorization"] = True; cases.append(("generic_go_authority", bad))
    bad = copy.deepcopy(base); bad["evidence"]["d1_registration_receipt"]["direct_current_return_registry_edit"] = True; cases.append(("invent_stable_registry_edit", bad))
    bad = copy.deepcopy(base); bad["repair"]["changes_runtime_state"] = True; cases.append(("runtime_scope_leak", bad))
    bad = copy.deepcopy(base); bad["repair"]["changes_effect_authority"] = True; cases.append(("effect_authority_leak", bad))
    bad = copy.deepcopy(base); bad["authority_anchor"]["current_state_sha256"] = "0" * 64; cases.append(("anchor_tamper", bad))
    bad = copy.deepcopy(base); bad["repair"]["json_patch"][0]["op"] = "replace"; cases.append(("missing_test_guard", bad))
    bad = copy.deepcopy(base); bad["gate"]["exact_authorization_phrase"] = "го"; cases.append(("unsafe_gate_phrase", bad))

    for name, candidate in cases:
        if not validate(candidate):
            failures.append(name)
    return failures


def main() -> int:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    errors = validate(proposal)
    adversarial_failures = adversarial_cases(proposal)
    if adversarial_failures:
        errors.append("adversarial_not_rejected::" + ",".join(adversarial_failures))
    out = {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "proposal_applied": proposal.get("gate", {}).get("proposal_applied"),
        "target": proposal.get("target", {}).get("json_pointer"),
        "exact_authorization_phrase": proposal.get("gate", {}).get("exact_authorization_phrase"),
        "adversarial_cases": 10,
    }
    print(json.dumps(out, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
