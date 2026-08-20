from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from current_authority_anchor import append_anchor_errors

SCHEMA = "control_center.human_gate_packets.v1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_anchor(name: str, source: dict[str, Any], errors: list[str]) -> None:
    append_anchor_errors(name, source.get("authority_anchor", {}), errors)


def response_contract(response: str) -> dict[str, Any]:
    if response == "AUTHORIZE_APPLY":
        return {
            "response": response,
            "effect_authority_result": "BOUNDED_EFFECT_AUTHORIZATION_FOR_PACKET_SCOPE_ONLY",
            "execution_authority_result": "NOT_GRANTED",
            "apply_state_result": "NOT_APPLIED_UNTIL_EXECUTION_AND_READBACK",
            "next_required": ["BIND_EXACT_EXECUTION_SCOPE","BIND_EXECUTOR","SEPARATE_EXECUTION_AUTHORIZATION","EXECUTION_RECEIPT","POST_EFFECT_READBACK_RECEIPT"],
            "does_not_authorize": ["EXECUTION","DEPLOY","TRADING","CAPITAL_USE","EXTERNAL_MESSAGE","UNRELATED_EFFECT","SELF_APPLICATION"],
        }
    if response == "HOLD":
        return {"response":response,"effect_authority_result":"NOT_GRANTED","execution_authority_result":"NOT_GRANTED","apply_state_result":"NOT_APPLIED","next_required":["LATER_EXPLICIT_BOUNDED_HUMAN_DECISION"],"does_not_authorize":["EFFECT","EXECUTION","APPLY","DEPLOY","TRADING","CAPITAL_USE","EXTERNAL_MESSAGE"]}
    if response == "REJECT_EFFECT":
        return {"response":response,"effect_authority_result":"DENIED_FOR_THIS_PACKET_PROPOSAL","execution_authority_result":"NOT_GRANTED","apply_state_result":"NOT_APPLIED","semantic_acceptance_result":"UNCHANGED_ACCEPTED_RETURN","next_required":["SEPARATE_SUCCESSOR_PROPOSAL_IF_REVISITED"],"does_not_authorize":["EFFECT","EXECUTION","APPLY","DEPLOY","TRADING","CAPITAL_USE","EXTERNAL_MESSAGE"]}
    raise ValueError(f"unsupported_human_response::{response}")


