#!/usr/bin/env python3
from copy import deepcopy
import importlib.util,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
for name in ("authority_capture_refresh_v2","build_provider_surface_status_v2"):
 spec=importlib.util.spec_from_file_location(name,HERE/(name+".py")); mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);globals()[name]=mod
m=build_provider_surface_status_v2
a=authority_capture_refresh_v2

ROOT_MODIFIED={
 "CURRENT_POINTER.json":"2026-08-11T20:44:54.497Z",
 "CURRENT_STATE.json":"2026-08-11T20:24:59.622Z",
 "ROLE_INDEX.json":"2026-08-07T20:30:12.186Z",
 "ROLE_VIEWS.json":"2026-08-07T20:29:49.791Z",
 "MANIFEST.json":"2026-08-11T20:44:42.512Z",
}
def capture(when="2026-08-14T02:45:20+07:00"):
 roots={name:{**values,"modified_time":ROOT_MODIFIED[name]} for name,values in a.EXPECTED.items()}
 return {
  "schema":a.CAPTURE_SCHEMA,"capture_kind":a.CAPTURE_KIND,"provider":a.PROVIDER,
  "semantic_surface":a.SURFACE,"observed_at":when,"stable_roots":roots,
  "safety":{
   "provider_mutation_performed":False,"authority_granted":False,"registry_mutation_performed":False,
   "runtime_mutation_performed":False,"merge":False,"deploy":False,"can_trade":False,
   "capital_permission":"DENY","self_application":False,
  },
 }
def row(surface,dimension,source_class,when,freshness="CURRENT",identity=None):
 return {
  "semantic_surface":surface,"claim_dimension":dimension,"source_class":source_class,
  "source_id":"synthetic:"+surface,"source_scope":"TEST_FIXTURE","observed_at":when,
  "identity":identity or "synthetic:"+surface,"freshness":freshness,
  "claim_ceiling":"TEST_ONLY","effect_authority":"NONE","payload":{"freshness":freshness},
 }
AUTH_WHEN="2026-08-14T02:45:20+07:00"
CAP=capture(AUTH_WHEN)
SYNC={
 "schema":"control-center.sync-evidence.review.v2","observed_at":AUTH_WHEN,
 "observations":[
  row("r64.authority","authority","stable_authority_root",AUTH_WHEN,identity=a.EXPECTED["CURRENT_POINTER.json"]["sha256"]),
  row("hanri.repository","repository","github_provider","2026-08-14T01:20:00+07:00"),
  row("hanri.runtime","runtime","operator_terminal_receipt","2026-08-12T23:00:00+07:00"),
  row("hanri.projection","projection","provider_read","2026-08-14T00:10:00+07:00",freshness="STALE"),
 ]
}
NOW=a.parse_time("2026-08-14T02:55:00+07:00")
class T(unittest.TestCase):
 def test_fixture_is_exact_and_deterministic(self):
  self.assertEqual(a.validate_capture(CAP,now=NOW),[])
  self.assertEqual(a.current_row(SYNC)["observed_at"],AUTH_WHEN)
 def test_current_exact_after_applied_capture(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(s["authority_operator_state"],"CURRENT_EXACT");self.assertFalse(s["authority_hold_active"])
 def test_hanri_projection_stale_does_not_create_authority_hold(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertIn("hanri.projection",s["stale_or_blocked_surfaces"]);self.assertFalse(s["global_hold_derived_from_other_surface_staleness"]);self.assertFalse(s["authority_hold_active"])
 def test_surface_dimensions_preserved(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(s["surfaces"]["hanri.repository"]["claim_dimension"],"repository");self.assertEqual(s["surfaces"]["hanri.runtime"]["claim_dimension"],"runtime")
 def test_historical_authority_not_operator_surface(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(s["surfaces"]["r64.authority"]["observed_at"],AUTH_WHEN)
 def test_drift_hold_is_authority_scoped(self):
  c=deepcopy(CAP);c["stable_roots"]["MANIFEST.json"]["sha256"]="bad";s=m.build(SYNC,c,now=NOW);self.assertEqual(s["authority_operator_state"],"DRIFT_HOLD");self.assertTrue(s["authority_hold_active"])
 def test_invalid_capture_hold(self):
  c=deepcopy(CAP);c["provider"]="BAD";s=m.build(SYNC,c,now=NOW);self.assertEqual(s["authority_operator_state"],"INVALID_CAPTURE_HOLD")
 def test_expiry_hold(self):
  far=a.parse_time("2026-08-14T09:00:00+07:00");c=deepcopy(CAP);s=m.build(SYNC,c,now=far);self.assertEqual(s["authority_operator_state"],"EXPIRED_RECAPTURE");self.assertTrue(s["authority_hold_active"])
 def test_newer_exact_candidate_no_hold(self):
  c=deepcopy(CAP);c["observed_at"]="2026-08-14T02:56:00+07:00";now=a.parse_time("2026-08-14T02:56:00+07:00");s=m.build(SYNC,c,now=now);self.assertEqual(s["authority_operator_state"],"NEWER_EXACT_CAPTURE_CANDIDATE");self.assertFalse(s["authority_hold_active"])
 def test_no_effect_authority(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(m.validate(s),[]);self.assertFalse(s["safety"]["can_trade"]);self.assertEqual(s["safety"]["capital_permission"],"DENY")
 def test_stale_surface_cannot_clear_real_authority_drift(self):
  c=deepcopy(CAP);c["stable_roots"]["CURRENT_STATE.json"]["drive_file_id"]="bad";s=m.build(SYNC,c,now=NOW);self.assertTrue(s["authority_hold_active"]);self.assertIn("hanri.projection",s["stale_or_blocked_surfaces"])
if __name__=="__main__":unittest.main()
