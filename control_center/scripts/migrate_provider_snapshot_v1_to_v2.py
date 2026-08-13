#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Mapping

LEGACY_SCHEMA = "control_center.provider_snapshot.v1"
V2_SCHEMA = "control-center.sync-evidence.review.v2"
MAP_SCHEMA = "control-center.provider-snapshot-v1-migration-map.v1"

EXPECTED_LEGACY_SURFACES = {
    "observed_at",
    "canonical_roots",
    "canonical_broker",
    "return_registry",
    "github_lanes.control_center",
    "github_lanes.hanri",
    "github_lanes.bitevo_public",
    "hanri_evidence",
}
ALLOWED_DISPOSITIONS = {
    "MIGRATED_CURRENT",
    "SUPERSEDED_BY_CURRENT_V2",
    "RETAIN_HISTORICAL",
    "REVERIFY_REQUIRED",
    "DEPRECATED_STRUCTURE",
}
REQUIRED_R64_HASH_FIELDS = {
    "pointer_sha256": "CURRENT_POINTER.json",
    "current_state_sha256": "CURRENT_STATE.json",
    "role_index_sha256": "ROLE_INDEX.json",
    "role_views_sha256": "ROLE_VIEWS.json",
    "manifest_sha256": "MANIFEST.json",
}

