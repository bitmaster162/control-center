#!/usr/bin/env python3
from __future__ import annotations
from copy import deepcopy
import importlib.util, json, sys, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("mig", HERE/"migrate_provider_snapshot_v1_to_v2.py")
m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)

MAP=json.loads((HERE.parent/"data"/"provider_snapshot_v1_migration_map.review.v2.json").read_text(encoding="utf-8"))

def v1():
    return {
      "schema":"control_center.provider_snapshot.v1",
      "snapshot_kind":"NON_AUTHORITY_PROVIDER_READBACK",
      "observed_at":"2026-08-12T03:45:00+07:00",
      "canonical_roots":{
        "generation":"R64",
        "pointer_sha256":"p","current_state_sha256":"s","role_index_sha256":"i","role_views_sha256":"v","manifest_sha256":"m"
      },
      "canonical_broker":{"fresh_runtime_liveness":"UNVERIFIED_PROVIDER_READBACK_REQUIRED"},
      "return_registry":{"stable_drive_file_id":"registry","actual_file_sha256":"r"},
      "github_lanes":{
        "control_center":{"head_sha":"oldcc"},
        "hanri":{"head_sha":"oldhanri","accepted_live_r35_sha":"r35"},
        "bitevo_public":{"main_sha":"bitevo","merged":True}
      },
      "hanri_evidence":{"p0_1":"CLOSED","p0_2":"RE_CLOSED","p0_3":"CLOSED"}
    }

def obs(surface,dim,src,identity,when,payload,fresh="CURRENT"):
    return {
      "semantic_surface":surface,"claim_dimension":dim,"source_class":src,"source_id":surface+"-"+when,
      "source_scope":surface,"observed_at":when,"identity":identity,"freshness":fresh,
      "claim_ceiling":"X","effect_authority":"NONE","payload":payload
    }

def v2():
    return {
      "schema":"control-center.sync-evidence.review.v2",
      "observed_at":"2026-08-14T02:00:11+07:00",
      "observations":[
        obs("r64.authority","authority","stable_authority_root","p","2026-08-14T02:00:11+07:00",{
          "generation":"R64","provider_readback":"5_OF_5_EXACT","roots":{
            "CURRENT_POINTER.json":{"sha256":"p"},"CURRENT_STATE.json":{"sha256":"s"},
            "ROLE_INDEX.json":{"sha256":"i"},"ROLE_VIEWS.json":{"sha256":"v"},"MANIFEST.json":{"sha256":"m"}
          }}),
        obs("hanri.repository","repository","github_provider","newhanri","2026-08-14T01:20:00+07:00",{"head":"newhanri"}),
        obs("hanri.runtime","runtime","operator_terminal_receipt","runtime","2026-08-12T23:00:00+07:00",{"status":"ACCEPTED_LIVE"}),
        obs("hanri.projection","projection","provider_read","dash","2026-08-14T00:10:00+07:00",{"bound_repo_head":"older"},"STALE"),
        obs("continuityos.repository","repository","github_provider","cos","2026-08-14T01:20:00+07:00",{"head":"cos"}),
        obs("visionassist.custody","repository","verified_bundle","vision","2026-08-14T00:35:00+07:00",{"status":"PENDING"}),
        obs("collaboration.raw4ik","control_truth","provider_read","raw","2026-08-14T01:20:00+07:00",{"collaboration_live":True}),
      ]
    }

class MigrationTests(unittest.TestCase):
    def test_map_covers_every_v1_semantic_surface(self):
        self.assertEqual(m.validate_map(MAP),[])

    def test_good_parity_passes(self):
        r=m.build_report(v1(),v2(),MAP)
        self.assertEqual(r["status"],"PASS")
        self.assertEqual(r["terminal"],"V1_TO_PER_SURFACE_V2_PARITY_PASS")

    def test_r64_hash_mismatch_fails(self):
        x=v2(); x["observations"][0]["payload"]["roots"]["MANIFEST.json"]["sha256"]="wrong"
        r=m.build_report(v1(),x,MAP)
        self.assertIn("r64_hash_mismatch:MANIFEST.json",r["errors"])

    def test_v2_must_not_have_monolithic_timestamp(self):
        x=v2()
        for row in x["observations"]: row["observed_at"]="2026-08-14T00:00:00+07:00"
        r=m.build_report(v1(),x,MAP)
        self.assertIn("v2_still_monolithic_timestamp",r["errors"])

    def test_old_hanri_head_cannot_masquerade_as_current(self):
        x=v2(); x["observations"][1]["payload"]["head"]="oldhanri"
        r=m.build_report(v1(),x,MAP)
        self.assertIn("hanri_old_pr29_head_not_superseded",r["errors"])

    def test_hanri_runtime_must_have_runtime_source(self):
        x=v2(); x["observations"][2]["source_class"]="github_provider"
        r=m.build_report(v1(),x,MAP)
        self.assertIn("hanri_runtime_not_runtime_sourced",r["errors"])

    def test_static_control_center_current_head_is_forbidden(self):
        x=v2(); x["observations"].append(obs(
          "control_center.repository","repository","github_provider","cc","2026-08-14T02:20:00+07:00",{"head":"self"}))
        r=m.build_report(v1(),x,MAP)
        self.assertIn("static_control_center_repo_head_current_forbidden",r["errors"])

    def test_return_registry_cannot_be_silently_promoted_current(self):
        x=v2(); x["observations"].append(obs(
          "return_registry.stable","control_truth","provider_read","registry","2026-08-14T02:20:00+07:00",{"sha":"r"}))
        r=m.build_report(v1(),x,MAP)
        self.assertIn("legacy_surface_promoted_without_reverify:return_registry.stable",r["errors"])

    def test_dashboard_projection_cannot_be_current_source(self):
        x=v2(); x["observations"].append(obs(
          "some.dashboard","projection","dashboard_projection","d","2026-08-14T02:20:00+07:00",{}))
        r=m.build_report(v1(),x,MAP)
        self.assertIn("current_dashboard_projection_used_as_source:some.dashboard",r["errors"])

    def test_effect_authority_remains_none(self):
        x=v2(); x["observations"][1]["effect_authority"]="WRITE"
        r=m.build_report(v1(),x,MAP)
        self.assertIn("unexpected_effect_authority:hanri.repository",r["errors"])

if __name__=="__main__":
    unittest.main()
