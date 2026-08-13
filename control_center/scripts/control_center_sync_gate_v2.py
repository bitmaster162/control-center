#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

REQUIRED_SURFACES = {
    "r64.authority","hanri.runtime","hanri.repository","hanri.projection",
    "collaboration.raw4ik","continuityos.repository","visionassist.custody",
}
RANK = {
    "authority":{"human_decision":300,"stable_authority_root":250,"control_receipt":200},
    "control_truth":{"stable_authority_root":300,"control_receipt":250,"provider_read":200},
    "repository":{"github_provider":300,"verified_bundle":250,"strict_return":200,"owner_narrative":50},
    "runtime":{"host_readback":300,"operator_terminal_receipt":250,"slot_receipt":200},
    "projection":{"provider_read":300,"control_receipt":280,"github_provider":260,"operator_terminal_receipt":240,"verified_bundle":180},
}
ALLOWED = {
    "authority":{"human_decision","stable_authority_root","control_receipt"},
    "control_truth":{"stable_authority_root","control_receipt","provider_read"},
    "repository":{"github_provider","verified_bundle","strict_return","owner_narrative"},
    "runtime":{"host_readback","operator_terminal_receipt","slot_receipt"},
    "projection":{"provider_read","control_receipt","github_provider","host_readback","operator_terminal_receipt","slot_receipt","role_readback","verified_bundle"},
}
REQUIRED_FIELDS = {
    "semantic_surface","claim_dimension","source_class","source_id","source_scope",
    "observed_at","identity","freshness","claim_ceiling","effect_authority","payload",
}

def ts(s:str):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def normalize(raw:list[dict[str,Any]]) -> list[dict[str,Any]]:
    seen={}
    out=[]
    for x in raw:
        miss=REQUIRED_FIELDS-set(x)
        if miss: raise ValueError("MISSING_FIELDS:"+",".join(sorted(miss)))
        if x["source_class"] not in ALLOWED.get(x["claim_dimension"],set()):
            raise ValueError("SOURCE_NOT_ALLOWED:"+x["semantic_surface"])
        if x["effect_authority"]!="NONE" and x["claim_dimension"]!="authority":
            raise ValueError("EFFECT_AUTHORITY_OUT_OF_DIMENSION")
        ts(x["observed_at"])
        prior=seen.get(x["source_id"])
        if prior is not None and prior!=x["identity"]:
            raise ValueError("SOURCE_ID_REUSED_WITH_DIFFERENT_IDENTITY:"+x["source_id"])
        seen[x["source_id"]]=x["identity"]
        out.append(deepcopy(x))
    return out

def select(obs:list[dict[str,Any]], surface:str) -> tuple[dict[str,Any],list[str]]:
    c=[x for x in obs if x["semantic_surface"]==surface]
    if not c: raise ValueError("NO_EVIDENCE:"+surface)
    if len({x["claim_dimension"] for x in c})!=1: raise ValueError("CLAIM_DIMENSION_CONFLICT:"+surface)
    superseded={s for x in c for s in x.get("supersedes",[])}
    c=[x for x in c if x["source_id"] not in superseded]
    c.sort(key=lambda x:(RANK.get(x["claim_dimension"],{}).get(x["source_class"],-1),ts(x["observed_at"])),reverse=True)
    top=c[0]; rank=RANK.get(top["claim_dimension"],{}).get(top["source_class"],-1)
    peer=[x for x in c[1:] if RANK.get(x["claim_dimension"],{}).get(x["source_class"],-1)==rank and ts(x["observed_at"])==ts(top["observed_at"])]
    if any(x["identity"]!=top["identity"] for x in peer): raise ValueError("EQUAL_PRIORITY_IDENTITY_CONFLICT:"+surface)
    warnings=[]
    if any(RANK.get(x["claim_dimension"],{}).get(x["source_class"],-1)<rank and ts(x["observed_at"])>ts(top["observed_at"]) and x["identity"]!=top["identity"] for x in c[1:]):
        warnings.append("NEWER_LOWER_AUTHORITY_EVIDENCE_DIFFERS:"+surface)
    return deepcopy(top),warnings

