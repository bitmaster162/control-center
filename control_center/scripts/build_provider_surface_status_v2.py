#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from authority_capture_refresh_v2 import classify, current_row, parse_time, MAX_AGE_SECONDS

SCHEMA="control-center.provider-surface-status.v2"
PROJECTION_KIND="NON_AUTHORITY_PER_SURFACE_PROVIDER_DIAGNOSTIC"

def safety()->dict[str,Any]:
 return {
  "diagnostic_grants_authority":False,"refresh_authorized":False,"root_write_authorized":False,
  "registry_write_authorized":False,"runtime_mutation_authorized":False,"routing_mutation_authorized":False,
  "dispatch_authorized":False,"apply_authorized":False,"execution_authorized":False,"deploy_authorized":False,
  "external_message_authorized":False,"can_trade":False,"capital_permission":"DENY","self_application":False
 }

def surface_rows(sync:Mapping[str,Any])->dict[str,dict[str,Any]]:
 out={}
 for row in sync.get("observations",[]):
  if not isinstance(row,dict): continue
  surface=row.get("semantic_surface")
  if not surface: continue
  if row.get("freshness")=="HISTORICAL": continue
  prior=out.get(surface)
  if prior is None or parse_time(str(row.get("observed_at"))) > parse_time(str(prior.get("observed_at"))):
   out[str(surface)]=row
 return out

def build(sync:Mapping[str,Any], capture:Mapping[str,Any], *, now:datetime)->dict[str,Any]:
 result=classify(sync,capture,now=now)
 auth=current_row(sync)
 observed=parse_time(str(auth["observed_at"]))
 expiry=observed+timedelta(seconds=MAX_AGE_SECONDS)
 age=(now.astimezone(timezone.utc)-observed).total_seconds()
 verdict=result["verdict"]
 if verdict=="DRIFT_HOLD":
  auth_state="DRIFT_HOLD"; hold=True
 elif verdict=="INVALID_CAPTURE":
  auth_state="INVALID_CAPTURE_HOLD"; hold=True
 elif verdict=="EXPIRED_RECAPTURE" or age>MAX_AGE_SECONDS:
  auth_state="EXPIRED_RECAPTURE"; hold=True
 elif verdict=="NEWER_EXACT_CAPTURE_CANDIDATE":
  auth_state="NEWER_EXACT_CAPTURE_CANDIDATE"; hold=False
 else:
  auth_state="CURRENT_EXACT"; hold=False

 rows=surface_rows(sync)
 surfaces={}
 for surface,row in sorted(rows.items()):
  surfaces[surface]={
   "freshness":row.get("freshness","UNKNOWN"),
   "observed_at":row.get("observed_at"),
   "identity":row.get("identity"),
   "claim_dimension":row.get("claim_dimension"),
   "source_class":row.get("source_class"),
   "effect_authority":row.get("effect_authority","NONE")
  }
 surfaces["r64.authority"].update({
  "operator_state":auth_state,
  "lease_expires_at":expiry.isoformat().replace("+00:00","Z"),
  "capture_verdict":verdict,
  "hold_active":hold
 })
 stale=sorted(k for k,v in surfaces.items() if v.get("freshness") in {"STALE","BLOCKED_REVERIFY","UNKNOWN"})
 return {
  "schema":SCHEMA,
  "projection_kind":PROJECTION_KIND,
  "generated_at":now.astimezone(timezone.utc).isoformat().replace("+00:00","Z"),
  "authority_surface":"r64.authority",
  "authority_operator_state":auth_state,
  "authority_hold_active":hold,
  "global_hold_derived_from_other_surface_staleness":False,
  "stale_or_blocked_surfaces":stale,
  "surfaces":surfaces,
  "capture":{
    "schema":capture.get("schema"),"provider":capture.get("provider"),"observed_at":capture.get("observed_at"),
    "verdict":verdict,"errors":result.get("errors",[])
  },
  "note":"Per-surface diagnostic only. Staleness on HANRI projection or other evidence surfaces does not silently create or clear R64 authority hold.",
  "safety":safety()
 }

def validate(status:Mapping[str,Any])->list[str]:
 e=[]
 if status.get("schema")!=SCHEMA: e.append("schema_mismatch")
 if status.get("projection_kind")!=PROJECTION_KIND: e.append("projection_kind_mismatch")
 if "r64.authority" not in status.get("surfaces",{}): e.append("authority_surface_missing")
 if status.get("global_hold_derived_from_other_surface_staleness") is not False: e.append("cross_surface_hold_leak")
 for surface,row in status.get("surfaces",{}).items():
  if row.get("effect_authority") not in {None,"NONE"}: e.append("surface_effect_authority_leak:"+surface)
 s=status.get("safety",{})
 for k in ("diagnostic_grants_authority","refresh_authorized","root_write_authorized","registry_write_authorized","runtime_mutation_authorized","routing_mutation_authorized","dispatch_authorized","apply_authorized","execution_authorized","deploy_authorized","external_message_authorized","can_trade","self_application"):
  if s.get(k) is not False: e.append("safety_leak:"+k)
 if s.get("capital_permission")!="DENY": e.append("safety_leak:capital_permission")
 return sorted(set(e))

def main()->int:
 p=argparse.ArgumentParser()
 p.add_argument("sync_v2",type=Path); p.add_argument("capture",type=Path); p.add_argument("--now")
 args=p.parse_args()
 now=parse_time(args.now) if args.now else datetime.now(timezone.utc)
 sync=json.loads(args.sync_v2.read_text()); cap=json.loads(args.capture.read_text())
 status=build(sync,cap,now=now); errors=validate(status)
 status["validation_errors"]=errors
 status["terminal"]="PER_SURFACE_DRIFT_STATUS_V2_PASS" if not errors else "PER_SURFACE_DRIFT_STATUS_V2_FAIL"
 print(json.dumps(status,indent=2,sort_keys=True))
 return 0 if not errors else 2

if __name__=="__main__":raise SystemExit(main())
