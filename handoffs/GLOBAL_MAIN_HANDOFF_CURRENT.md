# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T09:05:28+07:00

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

# 1. Global responsibility map

`Robert/Human Sovereign → Control Center → {HANRI, TRIAXIS} → Knowledge Foundry → {ContinuityOS, ArchiveOS} → EvidenceStore → {SCT, Retrieval/Graph} → domain products`

Boundaries:
- Control Center = accepted intent/current-truth projection/effect gate.
- HANRI = freshness/contradiction/attention/shadow proposals; no self-approval.
- TRIAXIS = logically independent adversarial verifier.
- ContinuityOS = event/replay/continuity semantics.
- ArchiveOS = exact raw evidence/provenance custody.
- Knowledge Foundry = claims/evidence/contradictions/causal processing; no truth self-promotion.
- EvidenceStore = one canonical relational backend per runtime; PostgreSQL production target; bitemporal `valid_time` + `transaction_time`.
- pgvector/lexical/graph = derived retrieval/projection only.
- SCT = provider-independent Person/Decision Twin; `execution_authority=NONE`.
- BitEvo = commercial/operator umbrella, not infrastructure truth owner.
- Pandora = graph/epoch/time/causal visualization + optional simulation projection; no canonical authority.

Logical responsibility and physical service/storage topology remain separate decisions.

---

# 2. P0 CORE — Causal Spine candidate TECHNICALLY GREEN

Rule:
`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`

Missing/unproven frontier => `CAUSAL_SPINE_INCOMPLETE`.
`NO_MATERIAL_PIVOT_FOUND` requires completed bounded-search evidence.
A causal pass grants no source/canonical/merge/deploy/runtime/trading/capital/effect authority.

## Exact live candidate
- repo: `bitmaster162/continuityos`
- Issue #111
- Draft PR #115
- branch `agent/causal-spine-v1`
- base `master@021e2d521efc4df0ce390b38a919bc2f0b675460`
- head `8753edf511ec9cc195ca0369a8741279a5eda5a8`
- OPEN / DRAFT / UNMERGED / mergeable
- 25 commits
- 11 changed files
- 1460 additions / 0 deletions

Scope remains Causal Spine only: implementation, 3 strict schemas, CausalBench v0, causal/schema/benchmark tests, and one package-data line in `pyproject.toml`.

Closed/regression-covered:
- CS-R1 cross-subject current-state binding
- CS-R2 rehashed authority/effect laundering
- CS-R3 `state_id` provider-evidence binding

## Exact-head CI
All required synchronize-triggered workflows are PASS; no rerun requested:
- P0 Unified Shadow Continuity `32544706744`: SUCCESS
- CodeQL `32544706731`: SUCCESS
- review-gates `32544706828`: SUCCESS
  - Ubuntu Python 3.11: SUCCESS
  - Windows Python 3.11: SUCCESS

Ubuntu exact-head evidence:
- clean-source full pytest: `1165 passed, 12 skipped, 8 subtests passed`
- direct CausalBench hook collected/executed
- wheel build PASS with Causal Spine module + 3 schemas
- isolated wheel-only pytest: `1140 passed, 21 skipped, 8 subtests passed`
- editable full pytest: `1165 passed, 12 skipped, 8 subtests passed`
- governance corpus: 30/30 labeled agreement; 22/22 risky not auto-run; 8/8 adversarial dangerous not auto-run
- portable hardening 10/10 PASS
- Linux symlink/realpath PASS
- secret scan finding_count 0 outside allowlisted fixture

Windows exact-head review-gates completed the clean-source/build/wheel/editable/full-pytest/compile/governance/hardening/receipt chain SUCCESS; Linux-only symlink step correctly skipped.

## Benchmark/wheel boundary
The new direct benchmark gate caught a real intermediate defect: source CausalBench passed, but wheel-only collection originally imported source-only `bench/`. Final head fixes the boundary without shipping benchmark corpus in production wheel:
- source/editable CI runs CausalBench;
- wheel-only skips only when parent package `bench` is absent;
- any other missing-module error re-raises;
- packaged causal implementation/schemas remain wheel-tested.

## PR reconciliation / review
- stale PR #115 body has been replaced with exact head, scope, CI and boundary evidence.
- technical review COMMENT submitted on exact head: review id `4998639258`.
- review deliberately used COMMENT, not APPROVE, preserving independent review/merge separation.

**Current P0 CORE state:** `CANDIDATE_TECHNICALLY_GREEN / DRAFT / UNMERGED / INDEPENDENT_OR_OWNER_MERGE_GATE_OUTSTANDING`.

**Do not merge from this handoff.**

---

# 3. Memory / knowledge / trajectory direction

Universal Artifact Identity binds source/provider IDs, revision, locator, raw SHA-256, size/type, observed time, custody role, parent/derived relations and semantic family.

Dedup:
- T0 EXACT = same bytes/hash
- T1 DERIVED = same logical object, different representation/version/export
- T2 RELATED = distinct evidence for same event/decision/project state

Universal ingestion:
`DISCOVER → IDENTIFY → HASH RAW → PRESERVE RAW → PARSE → NORMALIZE → CLASSIFY → DEDUP → SEMANTIC FAMILY → AUTHORSHIP → PROVENANCE → EVENTS → CAUSAL FRONTIERS → CONTRADICTIONS → CURRENT STATE → SQL → READBACK → RETRIEVAL → GRAPH`.

Agent Trajectory Bundle remains provider-neutral/content-addressed. OpenTelemetry/OpenInference may map into it; they do not replace it.

A2A/MCP/framework/runtime choice remains benchmark-first.

---