def adjudicate_r52_r57(r52:Mapping[str,Any],r57:Mapping[str,Any]) -> dict[str,Any]:
    if r52.get("work_order_id")!="CODEX01-R52-CONTINUITYOS-CANONICAL-ADOPTION" or r52.get("terminal")!="LOCAL_CANONICAL_ADOPTION_PASS":
        raise ValueError("R52_INVALID")
    if r57.get("work_order_id")!="CODEX01-R57-CONTINUITYOS-RUNTIME-ADOPTION-PREFLIGHT" or r57.get("terminal")!="REVISE":
        raise ValueError("R57_INVALID")
    if r57.get("live_activation") is not False: raise ValueError("R57_REVISE_CANNOT_ASSERT_LIVE_ACTIVATION")
    return {
        "code_adoption":"R52_LOCAL_CANONICAL_ADOPTION_ACCEPTED_HISTORICAL",
        "runtime_adoption":"R57_REVISE_NO_LIVE_ACTIVATION",
        "live_activation":False,
        "current_public_repo_relation":"SEPARATE_SOURCE_FRESHNESS_DIMENSION",
    }

def build(data:dict[str,Any]) -> dict[str,Any]:
    obs=normalize(data["observations"])
    missing=sorted(REQUIRED_SURFACES-{x["semantic_surface"] for x in obs})
    if missing: raise ValueError("MISSING_REQUIRED_SURFACES:"+",".join(missing))
    chosen={}; warnings=[]
    for s in REQUIRED_SURFACES:
        chosen[s],w=select(obs,s); warnings+=w
    a=chosen["r64.authority"]["payload"]
    hr=chosen["hanri.runtime"]["payload"]
    hg=chosen["hanri.repository"]["payload"]
    hp=chosen["hanri.projection"]["payload"]
    co=chosen["collaboration.raw4ik"]["payload"]
    va=chosen["visionassist.custody"]["payload"]
    cr=chosen["continuityos.repository"]["payload"]
    projection_freshness="CURRENT" if hp["bound_repo_head"]==hg["head"] else "STALE"
    anchor_freshness="CURRENT" if co["canonical_anchor_head"]==hg["head"] else "STALE"
    effects=deepcopy(a["effect_ceiling"])
    snapshot={
        "schema":"control-center.normalized-snapshot.v2",
        "snapshot_id":"CONTROL_CENTER_NORMALIZED_"+data["observed_at"],
        "generated_at":data["observed_at"],
        "authority":{"generation":a["generation"],"status":a["status"]},
        "control_center":{"role":"GLOBAL_COMMAND_TRUTH_ROUTING_ADJUDICATION"},
        "hanri":{
            "role":"SUBORDINATE_RUNTIME_ATTENTION_GOVERNOR_EVIDENCE",
            "runtime_state":hr,
            "repo_state":hg,
            "projection_state":hp,
        },
        "continuityos":{
            "modern_repository":cr,
            "historical_local_adoption":adjudicate_r52_r57(data["continuityos_r52"],data["continuityos_r57"]),
        },
        "return_broker":{"role":"TRANSPORT_INDEX_DEDUP_NOT_AUTHORITY"},
        "projects":{"VisionAssist":va},
        "agent_slots":deepcopy(data["agent_slots"]),
        "collaboration":{**co,"anchor_freshness":anchor_freshness},
        "effects":effects,
        "freshness":{
            "authority_freshness":chosen["r64.authority"]["freshness"],
            "runtime_freshness":chosen["hanri.runtime"]["freshness"],
            "projection_freshness":projection_freshness,
            "hanri_repo_provider_head":hg["head"],
        },
        "visible_shell":{
            "authority_generation":a["generation"],
            "hanri_runtime":hr["label"],
            "hanri_repo_head":hg["head"],
            "collaboration_live":co["collaboration_live"],
        },
        "normalization":{"warnings":sorted(set(warnings))},
    }
    return snapshot

