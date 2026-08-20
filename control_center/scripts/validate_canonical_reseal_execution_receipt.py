#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "data" / "canonical_reseal_execution_receipt.generated.v1.json"

EXPECTED_GATE = "APPLY_R64_CANONICAL_RESEAL_V1__MANIFEST_383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d"
EXPECTED = {
    "CURRENT_STATE.json": (6506, "701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68"),
    "ROLE_INDEX.json": (2043, "e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567"),
    "ROLE_VIEWS.json": (3945, "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148"),
    "MANIFEST.json": (1328, "383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d"),
    "CURRENT_POINTER.json": (5493, "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3"),
}

def require(cond, code):
    if not cond:
        raise ValueError(code)

def main():
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(doc.get("schema") == "control_center.canonical_reseal_execution_receipt.v1", "schema")
    require(doc.get("projection_kind") == "EVIDENCE_RECEIPT_NON_AUTHORITY", "projection_kind")
    require(doc["human_gate"]["decision"] == EXPECTED_GATE, "gate")
    require(doc["human_gate"]["binding"] == "EXACT", "binding")
    require(doc["human_gate"]["accepted_manifest_sha256"] == EXPECTED["MANIFEST.json"][1], "manifest_binding")
    require(doc["preconditions"]["all_exact"] is True, "preconditions_not_exact")
    writes = doc["writes"]
    require([x["file"] for x in writes] == ["MANIFEST.json", "CURRENT_POINTER.json"], "write_order")
    require(writes[0]["order"] == 1 and writes[1]["order"] == 2, "write_numbers")
    require(writes[1].get("last_stable_root_write") is True, "pointer_not_last")
    require(writes[0]["after"] == {"bytes": EXPECTED["MANIFEST.json"][0], "sha256": EXPECTED["MANIFEST.json"][1]}, "manifest_after")
    require(writes[1]["after"] == {"bytes": EXPECTED["CURRENT_POINTER.json"][0], "sha256": EXPECTED["CURRENT_POINTER.json"][1]}, "pointer_after")
    rb = doc["post_write_provider_readback"]
    require(rb["required"] is True and rb["all_exact"] is True, "readback_not_exact")
    for name, (size, sha) in EXPECTED.items():
        require(rb["files"][name] == {"bytes": size, "sha256": sha, "exact_match": True}, "readback_mismatch:" + name)
    result = doc["canonical_result"]
    require(result["status"] == "R64_RESEALED_ALL_EXACT", "status")
    require(result["current_all_exact"] is True, "all_exact_false")
    require(result["manifest_sha256"] == EXPECTED["MANIFEST.json"][1], "manifest_result")
    require(result["pointer_sha256"] == EXPECTED["CURRENT_POINTER.json"][1], "pointer_result")
    require(result["original_promotion_evidence_status"] == "HISTORICAL_PRE_REPAIR_ONLY", "history_scope")
    require(doc["ready_marker"]["written_in_reseal"] is False, "unauthorized_ready_write")
    boundary = doc["scope_boundary"]
    for key in ["CURRENT_STATE_written","ROLE_INDEX_written","ROLE_VIEWS_written","CURRENT_RETURN_REGISTRY_written","historical_promotion_receipt_written","historical_provider_readback_written","runtime_mutation","routing_mutation","agent_dispatch","external_message","merge","deploy","trading","capital_effect","self_application"]:
        require(boundary[key] is False, "scope_leak:" + key)
    ceiling = doc["effect_ceiling"]
    require(ceiling["NO_FURTHER_AGENT_WORK"] is True, "agent_ceiling")
    require(ceiling["can_trade"] is False and ceiling["capital_permission"] == "DENY" and ceiling["deploy"] == "DENY", "effect_ceiling")
    print("CANONICAL_RESEAL_EXECUTION_RECEIPT_V1_PASS")

if __name__ == "__main__":
    main()