# 4. Gemini cluster / Claude adjudication

Four Gemini Deep Research outputs were treated as one correlated research cluster.

Accepted direction: Causal Spine, bitemporal EvidenceStore, raw CAS, derived retrieval, governed fleet, trajectory archive, provider readback, authority-leak/confused-deputy security, benchmark program, Agent Authority & Evidence Audit wedge.

Held for Claude: ArchiveOS topology; ContinuityOS service/storage split; HANRI vs Control Center; Return Broker; SQLite edge; TRIAXIS structure; Pandora scope; Python vs mandatory Rust; standards/framework choices; enterprise-first vs portfolio-parallel strategy.

Rejected from automatic Gemini adoption: blanket product KILL/FREEZE, freeze-all-non-core, immediate product/DNS shutdowns, mandatory price/revenue targets, enterprise-only destruction of portfolio option value.

Claude received sealed review packet. No Claude output has been accepted yet.

---

# 5. Product / commercial census — delta R2

Durable Library artifact:
`/GLOBAL_MAIN_HANDOFF/PRODUCT_PORTFOLIO_CENSUS_DELTA_R2_20260822.md`

Portfolio is neither “44 businesses” nor “one megamonolith”. Maintain five views:
1. Canonical Portfolio Register
2. Extended Strategic Program Register
3. Alias/Family Register
4. Parent–Child/Dependency Graph
5. Commercial Priority Register

Rules:
- `Commercial priority != architectural importance`
- `Alias != project identity`
- `Component != product`
- `Research program != runtime`
- conceptual similarity = `UNPROVEN_RELATION` until source/interface/data-flow/runtime evidence exists

Revenue-now internal lanes:
- 7-Day Operator Decision Sprint — `SELLABLE_MANUAL_PILOT_PENDING`; working `SELL_NOW`, payment proof absent.
- AI-Agent Reliability Audit — `PUBLIC_OFFER_NO_PAYMENT_PROOF`; working `SELL_NOW`, delivery/payment proof absent.
- Blockchain Forensics/OSINT — personal investigation and customer service must remain separate; legal/provenance/case gates apply.

Key corrections:
- Crypto Guides: `PUBLIC_LIVE_EDITORIAL_AUDIT`; visible source restored to 162-guide state → `FINISH_FIRST/CURRENTNESS_REVERIFY`, not blanket KILL.
- VisionAssist: P0 empirical gate; fresh GitHub merge activity on 2026-08-22 → `FINISH_FIRST`.
- OKX NFT / Parasite line: fresh R90 safety merge activity on 2026-08-22 → no blanket KILL without product-specific audit.
- AI Skill Lab: fresh R70 commercial-parity merge on 2026-08-21 → no blanket FREEZE.
- AXIOM Game / Parasite Hunter: empirical proof gate → `FINISH_FIRST/EMPIRICAL_PROOF` pending source mapping.
- Fable 5 Observer vs Fable5 package: `ENTITY_SPLIT_REQUIRED`.
- Amora: internal `PARKED`; `$AMORA` holds with parent → `FREEZE/HOLD` until explicit revival.
- LifeOS × MAWorld × HANRI: strategic proof program, not one product; first habitat synthetic-only/no external effect.
- Forge/Foundry: merge lock; `ENTITY_RECAPTURE_REQUIRED`.
- Pandora: queued strategic proof; no truth authority.

Fresh owner GitHub surface exposes 15 repositories. Fable/AXIOM/Amora/LifeOS/MAWorld/Pandora are not separate visible owner repos there, so currentness must be recovered from Library/Drive/local handoffs rather than inferred from GitHub absence.

Best current portfolio strategy:
`one paid manual pilot + one P0 core infrastructure frontier + bounded finish-to-market/proof lanes`.

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

1. **P0 CORE:** candidate is technically green; await independent/owner merge-gate adjudication. No merge.
2. **P0 KNOWLEDGE READ-ONLY:** continue exact identity/currentness mapping for Fable/AXIOM/Forge/Pandora/LifeOS/MAWorld and other non-GitHub surfaces.
3. **P0 CASH:** verify actual sellable surfaces/evidence for Decision Sprint + Reliability Audit + Forensics.
4. **NEXT CORE DESIGN, READ-ONLY UNTIL WRITE SLOT CLEARS:** Universal Artifact Identity + Agent Trajectory Bundle integration map.
5. **P1 GRAPH:** Pandora source census/projection contract.
6. **P1 SKILLS:** user recent skill pack intake when supplied.

---

# Recent GMH ledger

## GMH-0008 — Gemini intake / Claude handoff
Gemini cluster adjudicated with boundaries; Claude received sealed independent review packet.

## GMH-0009 — Exact CausalBench gate
Direct benchmark execution added to source/editable CI.

## GMH-0010 — Wheel-boundary correction
CI caught source-only benchmark/wheel coupling. Boundary corrected without shipping benchmark corpus.

## GMH-0011 — Product census delta R2
Recovered portfolio ontology, revenue-now lanes and anti-merge rules; persisted census delta in Library.

## GMH-0012 — Causal Spine exact-head technical gate closed
Head `8753edf5...` is green on P0 Unified Shadow Continuity, CodeQL and review-gates Ubuntu/Windows. PR body reconciled to exact evidence. Technical COMMENT review `4998639258` submitted, not APPROVE. PR remains draft/unmerged and requires independent/owner merge-gate authority.

---

# Resume protocol

Read CURRENT → fresh-read provider state → execute one bounded step → provider readback → update CURRENT → preserve authority ceiling.

If CURRENT conflicts with physical provider evidence: **provider evidence wins; correct CURRENT.**