def build(command_queue: dict[str, Any], lifecycle: dict[str, Any], ledger: dict[str, Any], effect: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    expected_schemas = {"command_queue":"control_center.command_queue.v1","lifecycle":"control_center.work_order_lifecycle.v1","ledger":"control_center.decision_effect_ledger.v1","effect":"control_center.effect_readback_plane.v1"}
    sources = {"command_queue":command_queue,"lifecycle":lifecycle,"ledger":ledger,"effect":effect}
    for name, source in sources.items():
        if source.get("schema") != expected_schemas[name]: errors.append(f"{name}_schema_mismatch")
        validate_anchor(name, source, errors)

    queue_policy=command_queue.get("policy",{}); ledger_policy=ledger.get("policy",{}); effect_policy=effect.get("policy",{}); lifecycle_policy=lifecycle.get("global_policy",{})
    if queue_policy.get("queue_grants_authority") is not False: errors.append("command_queue_authority_leak")
    for key in ("auto_dispatch","auto_accept","auto_apply","auto_execute","self_approval","self_application"):
        if queue_policy.get(key) is not False: errors.append(f"command_queue_{key}_forbidden")
    if ledger_policy.get("effect_authorization_executes_effect") is not False: errors.append("ledger_effect_executes_forbidden")
    if effect_policy.get("receipt_never_grants_authority") is not True: errors.append("receipt_authority_rule_missing")
    if effect_policy.get("execution_requires_explicit_authorization") is not True: errors.append("explicit_execution_authority_rule_missing")
    if effect_policy.get("closure_requires_readback") is not True: errors.append("closure_readback_rule_missing")
    if lifecycle_policy.get("auto_apply") is not False: errors.append("lifecycle_auto_apply_forbidden")

    lifecycle_by_work={str(x.get("work_order")):x for x in lifecycle.get("work_orders",[]) if x.get("work_order")}
    decisions_by_id={str(x.get("decision_id")):x for x in ledger.get("decisions",[]) if x.get("decision_id")}
    effects_by_decision={str(x.get("decision_id")):x for x in effect.get("effect_candidates",[]) if x.get("decision_id")}
    queue_human_ids=list(command_queue.get("queues",{}).get("HUMAN_NOW",[]))
    queue_human_rows={str(x.get("command_id")):x for x in command_queue.get("human_now",[]) if x.get("command_id")}
    if set(queue_human_ids)!=set(queue_human_rows): errors.append("human_now_queue_detail_mismatch")
    if len(queue_human_ids)>int(queue_policy.get("max_human_now",0)): errors.append("human_now_exceeds_max")

    packets=[]
    for command_id in queue_human_ids:
        command=queue_human_rows.get(command_id)
        if not command: errors.append(f"human_now_detail_missing::{command_id}"); continue
        decision_id=str(command.get("decision_id")); work_order=str(command.get("work_order")); decision=decisions_by_id.get(decision_id); life=lifecycle_by_work.get(work_order); eff=effects_by_decision.get(decision_id)
        if not decision: errors.append(f"decision_missing::{decision_id}"); continue
        if not life: errors.append(f"lifecycle_missing::{work_order}"); continue
        if not eff: errors.append(f"effect_candidate_missing::{decision_id}"); continue
        if decision.get("decision_state")!="OPEN" or decision.get("human_ripe") is not True: errors.append(f"decision_not_ripe::{decision_id}")
        if decision.get("owner")!="ROBERT" or decision.get("decision_class")!="HUMAN_EFFECT_AUTHORIZATION": errors.append(f"human_gate_class_or_owner_mismatch::{decision_id}")
        if decision.get("decision_outcome") is not None: errors.append(f"decision_already_resolved::{decision_id}")
        if decision.get("effect_authorized") is not False or decision.get("execution_authorized") is not False: errors.append(f"unexpected_decision_authority::{decision_id}")
        if life.get("semantic_status")!="ACCEPTED" or life.get("apply_status")!="NOT_APPLIED": errors.append(f"lifecycle_not_accepted_unapplied::{work_order}")
        if life.get("lifecycle_stage")!="EFFECT_GATE_WAIT": errors.append(f"lifecycle_not_effect_gate_wait::{work_order}")
        if eff.get("stage")!="AWAITING_HUMAN_EFFECT_AUTHORIZATION": errors.append(f"effect_stage_not_waiting_human::{decision_id}")
        if eff.get("effect_authorized") is not False or eff.get("execution_authorized") is not False: errors.append(f"effect_authority_already_present::{decision_id}")
        if eff.get("execution_receipt_id") is not None or eff.get("readback_receipt_id") is not None: errors.append(f"unexpected_effect_receipt::{decision_id}")
        if command.get("authority_granted") is not False or command.get("auto_execute") is not False: errors.append(f"command_authority_leak::{command_id}")
        allowed=list(decision.get("allowed_decisions",[]))
        if allowed!=list(command.get("allowed_decisions",[])): errors.append(f"allowed_decision_mismatch::{decision_id}")
        try: response_contracts=[response_contract(str(x)) for x in allowed]
        except ValueError as exc: errors.append(str(exc)); continue
        gate=str(decision.get("gate")); return_id=life.get("return_id")
        packets.append({
            "packet_id":f"HGP::{work_order}::{gate}","status":"OPEN_HUMAN_DECISION_REQUIRED","command_id":command_id,"decision_id":decision_id,"work_order":work_order,"return_id":return_id,"project":decision.get("project"),"slot":decision.get("slot"),"gate":gate,"authority_required":decision.get("authority_required"),
            "current_state":{"transport":life.get("transport_status"),"semantic":life.get("semantic_status"),"apply":life.get("apply_status"),"lifecycle_stage":life.get("lifecycle_stage"),"effect_stage":eff.get("stage"),"effect_authorized":False,"execution_authorized":False,"execution_receipt":None,"readback_receipt":None},
            "evidence_bindings":[
                {"source":"COMMAND_QUEUE","schema":command_queue.get("schema"),"path":"control_center/data/command_queue.generated.v1.json","identity":command_id,"claims":["HUMAN_NOW","authority_granted=false","auto_execute=false"]},
                {"source":"WORK_ORDER_LIFECYCLE","schema":lifecycle.get("schema"),"path":"control_center/data/work_order_lifecycle.generated.v1.json","identity":work_order,"claims":[f"transport={life.get('transport_status')}",f"semantic={life.get('semantic_status')}",f"apply={life.get('apply_status')}",f"return_id={return_id}"]},
                {"source":"DECISION_EFFECT_LEDGER","schema":ledger.get("schema"),"path":"control_center/data/decision_effect_ledger.generated.v1.json","identity":decision_id,"claims":[f"owner={decision.get('owner')}",f"class={decision.get('decision_class')}",f"gate={gate}","effect_authorized=false","execution_authorized=false"]},
                {"source":"EFFECT_READBACK","schema":effect.get("schema"),"path":"control_center/data/effect_readback_plane.generated.v1.json","identity":decision_id,"claims":[f"stage={eff.get('stage')}","execution_receipt=null","readback_receipt=null"]}
            ],
            "effect_scope":{"scope_id":f"APPLY::{work_order}","scope_statement":f"Apply/migration effect represented by {gate} for {work_order} only","identity_bound":True,"operation_details_bound":False,"provider_target_bound":False,"mutation_set_bound":False,"execution_ready":False,"readiness_blockers":["EXACT_EXECUTION_OPERATION_NOT_SOURCE_BOUND","EXECUTOR_NOT_SOURCE_BOUND","EXECUTION_AUTHORIZATION_NOT_GRANTED"]},
            "allowed_responses":response_contracts,
            "executor_binding":{"state":"UNBOUND_REQUIRES_SEPARATE_BINDING","executor":None,"binding_grants_execution_authority":False},
            "execution_contract":{"separate_execution_authorization_required":True,"execution_receipt_required":True,"required_receipt_fields":["packet_id","decision_id","work_order","executor_identity","exact_effect_scope","executed_at","result","provider_or_object_identifiers"]},
            "readback_contract":{"post_effect_readback_required":True,"independent_binding_to_execution_receipt_required":True,"required_receipt_fields":["packet_id","decision_id","work_order","execution_receipt_id","readback_at","provider_current_state","verification_result"],"closure_before_verified_readback":False},
            "forbidden_implications":["PACKET_IS_NOT_AUTHORITY","GENERIC_CONTINUATION_IS_NOT_EFFECT_AUTHORIZATION","SEMANTIC_ACCEPTED_DOES_NOT_IMPLY_APPLY","EFFECT_AUTHORIZATION_DOES_NOT_IMPLY_EXECUTION_AUTHORIZATION","EXECUTION_AUTHORIZATION_DOES_NOT_PROVE_EXECUTION","EXECUTION_RECEIPT_DOES_NOT_PROVE_READBACK","NO_CLOSURE_WITHOUT_VERIFIED_POST_EFFECT_READBACK","NO_SELF_APPROVAL","NO_SELF_APPLICATION"]
        })
    if errors: raise ValueError(";".join(errors))
    return {
        "schema":SCHEMA,"projection_kind":"NON_AUTHORITY_PROJECTION","observed_at":command_queue.get("observed_at"),"authority_anchor":command_queue.get("authority_anchor"),
        "policy":{"packet_grants_authority":False,"generic_continuation_is_authorization":False,"effect_authorization_executes_effect":False,"executor_binding_grants_execution_authority":False,"receipt_grants_authority":False,"auto_apply":False,"auto_execute":False,"self_approval":False,"self_application":False,"can_trade":False,"capital_permission":"DENY","deploy_permission":"DENY","external_messages":"DENY_WITHOUT_EXACT_SEPARATE_SEND"},
        "summary":{"human_now_commands":len(queue_human_ids),"packets_total":len(packets),"open_packets":sum(1 for x in packets if x["status"]=="OPEN_HUMAN_DECISION_REQUIRED"),"execution_ready_packets":sum(1 for x in packets if x["effect_scope"]["execution_ready"]),"effects_authorized":0,"executions_authorized":0,"execution_receipts":0,"readback_receipts":0},
        "packets":packets,
        "invariants":{"one_packet_per_human_now_command":True,"packet_never_grants_authority":True,"executor_never_invented":True,"execution_requires_separate_authority":True,"closure_requires_verified_readback":True}
    }


def main() -> int:
    parser=argparse.ArgumentParser(description="Build Human Gate Packet V1 from current Control Center projections.")
    parser.add_argument("command_queue",type=Path); parser.add_argument("lifecycle",type=Path); parser.add_argument("ledger",type=Path); parser.add_argument("effect",type=Path); parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try: output=build(load(args.command_queue),load(args.lifecycle),load(args.ledger),load(args.effect))
    except ValueError as exc:
        print(json.dumps({"status":"FAIL","errors":str(exc).split(";")},indent=2)); return 2
    rendered=json.dumps(output,ensure_ascii=False,indent=2)+"\n"
    if args.output: args.output.write_text(rendered,encoding="utf-8")
    else: print(rendered,end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
