# GMH DELTA R27 — CLAUDE COWORK SECURITY + COMMERCIAL LINEAGE

**Recorded:** 2026-08-22T11:22:04+07:00  
**Mode:** evidence ingest / current-provider readback / no operational effects

## New evidence

### Cowork source safety

Raw Claude Cowork session `bb66f3b3-cee5-425c-9447-ef4aea0805cf` is now classified:

`CONTAMINATED_SOURCE / SECRET_BEARING`

Path-only census, without opening credential contents:
- 54 `.credentials.json`
- 213 `.audit-key`
- 106 paths with credential/auth/token/secret/API-key-like names
- 223 Claude/config-like paths

Policy:
- raw Cowork archive MUST NOT be sent wholesale to GPT/Claude/external research;
- research receives sanitized derived extracts only;
- provenance/redaction/loss must be explicit;
- historical credential material must not be used for authentication;
- rotation status is `UNKNOWN_UNLESS_FRESHLY_PROVIDER_VERIFIED`.

### Memory-space index

123 space-memory files resolve into three Cowork spaces:
- space `411f...`: 31 — ContinuityOS, frontiers, done ledger, agent system, deployment references;
- space `6305...`: 52 — Binance/OKX/NFT runtime/project history;
- space `fc8e...`: 40 — Arena, ContinuityOS pivot/product, Fable, BitEvo and research lineage.

### Historical CurrentTruth lineage

Recovered real failure classes:
- `DRIVE_UPLOAD_TIME != SOURCE_EVENT_TIME`
- `SOURCE_STATE != DEPLOYMENT_STATE`
- `CONFIG_CORRECT != RUNTIME_RUNNING`
- `HISTORICAL_RUNTIME != CURRENT_RUNTIME`
- `SPEC_PROPOSES != IMPLEMENTATION_OBSERVED_AS`
- `PREVIEW_READY != PRODUCTION_PROMOTION`
- `PREEXEC_FAILURE != BUILD_CODE_FAILURE`
- `AGENT_MEMORY_CLAIM != CURRENT_PROVIDER_STATE`
- `HISTORICAL_TRADING_RUNTIME != CURRENT_TRADING_AUTHORITY`
- `RAW_SECRET_BEARING_ARCHIVE != SAFE_RESEARCH_SOURCE`
- `OBSERVED_EFFECT != AUTHORITY_TO_REPEAT`
- `LIVE_OFFER != PAYMENT_PROOF`

Executable Cowork Historical CurrentTruth Bench: **23/23 PASS** over 12 fixtures.

## P0 CASH causal lineage

Historical source-backed chain:

1. `project_frontiers.md` / 2026-04-27:
   one active cash lane; then Inner Circle.
2. `project_final_extract_arena_20260721.md` / 2026-07-21:
   revenue-zero/build:sell diagnosis and material correction toward **AI-Agent Reliability Audit**, with an approximately `$1.5k` paid wedge.
3. Fresh Vercel provider read / 2026-08-22:
   - production `dpl_7coXfJt5BHYubLMejnpnt5q9rJH9`
   - READY / target production
   - `main@6a9d20537da01f9e5cb1ae1a06d627f2fa0f9e00`
   - `/agent-authority-audit` HTTP 200
   - `/pricing` HTTP 200
   - Entry Audit `$1,500`
   - Agent Authority & Evidence Audit `$4,900`
   - public intake grants no testing authority
   - payment proof absent.

Terminal:
`COMMERCIAL_CAUSAL_SPINE_SOURCE_BACKED / LIVE_OFFER / NO_PAYMENT_PROOF`

## BitEvo preview/current-production distinction

Fresh Vercel:
- PR #8 candidate preview `dpl_F7yDkGh9aZ8Nwp5f9mG2L9JqkmiX` = READY
- branch/head `agent/provider-context-quality-gate-fix@8e230699baa19561ed3189cb53f7e769ac9d985b`
- target = preview/null, not production.

Fresh GitHub:
- PR #8 OPEN
- draft=true
- merged=false
- base `main@6a9d20537da01f9e5cb1ae1a06d627f2fa0f9e00`
- head `8e230699baa19561ed3189cb53f7e769ac9d985b`

Production remains main `6a9d205...`.

Therefore:
`PREVIEW_READY != PRODUCTION_PROMOTION != CI_PASS`.

The preview is useful provider-build evidence but does not resolve the zero-step GitHub CI failure or grant merge/deploy authority.

## Research

Actual Claude Web Deep Research R2 is still outstanding.
GPT Deep Research R3 remains HOLD.

When dispatched, GPT R3 may receive only sanitized Cowork-derived evidence, never the raw Cowork tree/ZIP.

## Authority

No merge, deploy, runtime mutation, credential use, outreach, testing, payment, trading or capital authority granted.
`can_trade=false`
`capital_permission=DENY`