def validate(s:dict[str,Any]) -> tuple[list[str],list[str]]:
    e=[]; w=[]
    if s["visible_shell"]["authority_generation"]!=s["authority"]["generation"]: e.append("VISIBLE_AUTHORITY_MISMATCH")
    if s["visible_shell"]["hanri_runtime"]!=s["hanri"]["runtime_state"]["label"]: e.append("VISIBLE_RUNTIME_MISMATCH")
    if s["visible_shell"]["hanri_repo_head"]!=s["hanri"]["repo_state"]["head"]: e.append("VISIBLE_REPO_HEAD_MISMATCH")
    if s["visible_shell"]["collaboration_live"]!=s["collaboration"]["collaboration_live"]: e.append("VISIBLE_COLLABORATION_MISMATCH")
    rs=s["hanri"]["runtime_state"]
    if rs["status"]=="ACCEPTED_LIVE" and rs["source_class"] not in {"host_readback","operator_terminal_receipt","slot_receipt"}: e.append("LIVE_RUNTIME_WITHOUT_RUNTIME_SOURCE")
    c5=s["agent_slots"].get("CODEX-05",{})
    if c5.get("operational_status")=="DO_NOT_TOUCH" and c5.get("promotion_eligible") is True: e.append("CODEX05_DO_NOT_TOUCH_PROMOTION_DRIFT")
    ef=s["effects"]
    if ef.get("auto_accept") is True: e.append("AUTO_ACCEPT_BROADENED")
    if ef.get("auto_dispatch") is True: e.append("AUTO_DISPATCH_BROADENED")
    if ef.get("can_trade") is not False: e.append("TRADING_AUTHORITY_BROADENED")
    if ef.get("capital_permission")!="DENY": e.append("CAPITAL_AUTHORITY_BROADENED")
    if ef.get("self_application") is not False: e.append("SELF_APPLICATION_BROADENED")
    if s["freshness"]["projection_freshness"]=="STALE": w.append("HANRI_REPO_ADVANCED_AFTER_PROJECTION")
    if s["collaboration"]["anchor_freshness"]=="STALE": w.append("COLLAB_UPSTREAM_ANCHOR_STALE")
    return sorted(set(e)),sorted(set(w))

def gate(s:dict[str,Any], require_current:bool=False) -> dict[str,Any]:
    e,w=validate(s)
    pf=s["freshness"]["projection_freshness"]
    if require_current and pf!="CURRENT": e.append("PROJECTION_NOT_CURRENT")
    if pf=="STALE": w.append("PUBLISH_ONLY_WITH_VISIBLE_STALE_LABEL")
    status="BLOCKED" if e else ("PUBLISHABLE_STALE_ONLY" if pf=="STALE" else "PUBLISHABLE_CURRENT")
    return {"publishable":not e,"status":status,"blockers":sorted(set(e)),"warnings":sorted(set(w))}

def validate_write_guard(kind:str, *, fresh_pr:bool=False, exact_send:bool=False, exact_effect:bool=False) -> str:
    if kind in {"GITHUB_COMMENT","EXTERNAL_SEND"}: return "ALLOW" if exact_send else "DENY_NO_EXACT_SEND"
    if kind=="GITHUB_REVIEW_BRANCH_WRITE": return "ALLOW" if fresh_pr else "DENY_NO_FRESH_PR_READBACK"
    if kind in {"GITHUB_MERGE","DRIVE_WRITE","RUNTIME_MUTATION"}: return "ALLOW" if exact_effect else "DENY_NO_EXACT_EFFECT_GATE"
    if kind=="TRADING_OR_CAPITAL": return "DENY_TRADING_CAPITAL_CEILING"
    return "ALLOW_READ_ONLY" if kind=="READ_ONLY" else "DENY_UNKNOWN_OPERATION"

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--validate",type=Path,required=True)
    p.add_argument("--require-current",action="store_true")
    args=p.parse_args()
    data=json.loads(args.validate.read_text(encoding="utf-8"))
    s=build(data); g=gate(s,args.require_current)
    out={
        "terminal":"CONTROL_CENTER_SYNC_V2_PASS" if g["publishable"] else "CONTROL_CENTER_SYNC_V2_BLOCKED",
        "build_gate":g,
        "authority":s["authority"],
        "hanri_runtime":s["hanri"]["runtime_state"]["label"],
        "hanri_repo_head":s["hanri"]["repo_state"]["head"],
        "projection_freshness":s["freshness"]["projection_freshness"],
        "continuityos":s["continuityos"]["historical_local_adoption"],
        "visionassist_status":s["projects"]["VisionAssist"]["status"],
        "effects":s["effects"],
    }
    print(json.dumps(out,indent=2,sort_keys=True))
    return 0 if g["publishable"] else 2

if __name__=="__main__":
    raise SystemExit(main())