def by_surface(v2: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in v2.get("observations", []):
        if isinstance(row, dict) and row.get("semantic_surface"):
            out.setdefault(str(row["semantic_surface"]), []).append(row)
    return out

def entry_map(m: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(e.get("legacy_path")): e for e in m.get("entries", []) if isinstance(e, dict)}

def validate_map(m: Mapping[str, Any]) -> list[str]:
    errors=[]
    if m.get("schema") != MAP_SCHEMA:
        errors.append("migration_map_schema_mismatch")
    rows=entry_map(m)
    missing=sorted(EXPECTED_LEGACY_SURFACES-set(rows))
    extra=sorted(set(rows)-EXPECTED_LEGACY_SURFACES)
    if missing: errors.append("migration_map_missing:"+",".join(missing))
    if extra: errors.append("migration_map_unexpected:"+",".join(extra))
    for path,row in rows.items():
        if row.get("disposition") not in ALLOWED_DISPOSITIONS:
            errors.append("invalid_disposition:"+path)
        if not str(row.get("reason","")).strip():
            errors.append("missing_reason:"+path)
    return errors

def validate_r64_parity(v1: Mapping[str, Any], v2s: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    errors=[]
    roots=v1.get("canonical_roots",{})
    rows=v2s.get("r64.authority",[])
    current=[r for r in rows if r.get("freshness")=="CURRENT"]
    if len(current)!=1:
        return ["r64_authority_current_observation_count:"+str(len(current))]
    row=current[0]
    payload=row.get("payload",{})
    if payload.get("generation")!="R64":
        errors.append("r64_generation_mismatch")
    if payload.get("provider_readback") not in {"5_OF_5_EXACT","all_exact"}:
        errors.append("r64_provider_readback_not_exact")
    root_payload=payload.get("roots",{})
    for legacy_field,filename in REQUIRED_R64_HASH_FIELDS.items():
        expected=roots.get(legacy_field)
        got=(root_payload.get(filename) or {}).get("sha256")
        if expected != got:
            errors.append("r64_hash_mismatch:"+filename)
    if row.get("source_class")!="stable_authority_root":
        errors.append("r64_authority_source_class_mismatch")
    return errors

def validate_per_surface_time(v2: Mapping[str, Any]) -> list[str]:
    errors=[]
    rows=[r for r in v2.get("observations",[]) if isinstance(r,dict)]
    times=[r.get("observed_at") for r in rows]
    if not rows:
        return ["v2_observations_empty"]
    if any(not t for t in times):
        errors.append("v2_observation_missing_timestamp")
    if len(set(times)) < 2:
        errors.append("v2_still_monolithic_timestamp")
    for r in rows:
        if r.get("source_class")=="dashboard_projection" and r.get("freshness")=="CURRENT":
            errors.append("current_dashboard_projection_used_as_source:"+str(r.get("semantic_surface")))
        if r.get("effect_authority")!="NONE":
            errors.append("unexpected_effect_authority:"+str(r.get("semantic_surface")))
    return errors

def validate_hanri_supersession(v1: Mapping[str, Any], v2s: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    errors=[]
    old=(v1.get("github_lanes",{}) or {}).get("hanri",{})
    repo_rows=[r for r in v2s.get("hanri.repository",[]) if r.get("freshness")=="CURRENT"]
    runtime_rows=[r for r in v2s.get("hanri.runtime",[]) if r.get("freshness")=="CURRENT"]
    projection_rows=v2s.get("hanri.projection",[])
    if len(repo_rows)!=1: errors.append("hanri_repo_current_count:"+str(len(repo_rows)))
    if len(runtime_rows)!=1: errors.append("hanri_runtime_current_count:"+str(len(runtime_rows)))
    if len(projection_rows)<1: errors.append("hanri_projection_missing")
    if repo_rows:
        new_head=(repo_rows[0].get("payload") or {}).get("head")
        if new_head==old.get("head_sha"):
            errors.append("hanri_old_pr29_head_not_superseded")
    if runtime_rows:
        src=runtime_rows[0].get("source_class")
        if src not in {"host_readback","operator_terminal_receipt","slot_receipt"}:
            errors.append("hanri_runtime_not_runtime_sourced")
    return errors

def validate_no_illicit_promotions(v2s: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    errors=[]
    forbidden_current_prefixes=("return_registry","bitevo","hanri.d4","hanri_evidence")
    for surface,rows in v2s.items():
        if any(surface.startswith(p) for p in forbidden_current_prefixes):
            if any(r.get("freshness")=="CURRENT" for r in rows):
                errors.append("legacy_surface_promoted_without_reverify:"+surface)
    if "control_center.repository" in v2s:
        if any(r.get("freshness")=="CURRENT" for r in v2s["control_center.repository"]):
            errors.append("static_control_center_repo_head_current_forbidden")
    return errors

def build_report(v1: Mapping[str, Any], v2: Mapping[str, Any], m: Mapping[str, Any]) -> dict[str, Any]:
    errors=[]
    errors += validate_map(m)
    if v1.get("schema") != LEGACY_SCHEMA:
        errors.append("legacy_schema_mismatch")
    if v2.get("schema") != V2_SCHEMA:
        errors.append("v2_schema_mismatch")
    surfaces=by_surface(v2)
    errors += validate_r64_parity(v1,surfaces)
    errors += validate_per_surface_time(v2)
    errors += validate_hanri_supersession(v1,surfaces)
    errors += validate_no_illicit_promotions(surfaces)

    rows=entry_map(m)
    counts={d:0 for d in sorted(ALLOWED_DISPOSITIONS)}
    for path in EXPECTED_LEGACY_SURFACES:
        if path in rows:
            counts[rows[path]["disposition"]] += 1

    return {
        "schema":"control-center.provider-snapshot-v1-v2-parity-report.v1",
        "status":"PASS" if not errors else "FAIL",
        "errors":sorted(set(errors)),
        "legacy_schema":v1.get("schema"),
        "v2_schema":v2.get("schema"),
        "legacy_global_observed_at":v1.get("observed_at"),
        "v2_observation_timestamps":sorted({r.get("observed_at") for r in v2.get("observations",[]) if isinstance(r,dict)}),
        "migration_disposition_counts":counts,
        "mapped_legacy_surfaces":sorted(rows),
        "current_v2_surfaces":sorted(surfaces),
        "claim_ceiling":"READ_ONLY_PARITY_EVIDENCE_ONLY",
        "effects":{
            "canonical_mutation":False,
            "registry_mutation":False,
            "runtime_mutation":False,
            "merge":False,
            "deploy":False,
            "trading":False,
            "capital_permission":"DENY",
        },
        "terminal":"V1_TO_PER_SURFACE_V2_PARITY_PASS" if not errors else "V1_TO_PER_SURFACE_V2_PARITY_FAIL",
    }

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("legacy_v1",type=Path)
    p.add_argument("sync_v2",type=Path)
    p.add_argument("migration_map",type=Path)
    p.add_argument("--write-report",type=Path)
    args=p.parse_args()
    v1=json.loads(args.legacy_v1.read_text(encoding="utf-8"))
    v2=json.loads(args.sync_v2.read_text(encoding="utf-8"))
    m=json.loads(args.migration_map.read_text(encoding="utf-8"))
    report=build_report(v1,v2,m)
    text=json.dumps(report,indent=2,sort_keys=True)
    print(text)
    if args.write_report:
        args.write_report.write_text(text+"\n",encoding="utf-8")
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
