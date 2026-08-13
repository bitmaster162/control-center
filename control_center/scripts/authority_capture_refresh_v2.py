#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SYNC_SCHEMA="control-center.sync-evidence.review.v2"
CAPTURE_SCHEMA="control-center.authority-refresh-capture.v2"
CAPTURE_KIND="READ_ONLY_PROVIDER_CAPTURE_PER_SURFACE"
PROVIDER="GOOGLE_DRIVE_DIRECT_READBACK"
SURFACE="r64.authority"
MAX_AGE_SECONDS=21600
FUTURE_SKEW_SECONDS=300

EXPECTED={
 "CURRENT_POINTER.json":{"drive_file_id":"10HUmbzBVCQDnbFAL6UQ6B2O336ENkEW5","bytes":5493,"sha256":"3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3"},
 "CURRENT_STATE.json":{"drive_file_id":"10w_2sw2Sl2I5SNe3aY9jqS46u0muvYs_","bytes":6506,"sha256":"701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68"},
 "ROLE_INDEX.json":{"drive_file_id":"1AxtE4avTtVCu8kLr2T6UPT4kGB45yZfa","bytes":2043,"sha256":"e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567"},
 "ROLE_VIEWS.json":{"drive_file_id":"19S7z_XwuG-SsKnsxa8vplx4DZxvy49VT","bytes":3945,"sha256":"9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148"},
 "MANIFEST.json":{"drive_file_id":"1I757i4MVez3Xr6DiqH5DJ7sBY1POl-5g","bytes":1328,"sha256":"383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d"},
}

def parse_time(s:str)->datetime:
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("timezone_required")
    return d.astimezone(timezone.utc)

def current_row(sync:Mapping[str,Any])->dict[str,Any]:
    rows=[r for r in sync.get("observations",[]) if isinstance(r,dict) and r.get("semantic_surface")==SURFACE and r.get("freshness")=="CURRENT"]
    if len(rows)!=1: raise ValueError("current_authority_row_count:"+str(len(rows)))
    return rows[0]

def validate_capture(c:Mapping[str,Any], *, now:datetime)->list[str]:
    e=[]
    if c.get("schema")!=CAPTURE_SCHEMA: e.append("capture_schema_mismatch")
    if c.get("capture_kind")!=CAPTURE_KIND: e.append("capture_kind_mismatch")
    if c.get("provider")!=PROVIDER: e.append("capture_provider_mismatch")
    if c.get("semantic_surface")!=SURFACE: e.append("capture_surface_mismatch")
    try:
        t=parse_time(str(c.get("observed_at","")))
        if (now.astimezone(timezone.utc)-t).total_seconds() < -FUTURE_SKEW_SECONDS:
            e.append("capture_from_future")
    except (TypeError,ValueError): e.append("capture_timestamp_invalid")
    roots=c.get("stable_roots",{})
    if set(roots)!=set(EXPECTED): e.append("root_set_mismatch")
    modified={}
    for name,exp in EXPECTED.items():
        r=roots.get(name,{})
        for k in ("drive_file_id","bytes","sha256"):
            if r.get(k)!=exp[k]: e.append(f"provider_drift:{name}:{k}")
        try: modified[name]=parse_time(str(r.get("modified_time","")))
        except (TypeError,ValueError): e.append(f"modified_time_invalid:{name}")
    if len(modified)==len(EXPECTED):
        latest=max(modified,key=modified.get)
        if latest!="CURRENT_POINTER.json": e.append("provider_drift:current_pointer_not_latest_modified_root")
    safety=c.get("safety",{})
    for k in ("provider_mutation_performed","authority_granted","registry_mutation_performed","runtime_mutation_performed","merge","deploy","can_trade","self_application"):
        if safety.get(k) is not False: e.append("safety_leak:"+k)
    if safety.get("capital_permission")!="DENY": e.append("safety_leak:capital_permission")
    return sorted(set(e))

