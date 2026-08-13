#!/usr/bin/env python3
from copy import deepcopy
import importlib.util,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
for name in ("authority_capture_refresh_v2","build_provider_surface_status_v2"):
 spec=importlib.util.spec_from_file_location(name,HERE/(name+".py")); mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);globals()[name]=mod
m=build_provider_surface_status_v2
SYNC=json.loads((HERE.parent/"data"/"current_sync_evidence.review.v2.json").read_text())
CAP=json.loads((HERE.parent/"data"/"authority_refresh_capture.readonly.v2.json").read_text())
NOW=authority_capture_refresh_v2.parse_time("2026-08-14T02:55:00+07:00")
class T(unittest.TestCase):
 def test_current_exact_after_applied_capture(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(s["authority_operator_state"],"CURRENT_EXACT");self.assertFalse(s["authority_hold_active"])
 def test_hanri_projection_stale_does_not_create_authority_hold(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertIn("hanri.projection",s["stale_or_blocked_surfaces"]);self.assertFalse(s["global_hold_derived_from_other_surface_staleness"]);self.assertFalse(s["authority_hold_active"])
 def test_surface_dimensions_preserved(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(s["surfaces"]["hanri.repository"]["claim_dimension"],"repository");self.assertEqual(s["surfaces"]["hanri.runtime"]["claim_dimension"],"runtime")
 def test_historical_authority_not_operator_surface(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(s["surfaces"]["r64.authority"]["observed_at"],"2026-08-14T02:45:20+07:00")
 def test_drift_hold_is_authority_scoped(self):
  c=deepcopy(CAP);c["stable_roots"]["MANIFEST.json"]["sha256"]="bad";s=m.build(SYNC,c,now=NOW);self.assertEqual(s["authority_operator_state"],"DRIFT_HOLD");self.assertTrue(s["authority_hold_active"])
 def test_invalid_capture_hold(self):
  c=deepcopy(CAP);c["provider"]="BAD";s=m.build(SYNC,c,now=NOW);self.assertEqual(s["authority_operator_state"],"INVALID_CAPTURE_HOLD")
 def test_expiry_hold(self):
  far=authority_capture_refresh_v2.parse_time("2026-08-14T09:00:00+07:00");c=deepcopy(CAP);c["observed_at"]="2026-08-14T02:45:20+07:00";s=m.build(SYNC,c,now=far);self.assertEqual(s["authority_operator_state"],"EXPIRED_RECAPTURE");self.assertTrue(s["authority_hold_active"])
 def test_newer_exact_candidate_no_hold(self):
  c=deepcopy(CAP);c["observed_at"]="2026-08-14T02:56:00+07:00";now=authority_capture_refresh_v2.parse_time("2026-08-14T02:56:00+07:00");s=m.build(SYNC,c,now=now);self.assertEqual(s["authority_operator_state"],"NEWER_EXACT_CAPTURE_CANDIDATE");self.assertFalse(s["authority_hold_active"])
 def test_no_effect_authority(self):
  s=m.build(SYNC,CAP,now=NOW);self.assertEqual(m.validate(s),[]);self.assertFalse(s["safety"]["can_trade"]);self.assertEqual(s["safety"]["capital_permission"],"DENY")
 def test_stale_surface_cannot_clear_real_authority_drift(self):
  c=deepcopy(CAP);c["stable_roots"]["CURRENT_STATE.json"]["drive_file_id"]="bad";s=m.build(SYNC,c,now=NOW);self.assertTrue(s["authority_hold_active"]);self.assertIn("hanri.projection",s["stale_or_blocked_surfaces"])
if __name__=="__main__":unittest.main()
