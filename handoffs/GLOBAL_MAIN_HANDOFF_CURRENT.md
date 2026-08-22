# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T08:58:56+07:00

## Canonical location
`bitmaster162/control-center` → `global/main-handoff-current` → `handoffs/GLOBAL_MAIN_HANDOFF_CURRENT.md`

Provider physical evidence overrides stale handoff text.

## Hard authority boundary
`source != build != deployment != runtime != effect != authority`

Defaults unless a fresher exact project gate overrides them:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge/deploy/runtime mutation solely from this handoff
- no workflow rerun solely from this handoff
- no destructive Drive action solely from this handoff
- generic `го` is not an exact destructive approval token

---

# 1. Accepted global responsibility map

`Robert/Human Sovereign → Control Center → {HANRI, TRIAXIS} → Knowledge Foundry → {ContinuityOS, ArchiveOS} → EvidenceStore → {SCT, Retrieval/Graph} → domain products`

- Control Center: accepted intent/current-truth projection/effect gate.
- HANRI: freshness/contradiction/attention/shadow proposals; no self-approval.
- TRIAXIS: logically independent adversarial verifier.
- ContinuityOS: event/replay/continuity semantics.
- ArchiveOS: exact raw evidence/provenance custody.
- Knowledge Foundry: claims/evidence/contradictions/causal processing; no truth self-promotion.
- EvidenceStore: one canonical relational backend per runtime; PostgreSQL production target; bitemporal `valid_time` + `transaction_time`.
- pgvector/lexical/graph: derived retrieval/projections only.
- SCT: provider-independent Person/Decision Twin; `execution_authority=NONE`.
- BitEvo: commercial/operator umbrella, not infrastructure truth owner.
- Pandora: graph/epoch/time/causal visualization + optional simulation projection; no canonical authority.

Logical responsibility and physical storage/process topology are different decisions. Shared PostgreSQL does not require a monolith.

---

# 2. P0 CORE — Causal Spine

Rule: `ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`.
Missing/unproven frontier => `CAUSAL_SPINE_INCOMPLETE`.
`NO_MATERIAL_PIVOT_FOUND` requires bounded-search evidence.
Causal pass never grants source/canonical/merge/deploy/runtime/trading/capital/effect authority.

## Live lane
- repo: `bitmaster162/continuityos`
- Issue #111
- Draft PR #115
- branch `agent/causal-spine-v1`
- base `master@021e2d521efc4df0ce390b38a919bc2f0b675460`
- fresh head `8753edf511ec9cc195ca0369a8741279a5eda5a8`
- PR OPEN / DRAFT / UNMERGED / mergeable
- 25 commits
- 11 changed files
- 1460 additions / 0 deletions

Scope: Causal Spine implementation, 3 strict schemas, CausalBench v0, causal tests, schema package tests, one package-data line in `pyproject.toml`.

Closed/regression-covered:
- CS-R1 cross-subject current-state binding
- CS-R2 rehashed authority/effect laundering
- CS-R3 `state_id` evidence binding

## Exact benchmark/wheel gate
Superseded head `c2da7c2...` proved CausalBench in clean-source full pytest but exposed a wheel-boundary error because source-only `bench/` is intentionally not shipped.

Current head `8753edf5...` corrects that boundary:
- source/editable CI executes CausalBench v0;
- wheel-only skips only when the parent package `bench` itself is absent;
- all other missing-module errors re-raise;
- benchmark code is not added to the production wheel.

Fresh exact-head evidence currently:
- CodeQL run `32544706731`: PASS
- P0 Unified Shadow Continuity `32544706744`: PASS
- review-gates `32544706828`: IN PROGRESS at last read
  - Ubuntu Python 3.11: PASS end-to-end
  - Windows Python 3.11: clean-source PASS; wheel-only test in progress at last read