def candidate_observation(c:Mapping[str,Any])->dict[str,Any]:
    return {
      "semantic_surface":SURFACE,
      "claim_dimension":"authority",
      "source_class":"stable_authority_root",
      "source_id":"R64_DRIVE_CAPTURE_"+str(c["observed_at"]),
      "source_scope":"R64_STABLE_AUTHORITY",
      "observed_at":c["observed_at"],
      "identity":EXPECTED["CURRENT_POINTER.json"]["sha256"],
      "freshness":"CURRENT",
      "claim_ceiling":"BOUND_AUTHORITY_FACT_ONLY",
      "effect_authority":"NONE",
      "payload":{
        "generation":"R64",
        "status":"ACTIVE_RESEALED",
        "human_sovereign":"ROBERT",
        "provider_readback":"5_OF_5_EXACT",
        "freshness":"CURRENT",
        "observed_at":c["observed_at"],
        "roots":deepcopy(c["stable_roots"]),
        "effect_ceiling":{
          "auto_accept":False,"auto_dispatch":False,"can_trade":False,
          "capital_permission":"DENY","deploy_permission":"DENY","self_application":False
        }
      }
    }

def classify(sync:Mapping[str,Any], c:Mapping[str,Any], *, now:datetime)->dict[str,Any]:
    invalid=validate_capture(c,now=now)
    if any(x.startswith(("capture_","root_set_","modified_time_","safety_leak")) for x in invalid):
        return {"verdict":"INVALID_CAPTURE","refresh_allowed":False,"errors":invalid,"candidate_observation":None}
    drift=[x for x in invalid if x.startswith("provider_drift:")]
    if drift:
        return {"verdict":"DRIFT_HOLD","refresh_allowed":False,"errors":drift,"candidate_observation":None}
    row=current_row(sync)
    cur=parse_time(str(row["observed_at"]))
    cap=parse_time(str(c["observed_at"]))
    age=(now.astimezone(timezone.utc)-cur).total_seconds()
    if cap <= cur:
        if age <= MAX_AGE_SECONDS:
            return {"verdict":"CURRENT_NO_REFRESH","refresh_allowed":False,"errors":[],"candidate_observation":None}
        return {"verdict":"EXPIRED_RECAPTURE","refresh_allowed":False,"errors":["strictly_newer_capture_required"],"candidate_observation":None}
    return {
      "verdict":"NEWER_EXACT_CAPTURE_CANDIDATE",
      "refresh_allowed":True,
      "allowed_update_surface":SURFACE,
      "all_other_surfaces_write_allowed":False,
      "errors":[],
      "candidate_observation":candidate_observation(c),
      "effect_authority":"NONE"
    }

def apply_candidate(sync:Mapping[str,Any], candidate:Mapping[str,Any])->dict[str,Any]:
    if candidate.get("semantic_surface")!=SURFACE: raise ValueError("candidate_surface_mismatch")
    out=deepcopy(sync)
    rows=[]
    replaced=0
    for r in out.get("observations",[]):
        if isinstance(r,dict) and r.get("semantic_surface")==SURFACE and r.get("freshness")=="CURRENT":
            old=deepcopy(r)
            old["freshness"]="HISTORICAL"
            old_payload=old.get("payload")
            if isinstance(old_payload,dict) and "freshness" in old_payload:
                old_payload["freshness"]="HISTORICAL"
            rows.append(old)
            replaced+=1
        else: rows.append(r)
    if replaced!=1: raise ValueError("apply_current_authority_row_count:"+str(replaced))
    rows.append(deepcopy(candidate))
    out["observations"]=rows
    out["observed_at"]=candidate["observed_at"]
    return out

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("sync_v2",type=Path); p.add_argument("capture",type=Path)
    p.add_argument("--now"); p.add_argument("--write-candidate",type=Path); p.add_argument("--write-updated-sync",type=Path)
    args=p.parse_args()
    now=parse_time(args.now) if args.now else datetime.now(timezone.utc)
    sync=json.loads(args.sync_v2.read_text(encoding="utf-8")); cap=json.loads(args.capture.read_text(encoding="utf-8"))
    result=classify(sync,cap,now=now)
    print(json.dumps(result,indent=2,sort_keys=True))
    if result.get("refresh_allowed") and args.write_candidate:
        args.write_candidate.write_text(json.dumps(result["candidate_observation"],indent=2)+"\n",encoding="utf-8")
    if result.get("refresh_allowed") and args.write_updated_sync:
        args.write_updated_sync.write_text(json.dumps(apply_candidate(sync,result["candidate_observation"]),indent=2)+"\n",encoding="utf-8")
    return 0 if result["verdict"] in {"CURRENT_NO_REFRESH","NEWER_EXACT_CAPTURE_CANDIDATE"} else 2

if __name__=="__main__": raise SystemExit(main())
