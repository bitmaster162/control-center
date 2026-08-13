#!/usr/bin/env python3
from __future__ import annotations
from copy import deepcopy
import importlib.util, json, sys, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("sync",HERE/"control_center_sync_gate_v2.py")
m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
DATA=json.loads((HERE.parent/"data"/"current_sync_evidence.review.v2.json").read_text(encoding="utf-8"))
RAW=DATA["observations"]

def snap():
    return m.build(DATA)

class SyncV2Tests(unittest.TestCase):
    def test_current_fixture_builds(self):
        s=snap()
        self.assertEqual(s["authority"]["generation"],"R64")
        self.assertEqual(s["hanri"]["runtime_state"]["label"],"R39.6.1.1 ACCEPTED_LIVE")
        self.assertEqual(s["hanri"]["repo_state"]["head"],"ef5c504179de8ae8c16bd70c168b14b79bd2f466")
        self.assertEqual(s["freshness"]["projection_freshness"],"STALE")
        self.assertEqual(s["collaboration"]["anchor_freshness"],"STALE")

    def test_dashboard_cannot_prove_authority(self):
        x=deepcopy(RAW[0]); x["source_class"]="dashboard_projection"
        with self.assertRaisesRegex(ValueError,"SOURCE_NOT_ALLOWED"):
            m.normalize([x])

    def test_github_repo_source_cannot_prove_live_runtime(self):
        x=deepcopy(next(v for v in RAW if v["semantic_surface"]=="hanri.runtime"))
        x["source_class"]="github_provider"
        with self.assertRaisesRegex(ValueError,"SOURCE_NOT_ALLOWED"):
            m.normalize([x])

    def test_duplicate_source_id_conflict_fails(self):
        x=deepcopy(RAW[0]); y=deepcopy(x); y["identity"]="different"
        with self.assertRaisesRegex(ValueError,"SOURCE_ID_REUSED_WITH_DIFFERENT_IDENTITY"):
            m.normalize([x,y])

    def test_same_rank_newer_provider_wins(self):
        a=deepcopy(next(v for v in RAW if v["semantic_surface"]=="hanri.repository"))
        a["source_id"]="old"; a["observed_at"]="2026-08-14T01:00:00+07:00"; a["identity"]="aaa"; a["payload"]["head"]="aaa"
        b=deepcopy(a); b["source_id"]="new"; b["observed_at"]="2026-08-14T01:10:00+07:00"; b["identity"]="bbb"; b["payload"]["head"]="bbb"
        top,_=m.select(m.normalize([a,b]),"hanri.repository")
        self.assertEqual(top["source_id"],"new")

    def test_newer_lower_authority_does_not_override_provider(self):
        a=deepcopy(next(v for v in RAW if v["semantic_surface"]=="hanri.repository"))
        b=deepcopy(a); b["source_class"]="owner_narrative"; b["source_id"]="owner"; b["identity"]="different"; b["observed_at"]="2026-08-14T01:40:00+07:00"
        top,w=m.select(m.normalize([a,b]),"hanri.repository")
        self.assertEqual(top["source_class"],"github_provider")
        self.assertIn("NEWER_LOWER_AUTHORITY_EVIDENCE_DIFFERS:hanri.repository",w)

    def test_equal_priority_same_time_conflict_blocks(self):
        a=deepcopy(next(v for v in RAW if v["semantic_surface"]=="hanri.repository"))
        b=deepcopy(a); b["source_id"]="conflict"; b["identity"]="different"
        with self.assertRaisesRegex(ValueError,"EQUAL_PRIORITY_IDENTITY_CONFLICT"):
            m.select(m.normalize([a,b]),"hanri.repository")

    def test_missing_required_surface_fails(self):
        d=deepcopy(DATA); d["observations"]=[x for x in RAW if x["semantic_surface"]!="hanri.runtime"]
        with self.assertRaisesRegex(ValueError,"MISSING_REQUIRED_SURFACES:hanri.runtime"):
            m.build(d)

    def test_shell_runtime_mismatch_fails(self):
        s=snap(); s["visible_shell"]["hanri_runtime"]="R36 LIVE"
        e,_=m.validate(s)
        self.assertIn("VISIBLE_RUNTIME_MISMATCH",e)

    def test_repo_merge_is_not_runtime_proof(self):
        s=snap(); s["hanri"]["runtime_state"]["source_class"]="github_provider"
        e,_=m.validate(s)
        self.assertIn("LIVE_RUNTIME_WITHOUT_RUNTIME_SOURCE",e)

    def test_codex05_freshness_does_not_lift_do_not_touch(self):
        s=snap(); s["agent_slots"]["CODEX-05"]["freshness"]="CURRENT"; s["agent_slots"]["CODEX-05"]["promotion_eligible"]=True
        e,_=m.validate(s)
        self.assertIn("CODEX05_DO_NOT_TOUCH_PROMOTION_DRIFT",e)

    def test_stale_projection_publishable_only_as_stale(self):
        g=m.gate(snap())
        self.assertTrue(g["publishable"])
        self.assertEqual(g["status"],"PUBLISHABLE_STALE_ONLY")
        self.assertIn("PUBLISH_ONLY_WITH_VISIBLE_STALE_LABEL",g["warnings"])

    def test_require_current_blocks_stale(self):
        g=m.gate(snap(),True)
        self.assertFalse(g["publishable"])
        self.assertIn("PROJECTION_NOT_CURRENT",g["blockers"])

    def test_effect_ceiling_cannot_broaden(self):
        s=snap(); s["effects"]["can_trade"]=True; s["effects"]["capital_permission"]="ALLOW"
        e,_=m.validate(s)
        self.assertIn("TRADING_AUTHORITY_BROADENED",e)
        self.assertIn("CAPITAL_AUTHORITY_BROADENED",e)

    def test_r52_r57_relation(self):
        d=snap()["continuityos"]["historical_local_adoption"]
        self.assertEqual(d["runtime_adoption"],"R57_REVISE_NO_LIVE_ACTIVATION")
        self.assertFalse(d["live_activation"])

    def test_r57_revise_cannot_assert_live_activation(self):
        r57=deepcopy(DATA["continuityos_r57"]); r57["live_activation"]=True
        with self.assertRaisesRegex(ValueError,"R57_REVISE_CANNOT_ASSERT_LIVE_ACTIVATION"):
            m.adjudicate_r52_r57(DATA["continuityos_r52"],r57)

    def test_visionassist_is_custody_pending(self):
        self.assertEqual(snap()["projects"]["VisionAssist"]["status"],"GITHUB_OWNER_TRANSFER_SENT_CUSTODY_PENDING")

    def test_comment_requires_exact_send(self):
        self.assertEqual(m.validate_write_guard("GITHUB_COMMENT"),"DENY_NO_EXACT_SEND")

    def test_review_write_requires_fresh_pr(self):
        self.assertEqual(m.validate_write_guard("GITHUB_REVIEW_BRANCH_WRITE"),"DENY_NO_FRESH_PR_READBACK")
        self.assertEqual(m.validate_write_guard("GITHUB_REVIEW_BRANCH_WRITE",fresh_pr=True),"ALLOW")

    def test_merge_requires_exact_effect(self):
        self.assertEqual(m.validate_write_guard("GITHUB_MERGE"),"DENY_NO_EXACT_EFFECT_GATE")

    def test_trading_capital_always_denied(self):
        self.assertEqual(m.validate_write_guard("TRADING_OR_CAPITAL",exact_effect=True),"DENY_TRADING_CAPITAL_CEILING")

if __name__=="__main__":
    unittest.main()
