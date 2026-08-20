#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "data" / "canonical_reseal_proposal.generated.v1.json"

EXPECTED = {
    "schema": "control_center.canonical_reseal_proposal.v1",
    "projection_kind": "NON_AUTHORITY_REVIEW_ONLY_PROPOSAL",
    "state_sha": "701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68",
    "state_bytes": 6506,
    "old_manifest_sha": "41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d",
    "old_pointer_sha": "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef",
    "manifest_sha": "383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d",
    "manifest_bytes": 1328,
    "pointer_sha": "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3",
    "pointer_bytes": 5493,
    "gate": "APPLY_R64_CANONICAL_RESEAL_V1__MANIFEST_383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d",
}

def canonical_bytes(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")

def require(cond, code):
    if not cond:
        raise ValueError(code)

def validate(doc):
    require(doc.get("schema") == EXPECTED["schema"], "schema_mismatch")
    require(doc.get("projection_kind") == EXPECTED["projection_kind"], "projection_kind_mismatch")

    ci = doc["current_integrity"]
    require(ci["status"] == "AUTHORIZED_ROOT_REPAIR_APPLIED_RESEAL_REQUIRED", "wrong_current_integrity_status")
    require(ci["current_all_exact"] is False, "current_all_exact_must_be_false_pre_reseal")
    require(ci["current_state"] == {
        "bytes": EXPECTED["state_bytes"],
        "drive_file_id": "10w_2sw2Sl2I5SNe3aY9jqS46u0muvYs_",
        "sha256": EXPECTED["state_sha"],
    }, "current_state_anchor_mismatch")
    require(ci["current_manifest"]["sha256"] == EXPECTED["old_manifest_sha"], "old_manifest_anchor_mismatch")
    require(ci["current_pointer"]["sha256"] == EXPECTED["old_pointer_sha"], "old_pointer_anchor_mismatch")

    gate = doc["future_gate"]
    require(gate["required_gate_class"] == "SEPARATE_EXPLICIT_CANONICAL_RESEAL_GATE", "gate_class_mismatch")
    require(gate["exact_authorization_phrase"] == EXPECTED["gate"], "gate_phrase_mismatch")
    require(gate["generic_go_is_authorization"] is False, "generic_go_authority_forbidden")
    require(gate["proposal_applied"] is False, "proposal_must_not_be_applied")
    require(gate["auto_apply"] is False, "auto_apply_forbidden")
    require(gate["self_application"] is False, "self_application_forbidden")

    manifest = doc["candidates"]["manifest"]
    pointer = doc["candidates"]["pointer"]
    mb = canonical_bytes(manifest["content_object"])
    pb = canonical_bytes(pointer["content_object"])
    require(len(mb) == manifest["bytes"] == EXPECTED["manifest_bytes"], "manifest_bytes_mismatch")
    require(hashlib.sha256(mb).hexdigest() == manifest["sha256"] == EXPECTED["manifest_sha"], "manifest_sha_mismatch")
    require(len(pb) == pointer["bytes"] == EXPECTED["pointer_bytes"], "pointer_bytes_mismatch")
    require(hashlib.sha256(pb).hexdigest() == pointer["sha256"] == EXPECTED["pointer_sha"], "pointer_sha_mismatch")

    m = manifest["content_object"]
    require(m["schema"] == "CONTROL_CANTER_R64_RESEAL_MANIFEST_V1", "manifest_schema_mismatch")
    require(m["generation"] == "R64" and m["base_generation"] == "R64", "manifest_generation_mismatch")
    require(m["apply_status"] == "RESEAL_CANDIDATE_NOT_APPLIED", "manifest_apply_status_mismatch")
    require(m["original_manifest_sha256"] == EXPECTED["old_manifest_sha"], "manifest_history_binding_mismatch")
    require(m["repair"]["authorization_phrase"] == "APPLY_R64_BROKER_MUTATION_RULE_REPAIR_V1", "repair_gate_binding_mismatch")
    require(m["repair"]["authorized_scope"] == "/broker_plane/registry_mutation_rule", "repair_scope_mismatch")
    require(m["repair"]["semantic_only"] is True, "repair_semantic_only_required")
    file_map = {x["path"]: x for x in m["files"]}
    require(set(file_map) == {"CURRENT_STATE.json", "ROLE_INDEX.json", "ROLE_VIEWS.json"}, "manifest_file_set_mismatch")
    require(file_map["CURRENT_STATE.json"] == {"bytes": EXPECTED["state_bytes"], "path": "CURRENT_STATE.json", "sha256": EXPECTED["state_sha"]}, "manifest_state_binding_mismatch")

    p = pointer["content_object"]
    require(p["schema"] == "CONTROL_CURRENT_POINTER_R64", "pointer_schema_mismatch")
    require(p["generation"] == "R64", "pointer_generation_mismatch")
    require(p["current_state"]["sha256"] == EXPECTED["state_sha"] and p["current_state"]["bytes"] == EXPECTED["state_bytes"], "pointer_state_binding_mismatch")
    require(p["manifest"]["sha256"] == EXPECTED["manifest_sha"] and p["manifest"]["size_bytes"] == EXPECTED["manifest_bytes"], "pointer_manifest_binding_mismatch")
    require(p["canonical_activation"]["status"] == "HISTORICAL_PRE_REPAIR_ACTIVATION", "original_activation_not_historical")
    rb = p["canonical_activation"]["stable_root_provider_readback"]
    require(rb["all_exact_at_original_promotion"] is True and rb["current_status"] == "HISTORICAL_PRE_REPAIR_ONLY", "historical_readback_not_scoped")
    cr = p["canonical_reseal"]
    require(cr["accepted_reseal_manifest_sha256"] == EXPECTED["manifest_sha"], "reseal_manifest_binding_mismatch")
    require(cr["decision"] == EXPECTED["gate"], "reseal_gate_binding_mismatch")
    require(cr["post_write_provider_readback_required"] is True, "provider_readback_required")
    require(cr["status"] == "ACTIVE_RESEALED_AFTER_EXACT_PROVIDER_READBACK", "reseal_status_mismatch")

    scope = doc["authorized_future_write_scope"]
    writes = scope["drive_writes_exactly"]
    require(len(writes) == 2, "write_scope_must_be_exactly_two")
    require([x["file"] for x in writes] == ["MANIFEST.json", "CURRENT_POINTER.json"], "write_order_mismatch")
    require(writes[0]["order"] == 1 and writes[1]["order"] == 2, "write_order_numbers_mismatch")
    require(writes[1].get("must_be_last_stable_root_write") is True, "pointer_must_be_last")
    forbidden = set(scope["must_not_write"])
    for name in ["CURRENT_STATE.json", "ROLE_INDEX.json", "ROLE_VIEWS.json", "CURRENT_RETURN_REGISTRY.json", "R64_POINTER_PROMOTION_RECEIPT.json", "R64_STABLE_ROOT_PROVIDER_READBACK_20260808.json"]:
        require(name in forbidden, "missing_forbidden_write:" + name)
    for flag in ["runtime_mutation", "routing_mutation", "effect_authority_change", "execution_authority_change", "trading_authority_change", "deploy_authority_change"]:
        require(scope[flag] is False, "authority_or_runtime_leak:" + flag)

    pre = doc["preconditions"]
    require(pre["on_any_mismatch"] == "ABORT_NO_WRITE", "precondition_failure_policy_mismatch")
    require(pre["current_state_must_match"] == {"bytes": EXPECTED["state_bytes"], "sha256": EXPECTED["state_sha"]}, "precondition_state_mismatch")
    require(pre["current_manifest_must_match"]["sha256"] == EXPECTED["old_manifest_sha"], "precondition_manifest_mismatch")
    require(pre["current_pointer_must_match"]["sha256"] == EXPECTED["old_pointer_sha"], "precondition_pointer_mismatch")

    post = doc["post_write_readback"]
    require(post["required"] is True, "post_write_readback_required")
    require(post["files"] == ["CURRENT_STATE.json", "ROLE_INDEX.json", "ROLE_VIEWS.json", "MANIFEST.json", "CURRENT_POINTER.json"], "post_readback_file_order_mismatch")
    require(post["expected"]["MANIFEST.json"] == {"bytes": EXPECTED["manifest_bytes"], "sha256": EXPECTED["manifest_sha"]}, "post_manifest_expectation_mismatch")
    require(post["expected"]["CURRENT_POINTER.json"] == {"bytes": EXPECTED["pointer_bytes"], "sha256": EXPECTED["pointer_sha"]}, "post_pointer_expectation_mismatch")
    require(post["all_exact_rule"] == "TRUE_ONLY_IF_ALL_FIVE_PROVIDER_READBACKS_MATCH_EXACT_BYTES_AND_SHA", "all_exact_rule_mismatch")
    require(post["on_failure"] == "DO_NOT_CLAIM_RESEALED_OR_ALL_EXACT; STOP_FOR_HUMAN_REPAIR", "readback_failure_policy_mismatch")

    hist = doc["historical_binding"]
    require(hist["historical_receipts_mutated"] is False, "historical_receipts_mutation_forbidden")
    require(hist["original_manifest_sha256"] == EXPECTED["old_manifest_sha"], "historical_manifest_binding_mismatch")
    require(hist["original_provider_readback_status"] == "HISTORICAL_PRE_REPAIR_ONLY", "historical_provider_status_mismatch")

    hp = doc["history_preservation"]
    require(hp["historical_receipts_remain_unchanged"] is True, "historical_receipts_must_remain")
    require(hp["manifest_existing_revision_observed"] is True, "manifest_revision_evidence_required")
    require(hp["pointer_existing_revision_observed"] is True, "pointer_revision_evidence_required")

    safety = doc["safety"]
    require(safety["no_drive_write_in_this_proposal"] is True, "proposal_drive_write_forbidden")
    require(safety["no_return_registry_mutation"] is True, "registry_mutation_forbidden")
    require(safety["no_runtime_mutation"] is True, "runtime_mutation_forbidden")
    require(safety["no_agent_dispatch"] is True, "agent_dispatch_forbidden")
    require(safety["no_external_message"] is True, "external_message_forbidden")
    require(safety["can_trade"] is False and safety["capital_permission"] == "DENY" and safety["deploy_permission"] == "DENY", "effect_ceiling_mismatch")
    return True

def main():
    doc = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    validate(doc)
    print("CANONICAL_RESEAL_PROPOSAL_V1_PASS")

if __name__ == "__main__":
    main()
