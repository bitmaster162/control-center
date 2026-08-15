"""Shadow operator projection v2 builder over already-fetched local JSON evidence."""
from __future__ import annotations
import argparse, json, os, tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from control_center.scripts.operator_projection_v2 import compile_projection, compute_source_cut
from control_center.scripts.projection_sources_v2 import load_authority_snapshot, load_provider_observations, load_return_cursor
from control_center.scripts.reconciliation_v1 import resolve
from control_center.scripts.legacy_p6_compat_v1 import adapt_legacy_work_order

AUTO_CUT="AUTO_SOURCE_CUT"

def _read_json(path:Path)->Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _load_subject_groups(path:Path)->list[list[dict[str,Any]]]:
    payload=_read_json(path)
    if not isinstance(payload,Mapping): raise ValueError("SUBJECT_GROUPS_REQUIRED")
    groups=payload.get("subjects",[])
    legacy_rows=payload.get("legacy_work_orders",[])
    legacy_observed_at=payload.get("legacy_observed_at")
    if not isinstance(groups,list) or not isinstance(legacy_rows,list): raise ValueError("SUBJECT_GROUPS_REQUIRED")
    out=[]
    for group in groups:
        if not isinstance(group,list) or not group: raise ValueError("SUBJECT_GROUP_INVALID")
        rows=[]
        for row in group:
            if not isinstance(row,Mapping): raise ValueError("SUBJECT_RECORD_INVALID")
            rows.append(dict(row))
        out.append(rows)
    if legacy_rows:
        if not isinstance(legacy_observed_at,str) or not legacy_observed_at:
            raise ValueError("LEGACY_OBSERVED_AT_REQUIRED")
        for row in legacy_rows:
            if not isinstance(row,Mapping): raise ValueError("LEGACY_WORK_ORDER_INVALID")
            out.append([adapt_legacy_work_order(row, observed_at=legacy_observed_at)])
    if not out:
        raise ValueError("SUBJECT_GROUPS_REQUIRED")
    return out

def _bind_source_cut(groups:Sequence[Sequence[Mapping[str,Any]]],source_cut_id:str)->list[list[dict[str,Any]]]:
    bound=[]
    for group in groups:
        rows=[]
        for row in group:
            copied=dict(row); existing=copied.get("source_cut_id")
            if existing not in (None,AUTO_CUT,source_cut_id):
                raise ValueError("SUBJECT_RECORD_FOREIGN_SOURCE_CUT")
            copied["source_cut_id"]=source_cut_id; rows.append(copied)
        bound.append(rows)
    return bound

def build_shadow_projection(*,authority_snapshot_path:Path,return_live_index_path:Path,provider_observation_paths:Sequence[Path],subject_records_path:Path,fetched_at:str,generated_at:str)->dict[str,Any]:
    authority=load_authority_snapshot(authority_snapshot_path)
    cursor=load_return_cursor(return_live_index_path)
    sources=load_provider_observations(provider_observation_paths,fetched_at=fetched_at)
    if authority.get("available") is not True or cursor.get("available") is not True:
        return compile_projection(authority_anchor=authority,return_plane_cursor=cursor,sources=sources,reconciliations=[],generated_at=generated_at)
    cut=compute_source_cut(authority,cursor,sources)["source_cut_id"]
    groups=_bind_source_cut(_load_subject_groups(subject_records_path),cut)
    reconciliations=[resolve(group) for group in groups]
    return compile_projection(authority_anchor=authority,return_plane_cursor=cursor,sources=sources,reconciliations=reconciliations,generated_at=generated_at)

def atomic_write_json_explicit(path:Path,value:Any)->None:
    path=path.resolve(); path.parent.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(value,ensure_ascii=False,indent=2)+"\n").encode()
    fd,tmp_name=tempfile.mkstemp(prefix="."+path.name+".",suffix=".tmp",dir=str(path.parent)); tmp=Path(tmp_name)
    try:
        with os.fdopen(fd,"wb") as fh:
            fh.write(payload); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp,path)
    finally:
        if tmp.exists(): tmp.unlink()

def parse_args(argv:Sequence[str]|None=None)->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--authority-snapshot",type=Path,required=True)
    parser.add_argument("--return-live-index",type=Path,required=True)
    parser.add_argument("--provider-observation",type=Path,action="append",default=[])
    parser.add_argument("--subject-records",type=Path,required=True)
    parser.add_argument("--fetched-at",required=True)
    parser.add_argument("--generated-at",required=True)
    parser.add_argument("--output",type=Path,required=True)
    return parser.parse_args(argv)

def main(argv:Sequence[str]|None=None)->int:
    args=parse_args(argv)
    projection=build_shadow_projection(
        authority_snapshot_path=args.authority_snapshot,return_live_index_path=args.return_live_index,
        provider_observation_paths=args.provider_observation,subject_records_path=args.subject_records,
        fetched_at=args.fetched_at,generated_at=args.generated_at)
    atomic_write_json_explicit(args.output,projection)
    print(json.dumps({"terminal":projection["terminal"],"projection_id":projection["projection_id"],"output":str(args.output),"projection_kind":projection["projection_kind"],"can_trade":projection["safety"]["can_trade"],"capital_permission":projection["safety"]["capital_permission"]},sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
