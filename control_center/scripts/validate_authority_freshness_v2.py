#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA="control-center.sync-evidence.review.v2"
MAX_AGE_SECONDS=21600
FUTURE_SKEW_SECONDS=300
EXPECTED_ROOTS={
  "CURRENT_POINTER.json":"3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3",
  "CURRENT_STATE.json":"701db3dfa51877c1662b94688e9c1136ec5b7a3602b4564bea885d72c9740d68",
  "ROLE_INDEX.json":"e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567",
  "ROLE_VIEWS.json":"9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148",
  "MANIFEST.json":"383ce835d68d69b9e96a5bba3ecd2051bdd06d5e0a369abf08c78d33c8e0912d",
}

def parse_time(value:str)->datetime:
    parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    if parsed.tzinfo is None: raise ValueError("timestamp_missing_timezone")
    return parsed.astimezone(timezone.utc)

def authority_rows(data:Mapping[str,Any])->list[dict[str,Any]]:
    return [
      r for r in data.get("observations",[])
      if isinstance(r,dict) and r.get("semantic_surface")=="r64.authority"
    ]

def validate(data:Mapping[str,Any], *, now:datetime)->list[str]:
    errors=[]
    if data.get("schema")!=SCHEMA: errors.append("schema_mismatch")
    rows=authority_rows(data)
    current=[r for r in rows if r.get("freshness")=="CURRENT"]
    if len(current)!=1:
        return errors+["current_r64_authority_observation_count:"+str(len(current))]
    row=current[0]
    if row.get("claim_dimension")!="authority": errors.append("claim_dimension_mismatch")
    if row.get("source_class")!="stable_authority_root": errors.append("source_class_mismatch")
    if row.get("effect_authority")!="NONE": errors.append("effect_authority_leak")
    try:
        observed=parse_time(str(row.get("observed_at","")))
        age=(now.astimezone(timezone.utc)-observed).total_seconds()
        if age>MAX_AGE_SECONDS: errors.append("authority_freshness_stale")
        if age < -FUTURE_SKEW_SECONDS: errors.append("authority_freshness_from_future")
    except (TypeError,ValueError):
        errors.append("authority_timestamp_invalid")
    payload=row.get("payload",{})
    if payload.get("generation")!="R64": errors.append("generation_mismatch")
    if payload.get("status")!="ACTIVE_RESEALED": errors.append("status_mismatch")
    if payload.get("provider_readback")!="5_OF_5_EXACT": errors.append("provider_readback_not_exact")
    roots=payload.get("roots",{})
    if set(roots)!=set(EXPECTED_ROOTS): errors.append("root_set_mismatch")
    for name,sha in EXPECTED_ROOTS.items():
        rr=roots.get(name,{})
        if rr.get("sha256")!=sha: errors.append("root_sha_mismatch:"+name)
        if not isinstance(rr.get("bytes"),int) or rr.get("bytes",0)<=0: errors.append("root_bytes_invalid:"+name)
    ceiling=payload.get("effect_ceiling",{})
    if ceiling.get("auto_accept") is not False: errors.append("auto_accept_leak")
    if ceiling.get("auto_dispatch") is not False: errors.append("auto_dispatch_leak")
    if ceiling.get("can_trade") is not False: errors.append("trade_authority_leak")
    if ceiling.get("capital_permission")!="DENY": errors.append("capital_authority_leak")
    if ceiling.get("self_application") is not False: errors.append("self_application_leak")
    return sorted(set(errors))

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("sync_v2",type=Path)
    p.add_argument("--now")
    args=p.parse_args()
    now=parse_time(args.now) if args.now else datetime.now(timezone.utc)
    data=json.loads(args.sync_v2.read_text(encoding="utf-8"))
    errors=validate(data,now=now)
    rows=authority_rows(data)
    observed=rows[0].get("observed_at") if len(rows)==1 else None
    print(json.dumps({
      "schema":"control-center.authority-freshness-v2-result.v1",
      "status":"PASS" if not errors else "FAIL",
      "gate":"AUTHORITY_FRESHNESS_V2",
      "observed_at":observed,
      "max_age_seconds":MAX_AGE_SECONDS,
      "errors":errors,
      "claim_ceiling":"AUTHORITY_FRESHNESS_ONLY_NO_EFFECT",
      "terminal":"AUTHORITY_FRESHNESS_V2_PASS" if not errors else "AUTHORITY_FRESHNESS_V2_FAIL"
    },indent=2,sort_keys=True))
    return 0 if not errors else 2

if __name__=="__main__":
    raise SystemExit(main())
