from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path
import pytest
from control_center.scripts.build_operator_projection_v2 import build_shadow_projection

h=lambda s: hashlib.sha256(s.encode()).hexdigest()

def write(p,v):
    p.write_text(json.dumps(v,indent=2)+"\n",encoding="utf-8"); return p

def snapshot():
    return {"schema":"control_center.provider_snapshot.v1","snapshot_kind":"NON_AUTHORITY_PROVIDER_READBACK",
    "canonical_roots":{"generation":"R64","status":"ACTIVE","pointer_sha256":h("p"),"manifest_sha256":h("m"),"current_state_sha256":h("s"),"role_index_sha256":h("ri"),"role_views_sha256":h("rv"),"provider_readback":"all_exact","r63_is_current":False},
    "github_lanes":{"control_center":{"head_sha":"8969c264d505a6d5cb8590eb5a1b74b461f0b19c"}}}

def live():
    return {"schema":"control_return_broker.v1.live_index","generation":"R59","updated_at_utc":"2026-08-15T17:00:00Z","slots":{},"entry_count":11}

def provider(head="9c3f3642211501867b8f089decb3b9b6166de350",verdict="FRESH",required=None):
    return {"source_id":"github:cc","locator":"github://cc","identity":{"repo":"cc","ref":"lane"},"observed_at":"2026-08-15T17:01:00Z",
    "freshness":{"verdict":verdict,"policy":"per-compile","expires_at":None},"payload":{"head_sha":head},"required_for":list(required or [])}

def rec(subject,artifact,source_class,**kw):
    row={"schema":"control_plane.reconciliation_record.v1","source_cut_id":"AUTO_SOURCE_CUT","subject_id":subject,"artifact_id":artifact,"artifact_sha256":h(artifact),
    "source_class":source_class,"authority_class":"NONE","observed_at":"2026-08-15T17:02:00Z","freshness":"FRESH","logical_version":None,"predecessor_id":None,"supersedes_id":None,
    "claim_value":"READY","claim_status":"PASS","current_observation":False,"evidence_debt":False,"transport_status":"NONE","semantic_status":"UNREVIEWED",
    "apply_status":"NOT_APPLIED","owner":"CONTROL_CENTER","do_not_touch":False,"requested_action":None,"human_gate_required":False,"action_evidence_fresh":True,
    "effect_authorized":False,"execution_authorized":False}; row.update(kw); return row

def canon(subject): return rec(subject,"canon:"+subject,"CANONICAL_ACTIVE_STATE",apply_status="APPLIED")
def accepted(subject): return rec(subject,"decision:"+subject,"CONTROLLER_ADJUDICATION",authority_class="DETERMINISTIC_CONTROLLER",semantic_status="ACCEPTED")
def gate(subject,fresh=True): return rec(subject,"gate:"+subject,"AUDIT",authority_class="FACTUAL_OBSERVATION",requested_action="APPLY",human_gate_required=True,action_evidence_fresh=fresh,freshness="FRESH" if fresh else "STALE",claim_status="HOLD")

def files(tmp_path,prov=None,groups=None):
    return (write(tmp_path/"a.json",snapshot()),write(tmp_path/"l.json",live()),write(tmp_path/"p.json",prov or provider()),write(tmp_path/"s.json",{"subjects":groups or [[canon("project:x")]]}))

def build(tmp_path,prov=None,groups=None):
    a,l,p,s=files(tmp_path,prov,groups)
    return build_shadow_projection(authority_snapshot_path=a,return_live_index_path=l,provider_observation_paths=[p],subject_records_path=s,
        fetched_at="2026-08-15T17:03:00Z",generated_at="2026-08-16T00:03:01+07:00")

def test_ready_and_legacy_head_not_leaked(tmp_path):
    x=build(tmp_path); raw=json.dumps(x)
    assert x["terminal"]=="PROJECTION_READY"
    assert "8969c264d505a6d5cb8590eb5a1b74b461f0b19c" not in raw

