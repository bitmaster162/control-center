from __future__ import annotations
import hashlib, json, pytest
from control_center.scripts.projection_sources_v2 import adapt_legacy_provider_snapshot, adapt_return_live_index, normalize_provider_observations

h=lambda s: hashlib.sha256(s.encode()).hexdigest()

def snapshot():
    return {"schema":"control_center.provider_snapshot.v1","snapshot_kind":"NON_AUTHORITY_PROVIDER_READBACK",
    "canonical_roots":{"generation":"R64","status":"ACTIVE","pointer_sha256":h("p"),"manifest_sha256":h("m"),"current_state_sha256":h("s"),"role_index_sha256":h("ri"),"role_views_sha256":h("rv"),"provider_readback":"all_exact","r63_is_current":False},
    "github_lanes":{"control_center":{"head_sha":"8969c264d505a6d5cb8590eb5a1b74b461f0b19c"}}}

def live():
    return {"schema":"control_return_broker.v1.live_index","generation":"R59","updated_at_utc":"2026-08-15T17:00:00Z","slots":{},"entry_count":11}

def obs(head="new",verdict="FRESH"):
    return {"source_id":"github:cc","locator":"github://cc","identity":{"repo":"cc","ref":"lane"},"observed_at":"2026-08-15T17:01:00Z",
    "freshness":{"verdict":verdict,"policy":"per-compile","expires_at":None},"payload":{"head_sha":head},"required_for":[]}

def test_legacy_only_exports_canonical_roots():
    a=adapt_legacy_provider_snapshot(snapshot()); raw=json.dumps(a)
    assert a["available"] is True and a["generation"]=="R64"
    assert "8969c264d505a6d5cb8590eb5a1b74b461f0b19c" not in raw and "github_lanes" not in raw

def test_bad_legacy_fails_closed():
    s=snapshot(); s["canonical_roots"]["provider_readback"]="partial"
    assert adapt_legacy_provider_snapshot(s)["available"] is False

def test_return_cursor_is_transport_only():
    x=live(); raw=(json.dumps(x)+"\n").encode(); c=adapt_return_live_index(x,raw_bytes=raw)
    assert c["available"] is True and c["semantic_authority"] is False
    assert c["cursor_sha256"]==hashlib.sha256(raw).hexdigest()

def test_bad_return_schema_unavailable():
    x=live(); x["schema"]="bad"; assert adapt_return_live_index(x)["available"] is False

def test_provider_is_factual_only():
    r=normalize_provider_observations([obs()],fetched_at="2026-08-15T17:02:00Z")[0]
    assert r["source_class"]=="PROVIDER_OBSERVATION" and r["authority_scope"]=="FACTUAL_ONLY"

def test_exact_duplicate_dedupes():
    o=obs(); assert len(normalize_provider_observations([o,dict(o)],fetched_at="2026-08-15T17:02:00Z"))==1

def test_conflicting_duplicate_holds_identity():
    r=normalize_provider_observations([obs("old"),obs("new")],fetched_at="2026-08-15T17:02:00Z")
    assert len(r)==1 and r[0]["freshness"]["verdict"]=="IDENTITY_CONFLICT"

def test_provider_cannot_choose_authority():
    o=obs(); o["source_class"]="CANONICAL_AUTHORITY"; o["authority_scope"]="HUMAN"; o["payload"]["effect_authorized"]=True
    r=normalize_provider_observations([o],fetched_at="2026-08-15T17:02:00Z")[0]
    assert r["source_class"]=="PROVIDER_OBSERVATION" and r["authority_scope"]=="FACTUAL_ONLY"

def test_bad_freshness_rejected():
    o=obs(); o["freshness"]["verdict"]="TRUST_ME"
    with pytest.raises(ValueError,match="PROVIDER_FRESHNESS_VERDICT"):
        normalize_provider_observations([o],fetched_at="2026-08-15T17:02:00Z")
