# HANRI R39.1 — Attention Fabric

R39 proved the four-domain intelligence loop. R39.1 replaces the single hard-coded pilot fixture with a deterministic evidence-ingestion fabric.

## Real observation plane

Every producer writes an evidence envelope, not an action command:

- `HANRI_SELF_TRACE` — HANRI misses, stale assumptions, blind spots, recommendation failures.
- `AGENT_RETURN` — agent validation result, repeated failure, tool misuse, skill gap, quality drift.
- `SYSTEM_HEALTH` — system state, freshness, drift, failure or friction.
- `OPERATOR_EVENT` — repeated manual work, operator friction, context/decision burden.
- `RECOMMENDATION_OUTCOME` — measured outcome of a prior HANRI recommendation.
- `OBSERVATION` — explicit evidence-bound normalized observation for sources that already classify their own domain/signal.

Each envelope is bound to a canonical SHA-256. Duplicate `envelope_id` + same hash is deduped. Duplicate ID + different hash fails closed.

## Pipeline

```text
real source envelopes
→ canonical envelope ledger + hashes
→ deterministic domain adapters
→ R39 Attention Governor
→ findings + skill/system/operator/self proposals
→ deterministic priority ranking
→ Attention Fabric receipt
→ Control Center / operator review
```

The fabric deliberately does **not** infer healthy state from missing data. If one of SELF / AGENT / SYSTEM / OPERATOR has no evidence-backed observation, the R39 governor emits an attention blind spot and `coverage_complete=false`.

## Agent skill factory

Repeated agent failures, tool misuse, quality drift and explicit skill gaps can become `SKILL_CANDIDATE` proposals. These remain drafts until isolated evaluation and human acceptance. R39.1 never installs a skill.

## Outcome loop

`RECOMMENDATION_OUTCOME` envelopes close the learning loop. `VERIFIED_NO_EFFECT` and `REGRESSED` feed back into HANRI SELF audit; verified improvement is counted as positive outcome evidence.

## Host inbox

Windows pilot runner reads JSON envelopes from:

`%LOCALAPPDATA%\ControlCenterHANRIR39\attention_inbox`

The directory is an observation inbox only. The runner produces a receipt under the R39 receipt directory and performs zero provider effects.

## Effect boundary

R39.1 remains intelligence/proposal-only:

- self_apply=false
- skill_install=false
- system_write=false
- operator_message=false
- auto_dispatch=false
- external_messages=false
- can_trade=false
- capital_permission=DENY

Accepted proposals still flow through Control Center authority and the R37 Effect Gateway before any real reversible/irreversible effect.