def test_auto_cut_bound_to_all_views(tmp_path):
    x=build(tmp_path); cut=x["source_cut"]["source_cut_id"]
    assert {v["source_cut_id"] for v in x["views"].values()}=={cut}

def test_foreign_record_cut_rejected(tmp_path):
    r=canon("p:x"); r["source_cut_id"]="cut-"+h("foreign")
    a,l,p,s=files(tmp_path,groups=[[r]])
    with pytest.raises(ValueError,match="SUBJECT_RECORD_FOREIGN_SOURCE_CUT"):
        build_shadow_projection(authority_snapshot_path=a,return_live_index_path=l,provider_observation_paths=[p],subject_records_path=s,
            fetched_at="2026-08-15T17:03:00Z",generated_at="2026-08-16T00:03:01+07:00")

def test_stale_required_source_suppresses_human_now(tmp_path):
    subject="effect:x"; x=build(tmp_path,provider(verdict="STALE",required=["subject:"+subject]),[[canon(subject),accepted(subject),gate(subject,True)]])
    assert x["terminal"]=="PROJECTION_DEGRADED" and x["views"]["human_now"]["items"]==[] and x["views"]["blocked"]["items"]==[subject]

def test_fresh_gate_enters_human_now(tmp_path):
    subject="effect:x"; x=build(tmp_path,provider(required=["subject:"+subject]),[[canon(subject),accepted(subject),gate(subject,True)]])
    assert x["views"]["human_now"]["items"]==[subject]

def test_identity_conflict_holds(tmp_path):
    a=write(tmp_path/"a.json",snapshot()); l=write(tmp_path/"l.json",live()); p1=write(tmp_path/"p1.json",provider("old")); p2=write(tmp_path/"p2.json",provider("new")); s=write(tmp_path/"s.json",{"subjects":[[canon("p:x")]]})
    x=build_shadow_projection(authority_snapshot_path=a,return_live_index_path=l,provider_observation_paths=[p1,p2],subject_records_path=s,
        fetched_at="2026-08-15T17:03:00Z",generated_at="2026-08-16T00:03:01+07:00")
    assert x["terminal"]=="PROJECTION_HOLD" and x["freshness_summary"]["identity_conflict"]==1

def test_invalid_authority_unavailable(tmp_path):
    bad=snapshot(); bad["canonical_roots"]["provider_readback"]="partial"
    a=write(tmp_path/"a.json",bad); l=write(tmp_path/"l.json",live()); p=write(tmp_path/"p.json",provider()); s=write(tmp_path/"s.json",{"subjects":[[canon("p:x")]]})
    x=build_shadow_projection(authority_snapshot_path=a,return_live_index_path=l,provider_observation_paths=[p],subject_records_path=s,
        fetched_at="2026-08-15T17:03:00Z",generated_at="2026-08-16T00:03:01+07:00")
    assert x["terminal"]=="PROJECTION_UNAVAILABLE"

def test_cli_only_writes_explicit_output(tmp_path):
    a,l,p,s=files(tmp_path); before={x.name:h(x.read_text()) for x in (a,l,p,s)}; out=tmp_path/"shadow"/"projection.json"
    cmd=[sys.executable,"-m","control_center.scripts.build_operator_projection_v2","--authority-snapshot",str(a),"--return-live-index",str(l),"--provider-observation",str(p),
         "--subject-records",str(s),"--fetched-at","2026-08-15T17:03:00Z","--generated-at","2026-08-16T00:03:01+07:00","--output",str(out)]
    proc=subprocess.run(cmd,capture_output=True,text=True); assert proc.returncode==0,proc.stderr; assert out.is_file()
    assert before=={x.name:h(x.read_text()) for x in (a,l,p,s)}
    assert json.loads(out.read_text())["projection_kind"]=="NON_AUTHORITY_PROJECTION"