Ubuntu exact-head proof includes:
- clean-source full pytest: `1165 passed, 12 skipped, 8 subtests passed`
- CausalBench test collected/executed in that source run
- wheel build PASS with Causal Spine module + 3 schemas packaged
- wheel-only pytest: `1140 passed, 21 skipped, 8 subtests passed`
- editable full pytest: `1165 passed, 12 skipped, 8 subtests passed`
- governance corpus 30/30 agreement, 22/22 risky not auto-run, 8/8 adversarial dangerous not auto-run
- portable hardening 10/10 PASS
- Linux realpath/symlink regression PASS
- secret scan finding_count 0 excluding known fixture

No workflow rerun requested.

**Next P0 action:** exact-head Windows/review-gates readback → reconcile PR #115 stale body → COMMENT technical review (not self-APPROVE) → keep draft/unmerged.

---

# 3. Memory / knowledge / trajectory direction

Universal Artifact Identity binds source/provider IDs, provider revision, locator, raw SHA-256, size/type, observed time, custody role, parent/derived relations and semantic family.

Dedup:
- T0 EXACT = same bytes/hash
- T1 DERIVED = same logical object, different representation/version/export
- T2 RELATED = distinct evidence for same event/decision/project state

Universal ingestion:
`DISCOVER → IDENTIFY → HASH RAW → PRESERVE RAW → PARSE → NORMALIZE → CLASSIFY → DEDUP → SEMANTIC FAMILY → AUTHORSHIP → PROVENANCE → EVENTS → CAUSAL FRONTIERS → CONTRADICTIONS → CURRENT STATE → SQL → READBACK → RETRIEVAL → GRAPH`.

Agent Trajectory Bundle remains provider-neutral and content-addressed. OpenTelemetry/OpenInference may be interop mappings, not canonical replacement.

A2A/MCP/framework choice remains benchmark-first.

---

# 4. Gemini cluster / Claude adjudication

Four Gemini Deep Research outputs were treated as one correlated research cluster.

Accepted direction: Causal Spine, bitemporal EvidenceStore, raw CAS, derived retrieval, governed fleet, trajectory archive, provider readback, authority-leak/confused-deputy security, benchmark program, Agent Authority & Evidence Audit wedge.

Held for Claude: ArchiveOS topology; ContinuityOS service/storage split; HANRI vs Control Center; Return Broker; SQLite edge; TRIAXIS structure; Pandora scope; Python vs mandatory Rust; standards/framework choices; commercial portfolio strategy.

Rejected from automatic Gemini adoption: blanket product KILL/FREEZE, freeze-all-non-core, immediate DNS/product shutdowns, mandatory revenue/pricing numbers, enterprise-only destruction of broader portfolio.

Claude received sealed review packet. No Claude output has been accepted yet.

---

# 5. Product / commercial census — fresh delta R2

Durable evidence artifact: `/GLOBAL_MAIN_HANDOFF/PRODUCT_PORTFOLIO_CENSUS_DELTA_R2_20260822.md`.

Current portfolio ontology is **not** “44 independent businesses” and **not** “one mega-monolith”. Maintain:
1. Canonical Portfolio Register
2. Extended Strategic Program Register
3. Alias/Family Register
4. Parent–Child/Dependency Graph
5. Commercial Priority Register

Rules:
- `Commercial priority != architectural importance`
- `Not in one registry != nonexistent`
- `Alias != project identity`
- `Component != product`
- `Research program != runtime`
- conceptual similarity is `UNPROVEN_RELATION` until source/interface/data-flow/runtime evidence exists

## Revenue-now internal lanes
- 7-Day Operator Decision Sprint: `SELLABLE_MANUAL_PILOT_PENDING`; working `SELL_NOW`, payment proof absent.
- AI-Agent Reliability Audit: `PUBLIC_OFFER_NO_PAYMENT_PROOF`; working `SELL_NOW`, delivery/payment proof absent.
- Blockchain Forensics / OSINT: active personal-investigation lane exists; commercial service remains separate and requires provenance/legal/case separation.

