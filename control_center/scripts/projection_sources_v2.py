"""Read-only source adapters for Control Center projection v2."""
from __future__ import annotations
import datetime as dt, hashlib, json, re
from pathlib import Path
from typing import Any, Mapping, Sequence

_SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
_GEN_RE=re.compile(r"^R\d{1,6}$")
_FRESHNESS={"FRESH","STALE","UNKNOWN","UNAVAILABLE","IDENTITY_CONFLICT"}

def canonical_json(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def sha256_bytes(raw:bytes)->str: return hashlib.sha256(raw).hexdigest()
def sha256_json(value:Any)->str: return sha256_bytes(canonical_json(value))
def valid_sha(value:Any)->bool: return isinstance(value,str) and _SHA256_RE.fullmatch(value.lower()) is not None

def parse_time(value:Any)->dt.datetime:
    if not isinstance(value,str) or not value.strip(): raise ValueError("INVALID_TIME")
    raw=value.strip()
    if raw.endswith("Z"): raw=raw[:-1]+"+00:00"
    try: parsed=dt.datetime.fromisoformat(raw)
    except ValueError as exc: raise ValueError("INVALID_TIME") from exc
    if parsed.tzinfo is None: raise ValueError("TIME_MUST_BE_TIMEZONE_AWARE")
    return parsed.astimezone(dt.timezone.utc)

def read_json_bytes(path:Path)->tuple[dict[str,Any],bytes]:
    raw=path.read_bytes(); data=json.loads(raw.decode())
    if not isinstance(data,dict): raise ValueError("JSON_ROOT_MUST_BE_OBJECT")
    return data,raw

def adapt_legacy_provider_snapshot(snapshot:Mapping[str,Any])->dict[str,Any]:
    """Use ONLY canonical_roots. Ignore legacy github_lanes/hanri_evidence/return_registry."""
    if snapshot.get("schema")!="control_center.provider_snapshot.v1":
        return {"available":False,"reason":"PROVIDER_SNAPSHOT_SCHEMA_MISMATCH"}
    if snapshot.get("snapshot_kind")!="NON_AUTHORITY_PROVIDER_READBACK":
        return {"available":False,"reason":"PROVIDER_SNAPSHOT_KIND_MISMATCH"}
    roots=snapshot.get("canonical_roots")
    if not isinstance(roots,Mapping):
        return {"available":False,"reason":"CANONICAL_ROOTS_MISSING"}
    required=("generation","status","pointer_sha256","manifest_sha256","current_state_sha256","role_index_sha256","role_views_sha256","provider_readback")
    if any(roots.get(k) in (None,"") for k in required):
        return {"available":False,"reason":"CANONICAL_ROOTS_INCOMPLETE"}
    if not isinstance(roots["generation"],str) or not _GEN_RE.fullmatch(roots["generation"]):
        return {"available":False,"reason":"CANONICAL_GENERATION_INVALID"}
    if roots.get("status")!="ACTIVE":
        return {"available":False,"reason":"CANONICAL_STATUS_NOT_ACTIVE"}
    if roots.get("provider_readback")!="all_exact":
        return {"available":False,"reason":"CANONICAL_PROVIDER_READBACK_NOT_EXACT"}
    if roots.get("r63_is_current") is not False:
        return {"available":False,"reason":"CANONICAL_PREDECESSOR_FLAG_INVALID"}
    keys=("pointer_sha256","manifest_sha256","current_state_sha256","role_index_sha256","role_views_sha256")
    if any(not valid_sha(roots.get(k)) for k in keys):
        return {"available":False,"reason":"CANONICAL_ROOT_SHA_INVALID"}
    return {
        "available":True,"generation":roots["generation"],
        "pointer_sha256":roots["pointer_sha256"],
        "accepted_manifest_sha256":roots["manifest_sha256"],
        "current_state_sha256":roots["current_state_sha256"],
        "role_index_sha256":roots["role_index_sha256"],
        "role_views_sha256":roots["role_views_sha256"],
        "provider_readback":"all_exact"
    }

def adapt_return_live_index(live_index:Mapping[str,Any],*,raw_bytes:bytes|None=None)->dict[str,Any]:
    if live_index.get("schema")!="control_return_broker.v1.live_index":
        return {"available":False,"generation":None,"cursor_sha256":None,"semantic_authority":False,"reason":"RETURN_LIVE_INDEX_SCHEMA_MISMATCH"}
    generation=live_index.get("generation")
    if not isinstance(generation,str) or not _GEN_RE.fullmatch(generation):
        return {"available":False,"generation":None,"cursor_sha256":None,"semantic_authority":False,"reason":"RETURN_LIVE_INDEX_GENERATION_INVALID"}
    if not isinstance(live_index.get("slots"),Mapping):
        return {"available":False,"generation":generation,"cursor_sha256":None,"semantic_authority":False,"reason":"RETURN_LIVE_INDEX_SLOTS_INVALID"}
    if not isinstance(live_index.get("entry_count"),int) or live_index["entry_count"]<0:
        return {"available":False,"generation":generation,"cursor_sha256":None,"semantic_authority":False,"reason":"RETURN_LIVE_INDEX_ENTRY_COUNT_INVALID"}
    parse_time(live_index.get("updated_at_utc"))
    return {"available":True,"generation":generation,"cursor_sha256":sha256_bytes(raw_bytes) if raw_bytes is not None else sha256_json(live_index),"semantic_authority":False,"reason":None}

def _normalize_observation(observation:Mapping[str,Any],fetched_at:str)->dict[str,Any]:
    parse_time(fetched_at)
    sid=observation.get("source_id"); locator=observation.get("locator"); identity=observation.get("identity")
    observed_at=observation.get("observed_at"); freshness=observation.get("freshness"); payload=observation.get("payload"); required=observation.get("required_for",[])
    if not isinstance(sid,str) or not sid.strip(): raise ValueError("PROVIDER_SOURCE_ID")
    if not isinstance(locator,str) or not locator.strip(): raise ValueError("PROVIDER_LOCATOR")
    if not isinstance(identity,Mapping): raise ValueError("PROVIDER_IDENTITY")
    parse_time(observed_at)
    if not isinstance(freshness,Mapping): raise ValueError("PROVIDER_FRESHNESS")
    verdict=freshness.get("verdict")
    if verdict not in _FRESHNESS: raise ValueError("PROVIDER_FRESHNESS_VERDICT")
    if not isinstance(freshness.get("policy"),str) or not freshness["policy"]: raise ValueError("PROVIDER_FRESHNESS_POLICY")
    expires=freshness.get("expires_at")
    if expires is not None: parse_time(expires)
    if not isinstance(required,list): raise ValueError("PROVIDER_REQUIRED_FOR")
    return {
        "schema":"control_plane.projection_source_envelope.v2","source_id":sid.strip(),
        "source_class":"PROVIDER_OBSERVATION","authority_scope":"FACTUAL_ONLY","locator":locator.strip(),
        "identity":dict(identity),"observed_at":observed_at,"fetched_at":fetched_at,
        "freshness":{"verdict":verdict,"policy":freshness["policy"],"expires_at":expires},
        "payload_sha256":sha256_json(payload),"required_for":[str(x) for x in required]
    }

def normalize_provider_observations(observations:Sequence[Mapping[str,Any]],*,fetched_at:str)->list[dict[str,Any]]:
    normalized=[_normalize_observation(o,fetched_at) for o in observations]
    by_id={}
    for env in normalized: by_id.setdefault(env["source_id"],[]).append(env)
    result=[]
    for sid in sorted(by_id):
        rows=by_id[sid]
        signatures={(r["payload_sha256"],canonical_json(r["identity"]),r["locator"],r["observed_at"],canonical_json(r["required_for"])) for r in rows}
        if len(signatures)==1:
            result.append(sorted(rows,key=canonical_json)[0]); continue
        payload=[{"payload_sha256":r["payload_sha256"],"identity":r["identity"],"locator":r["locator"],"observed_at":r["observed_at"],"required_for":r["required_for"]} for r in sorted(rows,key=canonical_json)]
        newest=max(parse_time(r["observed_at"]) for r in rows)
        result.append({
            "schema":"control_plane.projection_source_envelope.v2","source_id":sid,
            "source_class":"PROVIDER_OBSERVATION","authority_scope":"FACTUAL_ONLY",
            "locator":"identity-conflict://"+sid,"identity":{"source_id":sid,"conflicting_observations":len(rows)},
            "observed_at":newest.isoformat().replace("+00:00","Z"),"fetched_at":fetched_at,
            "freshness":{"verdict":"IDENTITY_CONFLICT","policy":"duplicate-source-id-mismatch","expires_at":None},
            "payload_sha256":sha256_json(payload),
            "required_for":sorted({x for r in rows for x in r.get("required_for",[])})
        })
    return result

def load_authority_snapshot(path:Path)->dict[str,Any]:
    data,_=read_json_bytes(path); return adapt_legacy_provider_snapshot(data)
def load_return_cursor(path:Path)->dict[str,Any]:
    data,raw=read_json_bytes(path); return adapt_return_live_index(data,raw_bytes=raw)
def load_provider_observations(paths:Sequence[Path],*,fetched_at:str)->list[dict[str,Any]]:
    obs=[]
    for path in paths:
        data,_=read_json_bytes(path); obs.append(data)
    return normalize_provider_observations(obs,fetched_at=fetched_at)
