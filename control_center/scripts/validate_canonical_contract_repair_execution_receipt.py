import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "data" / "canonical_contract_repair_execution_receipt.generated.v1.json"
PROPOSAL = ROOT / "data" / "canonical_contract_repair_proposal.generated.v1.json"

EXPECTED_GATE = "APPLY_R64_BROKER_MUTATION_RULE_REPAIR_V1"
EXPECTED_BEFORE_SHA = "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd"
EXPECTED_AFTER_SHA = "701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68"
EXPECTED_POINTER_SHA = "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef"
EXPECTED_MANIFEST_SHA = "41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d"


def require(cond, msg):
    if not cond:
        raise SystemExit(msg)


def main():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))

    require(receipt["schema"] == "control_center.canonical_contract_repair_execution_receipt.v1", "wrong receipt schema")
    require(receipt["authority"]["exact_authorization_phrase"] == EXPECTED_GATE, "wrong human gate")
    require(receipt["authority"]["generic_go_is_authorization"] is False, "generic go must not authorize")
    require(receipt["target"]["file"] == "CURRENT_STATE.json", "wrong target file")
    require(receipt["target"]["json_pointer"] == "/broker_plane/registry_mutation_rule", "wrong target pointer")
    require(receipt["target"]["field_scope_count"] == 1, "scope expansion")
    require(receipt["before"]["sha256"] == EXPECTED_BEFORE_SHA, "wrong before sha")
    require(receipt["after"]["sha256"] == EXPECTED_AFTER_SHA, "wrong after sha")
    require(receipt["provider_readback"]["readback_sha256"] == EXPECTED_AFTER_SHA, "provider readback mismatch")
    require(receipt["provider_readback"]["exact_candidate_match"] is True, "provider readback not exact")
    require(receipt["after"]["value"] == proposal["repair"]["proposed_value"], "receipt/proposal semantic mismatch")
    require(receipt["before"]["value"] == proposal["target"]["current_value"], "receipt/proposal old-value mismatch")

    integrity = receipt["canonical_integrity_after_write"]
    require(integrity["status"] == "AUTHORIZED_ROOT_REPAIR_APPLIED_RESEAL_REQUIRED", "wrong integrity status")
    require(integrity["current_pointer_sha256"] == EXPECTED_POINTER_SHA, "pointer sha mismatch")
    require(integrity["manifest_sha256"] == EXPECTED_MANIFEST_SHA, "manifest sha mismatch")
    require(integrity["pointer_bound_current_state_sha256"] == EXPECTED_BEFORE_SHA, "pointer stale binding not recorded")
    require(integrity["manifest_bound_current_state_sha256"] == EXPECTED_BEFORE_SHA, "manifest stale binding not recorded")
    require(integrity["current_all_exact"] is False, "must fail closed: current all_exact cannot be true")
    require(integrity["pointer_mutated_by_this_gate"] is False, "pointer mutation outside gate")
    require(integrity["manifest_mutated_by_this_gate"] is False, "manifest mutation outside gate")
    require(integrity["stable_root_readback_mutated_by_this_gate"] is False, "historical readback mutation outside gate")

    write = receipt["provider_write"]
    require(write["success"] is True, "write not successful")
    require(write["same_drive_file_id_preserved"] is True, "stable file id changed")
    require(write["idempotent_duplicate_uploads_after_first"] == 7, "duplicate upload count must stay explicit")
    require(write["content_changed_only_on_first_successful_upload"] is True, "duplicate upload semantics hidden")

    boundary = receipt["effect_boundary"]
    for key in ["return_registry_mutated", "runtime_mutated", "routing_changed", "agent_dispatch", "external_message_sent", "merge", "deploy", "can_trade"]:
        require(boundary[key] is False, f"forbidden authority/effect leakage: {key}")
    require(boundary["capital_permission"] == "DENY", "capital permission changed")
    require(receipt["next"]["automatic_reseal_authorized"] is False, "automatic reseal forbidden")
    require(receipt["next"]["action"] == "PREPARE_CANONICAL_RESEAL_PROPOSAL_V1", "wrong next action")

    print("CANONICAL_CONTRACT_REPAIR_EXECUTION_RECEIPT_PASS")


if __name__ == "__main__":
    main()