## Key product corrections
- Crypto Guides: internal `PUBLIC_LIVE_EDITORIAL_AUDIT`; GitHub source exists with restored 162-guide state. `FINISH_FIRST/CURRENTNESS_REVERIFY`, not blanket KILL.
- VisionAssist: internal P0 `R57_IN_PROGRESS`, empirical evidence gate; GitHub shows fresh merge activity on 2026-08-22. `FINISH_FIRST`.
- OKX NFT / Parasite line: GitHub shows fresh R90 safety merge activity on 2026-08-22. No blanket KILL without product-specific current/effect/commercial audit.
- AI Skill Lab: GitHub shows R70 commercial-parity merge on 2026-08-21. No blanket FREEZE from Gemini hypothesis.
- AXIOM Game / Parasite Hunter: separate internal P1, empirical proof gate; `FINISH_FIRST/EMPIRICAL_PROOF` pending current source mapping.
- Fable 5 Observer vs Fable5 platform package: `ENTITY_SPLIT_REQUIRED`; do not silently merge identities.
- Amora: internal `PARKED`; `$AMORA` holds with parent; working `FREEZE/HOLD` until explicit revival.
- LifeOS × MAWorld × HANRI: strategic proof program, not one product; synthetic-only/no external effect for first habitat.
- Forge/Foundry variants: merge lock; `ENTITY_RECAPTURE_REQUIRED`.
- Pandora: queued strategic proof, no truth authority.

Fresh owner GitHub surface currently exposes 15 repositories. Fable/AXIOM/Amora/LifeOS/MAWorld/Pandora are not separate visible owner repos there, so their currentness must be reconstructed from Library/Drive/local handoffs rather than inferred from GitHub absence.

Best current portfolio strategy remains:
`one paid manual pilot + one P0 core infrastructure frontier + bounded finish-to-market/proof lanes`.

Exact prices, margins, sales cycles and revenue targets remain hypotheses until observed.

---

# 6. Storage cleanup boundary

Last destructive cleanup lineage remains conservative:
- old R59 non-actionable after authority drift/rollback
- R59R2 required exact owner token
- R60 HOLD
- Drive writes/deletes DENY in that lane

Read freshest cleanup handoff before destructive storage mutation.

---

# 7. Current queue

1. **P0 CORE ACTIVE:** finish exact-head CI → PR metadata/review → no merge.
2. **P0 KNOWLEDGE READ-ONLY:** map Fable/AXIOM/Forge/Pandora/LifeOS/MAWorld identities to exact physical sources and current gates.
3. **P0 CASH READY:** verify current sellable surfaces for Decision Sprint + Reliability Audit + Forensics and collect real external evidence.
4. **P1 GRAPH READ-ONLY:** Pandora source census/projection contract.
5. **P1 SKILLS WAITING INPUT:** user-provided recent skill pack intake/classification.

---

# Recent GMH ledger

## GMH-0008 — Gemini intake / Claude handoff
Gemini research cluster adjudicated with boundaries; Claude received sealed independent review packet.

## GMH-0009 — Exact CausalBench gate
Added direct CausalBench execution under source/editable pytest.

## GMH-0010 — Wheel-boundary correction
CI caught source-only benchmark import in wheel-only test. Corrected boundary without shipping benchmark corpus in production wheel. New head `8753edf5...`; Ubuntu exact-head gate PASS; Windows still running at last read.

## GMH-0011 — Product census delta R2
Recovered current portfolio ontology, revenue-now lanes and anti-merge rules from Library; cross-checked visible owner GitHub surface. Persisted `PRODUCT_PORTFOLIO_CENSUS_DELTA_R2_20260822.md` in `/GLOBAL_MAIN_HANDOFF/`. No product kill/merge/deploy action taken.

---

# Resume protocol

Read CURRENT → fresh-read provider state → execute one bounded step → provider readback → update CURRENT → preserve authority ceiling.

If CURRENT conflicts with physical provider evidence: **provider evidence wins; correct CURRENT.**
