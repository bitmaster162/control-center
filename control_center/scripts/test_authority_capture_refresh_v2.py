#!/usr/bin/env python3
from copy import deepcopy
import importlib.util,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("r",HERE/"authority_capture_refresh_v2.py"); m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
CAP=json.loads((HERE.parent/"data"/"authority_refresh_capture.readonly.v2.json").read_text())
def sync(when="2026-08-14T02:00:11+07:00"):
 return {"schema":"control-center.sync-evidence.review.v2","observed_at":when,"observations":[{
  "semantic_surface":"r64.authority","claim_dimension":"authority","source_class":"stable_authority_root","source_id":"old",
  "source_scope":"R64_STABLE_AUTHORITY","observed_at":when,"identity":m.EXPECTED["CURRENT_POINTER.json"]["sha256"],
  "freshness":"CURRENT","claim_ceiling":"BOUND_AUTHORITY_FACT_ONLY","effect_authority":"NONE","payload":{"generation":"R64"}
 }]}
NOW=m.parse_time("2026-08-14T02:45:20+07:00")
class T(unittest.TestCase):
 def test_real_capture_newer_candidate(self):
  x=m.classify(sync(),CAP,now=NOW); self.assertEqual(x["verdict"],"NEWER_EXACT_CAPTURE_CANDIDATE"); self.assertTrue(x["refresh_allowed"])
 def test_same_capture_no_refresh(self):
  self.assertEqual(m.classify(sync(CAP["observed_at"]),CAP,now=NOW)["verdict"],"CURRENT_NO_REFRESH")
 def test_stale_current_requires_newer_capture(self):
  old=sync("2026-08-13T18:00:00+07:00"); cap=deepcopy(CAP);cap["observed_at"]="2026-08-13T18:00:00+07:00"
  self.assertEqual(m.classify(old,cap,now=NOW)["verdict"],"EXPIRED_RECAPTURE")
 def test_hash_drift_holds(self):
  c=deepcopy(CAP);c["stable_roots"]["MANIFEST.json"]["sha256"]="bad";self.assertEqual(m.classify(sync(),c,now=NOW)["verdict"],"DRIFT_HOLD")
 def test_id_drift_holds(self):
  c=deepcopy(CAP);c["stable_roots"]["CURRENT_STATE.json"]["drive_file_id"]="bad";self.assertEqual(m.classify(sync(),c,now=NOW)["verdict"],"DRIFT_HOLD")
 def test_pointer_order_drift_holds(self):
  c=deepcopy(CAP);c["stable_roots"]["CURRENT_STATE.json"]["modified_time"]="2026-08-12T20:44:55Z";self.assertEqual(m.classify(sync(),c,now=NOW)["verdict"],"DRIFT_HOLD")
 def test_invalid_provider_fails(self):
  c=deepcopy(CAP);c["provider"]="OTHER";self.assertEqual(m.classify(sync(),c,now=NOW)["verdict"],"INVALID_CAPTURE")
 def test_future_capture_invalid(self):
  c=deepcopy(CAP);c["observed_at"]="2026-08-14T03:00:00+07:00";self.assertEqual(m.classify(sync(),c,now=NOW)["verdict"],"INVALID_CAPTURE")
 def test_safety_leak_invalid(self):
  c=deepcopy(CAP);c["safety"]["provider_mutation_performed"]=True;self.assertEqual(m.classify(sync(),c,now=NOW)["verdict"],"INVALID_CAPTURE")
 def test_candidate_only_authority_surface(self):
  x=m.classify(sync(),CAP,now=NOW);self.assertEqual(x["allowed_update_surface"],"r64.authority");self.assertFalse(x["all_other_surfaces_write_allowed"])
 def test_apply_marks_old_historical(self):
  x=m.classify(sync(),CAP,now=NOW);out=m.apply_candidate(sync(),x["candidate_observation"]);rows=[r for r in out["observations"] if r["semantic_surface"]=="r64.authority"]
  self.assertEqual(len(rows),2);self.assertEqual(sum(r["freshness"]=="CURRENT" for r in rows),1);self.assertEqual(sum(r["freshness"]=="HISTORICAL" for r in rows),1)
 def test_candidate_preserves_effect_ceiling(self):
  x=m.classify(sync(),CAP,now=NOW);e=x["candidate_observation"]["payload"]["effect_ceiling"];self.assertFalse(e["can_trade"]);self.assertEqual(e["capital_permission"],"DENY");self.assertFalse(e["self_application"])
if __name__=="__main__":unittest.main()
