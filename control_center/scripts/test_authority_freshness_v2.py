#!/usr/bin/env python3
from __future__ import annotations
from copy import deepcopy
import importlib.util, sys, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("afv2",HERE/"validate_authority_freshness_v2.py")
m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)

def row(when="2026-08-14T02:00:11+07:00"):
    return {
      "semantic_surface":"r64.authority","claim_dimension":"authority","source_class":"stable_authority_root",
      "source_id":"roots","source_scope":"R64_STABLE_AUTHORITY","observed_at":when,"identity":m.EXPECTED_ROOTS["CURRENT_POINTER.json"],
      "freshness":"CURRENT","claim_ceiling":"BOUND_AUTHORITY_FACT_ONLY","effect_authority":"NONE",
      "payload":{
        "generation":"R64","status":"ACTIVE_RESEALED","provider_readback":"5_OF_5_EXACT",
        "roots":{k:{"bytes":1,"sha256":v} for k,v in m.EXPECTED_ROOTS.items()},
        "effect_ceiling":{"auto_accept":False,"auto_dispatch":False,"can_trade":False,"capital_permission":"DENY","self_application":False}
      }
    }

def data():
    return {"schema":m.SCHEMA,"observations":[row()]}

NOW=m.parse_time("2026-08-14T02:32:00+07:00")

class Tests(unittest.TestCase):
    def test_current_exact_passes(self): self.assertEqual(m.validate(data(),now=NOW),[])
    def test_stale_fails(self):
        x=data(); x["observations"][0]["observed_at"]="2026-08-13T18:00:00+07:00"
        self.assertIn("authority_freshness_stale",m.validate(x,now=NOW))
    def test_future_fails(self):
        x=data(); x["observations"][0]["observed_at"]="2026-08-14T02:40:00+07:00"
        self.assertIn("authority_freshness_from_future",m.validate(x,now=NOW))
    def test_hash_drift_fails(self):
        x=data(); x["observations"][0]["payload"]["roots"]["MANIFEST.json"]["sha256"]="bad"
        self.assertIn("root_sha_mismatch:MANIFEST.json",m.validate(x,now=NOW))
    def test_repo_source_cannot_prove_authority(self):
        x=data(); x["observations"][0]["source_class"]="github_provider"
        self.assertIn("source_class_mismatch",m.validate(x,now=NOW))
    def test_effect_authority_leak_fails(self):
        x=data(); x["observations"][0]["effect_authority"]="WRITE"
        self.assertIn("effect_authority_leak",m.validate(x,now=NOW))
    def test_capital_leak_fails(self):
        x=data(); x["observations"][0]["payload"]["effect_ceiling"]["capital_permission"]="ALLOW"
        self.assertIn("capital_authority_leak",m.validate(x,now=NOW))
    def test_multiple_current_authority_rows_fail(self):
        x=data(); x["observations"].append(deepcopy(x["observations"][0]))
        self.assertIn("current_r64_authority_observation_count:2",m.validate(x,now=NOW))
    def test_global_top_level_observed_at_irrelevant(self):
        x=data(); x["observed_at"]="1999-01-01T00:00:00+00:00"
        self.assertEqual(m.validate(x,now=NOW),[])

if __name__=="__main__":
    unittest.main()
