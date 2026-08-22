# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T09:08:16+07:00

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

Logical responsibility and physical service/storage topology are separate decisions.

---

# 2. P0 CORE — Causal Spine candidate TECHNICALLY GREEN

Rule: `ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`.
Missing/unproven frontier => `CAUSAL_SPINE_INCOMPLETE`.
`NO_MATERIAL_PIVOT_FOUND` requires completed bounded-search evidence.
Causal pass never grants merge/deploy/runtime/trading/capital/effect authority.

## Exact candidate
- repo `bitmaster162/continuityos`
- Issue #111
- Draft PR #115
- branch `agent/causal-spine-v1`
- base `master@021e2d521efc4df0ce390b38a919bc2f0b675460`
- head `8753edf511ec9cc195ca0369a8741279a5eda5a8`
- OPEN / DRAFT / UNMERGED / mergeable
- 25 commits / 11 changed files / +1460 / -0

Closed/regression-covered: CS-R1 cross-subject binding, CS-R2 rehashed authority/effect laundering, CS-R3 state-id evidence binding.

Exact-head CI PASS without rerun:
- P0 Unified Shadow Continuity `32544706744`
- CodeQL `32544706731`
- review-gates `32544706828`
  - Ubuntu Python 3.11 PASS
  - Windows Python 3.11 PASS

Ubuntu exact-head proof includes source CausalBench execution, clean-source `1165 passed / 12 skipped / 8 subtests`, isolated wheel `1140 passed / 21 skipped / 8 subtests`, editable `1165 passed / 12 skipped / 8 subtests`, governance corpus, portable hardening, Linux realpath/symlink and secret-scan gates.

The direct CausalBench gate caught an intermediate source-only benchmark/wheel coupling. Final head preserves CausalBench in source/editable CI while keeping benchmark corpus out of the production wheel.

PR #115 body is reconciled to exact current identity/evidence. Exact-head technical COMMENT review id `4998639258` was submitted deliberately as COMMENT, not APPROVE.

**State:** `CANDIDATE_TECHNICALLY_GREEN / DRAFT / UNMERGED / INDEPENDENT_OR_OWNER_MERGE_GATE_OUTSTANDING`.

Do not merge from this handoff.

---

# 3. Universal Artifact Identity — DESIGN READY / IMPLEMENTATION HELD

Durable Library artifact:
`/GLOBAL_MAIN_HANDOFF/UNIVERSAL_ARTIFACT_IDENTITY_INTEGRATION_MAP_R1_20260822.md`

## Recovered existing primitives

ArchiveOS current contract already owns source/raw identity concepts:
- `source_id`, `source_type`, `source_file`, `record_id`, `thread_id`
- source timestamps/timezone/author/content metadata
- derived `dedup_hash`, chronology and `claimed|evidenced|verified`
- raw/source separate from derived/extracted
- dedup never deletes raw
- output packs link back to sources

ContinuityOS Common Operational Memory already owns:
- append-only event identity
- content hash + SHA-256 chain
- immutable evidence refs
- bitemporal claims/supersession
- explicit `IdentityConflict`
- strict evidence refs `{sha256, locator, kind?, scope?}`

`evidence_common.py` already owns strict SHA-256/file/manifest verification and fixed no-effect boundaries.

## UAI decision

Do **not** create another OS/service/database.

UAI = shared **contract + adapters**:
- ArchiveOS contract layer owns physical/source identity schema.
- ContinuityOS binds event/evidence refs to UAI identities; it does not own raw custody.
- future PostgreSQL EvidenceStore is the queryable relational projection.
- Control Center consumes provider/current-state observations; it does not mint physical identity.
- Pandora/graph are derived projections only.
- domain products reference UAI and do not redefine it.

Separate:
- `artifact_id` = stable logical artifact/provider-object identity
- `artifact_version_id` = one exact provider revision/payload identity
- `sha256_raw` = exact byte identity
- `location_id` = custody locator
- `observation_id` = provider/readback observation

Raw SHA-256 is **not** the only logical ID because one provider object can have multiple revisions and identical bytes can live in multiple custody locations.

Minimum target fields:
`artifact_id, artifact_version_id, source_system, source_type, provider_object_id, provider_revision_id, source_record_id, source_file, locator, mime_type, size_bytes, sha256_raw, created_at_source, modified_at_source, observed_at, custody_role, truth_role, authority_ceiling, parent_artifact_id, derived_from, semantic_family_id`.

Compatibility path:
- ArchiveOS `SOURCE_MODEL` → UAI adapter.
- UAI → current ContinuityOS evidence ref using existing strict keys; encode version identity in `scope` until an explicit v2 contract migration.
- do not silently add keys to current `normalize_evidence_refs`.

Minimum future PostgreSQL tables:
`sources, artifacts, artifact_versions, artifact_locations, artifact_observations, artifact_relations, semantic_families`.

UAI creates no deletion authority. Dedup remains T0 EXACT / T1 DERIVED EQUIVALENT / T2 RELATED.

Implementation remains held until current core ownership/adjudication settles; no repo write started.

---

# 4. Memory / ingestion / trajectory direction

Universal ingestion target:
`DISCOVER → PROVIDER IDENTIFY → UAI LOGICAL ID → RAW ACQUIRE/HASH → UAI VERSION ID → PRESERVE RAW → PARSE → NORMALIZE → CLASSIFY → DEDUP → SEMANTIC FAMILY → AUTHORSHIP → PROVENANCE → EVENTS → CAUSAL FRONTIERS → CONTRADICTIONS → CURRENT STATE → SQL → READBACK → RETRIEVAL → GRAPH`.

Agent Trajectory Bundle remains provider-neutral/content-addressed and references UAI input/output/patch/receipt/manifest identities. OpenTelemetry/OpenInference may map into it; they do not replace it.

A2A/MCP/framework/runtime choice remains benchmark-first.

---

# 5. Gemini cluster / Claude adjudication

Four Gemini reports were treated as one correlated research cluster.

Accepted direction: Causal Spine, bitemporal EvidenceStore, raw CAS, derived retrieval, governed fleet, trajectory archive, provider readback, authority-leak/confused-deputy security, benchmark program, Agent Authority & Evidence Audit wedge.

Held for Claude: ArchiveOS topology; ContinuityOS service/storage split; HANRI vs Control Center; Return Broker; SQLite edge; TRIAXIS structure; Pandora scope; Python vs mandatory Rust; standards/framework choices; enterprise-first vs portfolio-parallel strategy.

Rejected from automatic Gemini adoption: blanket KILL/FREEZE, freeze-all-non-core, immediate product/DNS shutdowns, mandatory pricing/revenue targets, enterprise-only portfolio destruction.

Claude has the sealed packet. No Claude result accepted yet.

---

# 6. Product / commercial census — delta R2

Durable Library artifact:
`/GLOBAL_MAIN_HANDOFF/PRODUCT_PORTFOLIO_CENSUS_DELTA_R2_20260822.md`

Portfolio is neither “44 businesses” nor “one megamonolith”. Maintain Canonical Portfolio, Extended Strategic Program, Alias/Family, Parent–Child/Dependency and Commercial Priority views.

Revenue-now internal lanes:
- 7-Day Operator Decision Sprint — `SELLABLE_MANUAL_PILOT_PENDING`; working SELL_NOW, payment proof absent.
- AI-Agent Reliability Audit — `PUBLIC_OFFER_NO_PAYMENT_PROOF`; working SELL_NOW, payment/delivery proof absent.
- Blockchain Forensics/OSINT — personal investigations and commercial service remain separate with provenance/legal/case gates.

Key corrections:
- Crypto Guides → `FINISH_FIRST/CURRENTNESS_REVERIFY`, not blanket KILL.
- VisionAssist → P0 empirical proof lane; fresh GitHub activity → FINISH_FIRST.
- OKX NFT/Parasite → fresh R90 safety merge activity; no blanket KILL without product-specific audit.
- AI Skill Lab → fresh R70 commercial-parity merge; no blanket FREEZE.
- AXIOM Game/Parasite Hunter → FINISH_FIRST/EMPIRICAL_PROOF pending source mapping.
- Fable 5 Observer vs Fable5 package → `ENTITY_SPLIT_REQUIRED`.
- Amora → PARKED / FREEZE-HOLD until explicit revival.
- LifeOS × MAWorld × HANRI → strategic proof program, not one product.
- Forge/Foundry → merge lock / `ENTITY_RECAPTURE_REQUIRED`.
- Pandora → queued strategic proof, no truth authority.

Fresh owner GitHub surface exposes 15 repositories; several strategic/product lines are not separate visible repos, so their currentness must be recovered from Library/Drive/local handoffs rather than inferred from GitHub absence.

Best current strategy:
`one paid manual pilot + one P0 core frontier + bounded finish-to-market/proof lanes`.

---

# 7. Storage cleanup boundary

Last destructive cleanup lineage remains conservative: old R59 non-actionable after rollback/authority drift; R59R2 required exact owner token; R60 HOLD; Drive writes/deletes DENY in that lane.

Read freshest cleanup handoff before destructive storage mutation.

---

# 8. Current queue

1. **P0 CORE:** Causal Spine technically green; await independent/owner merge-gate; no merge.
2. **NEXT CORE READ-ONLY:** UAI design ready; inspect adapters/identity conflicts and Agent Trajectory Bundle mapping without repo writes.
3. **P0 KNOWLEDGE READ-ONLY:** exact identity/currentness mapping for Fable/AXIOM/Forge/Pandora/LifeOS/MAWorld and non-GitHub surfaces.
4. **P0 CASH:** verify real sellable surfaces/evidence for Decision Sprint + Reliability Audit + Forensics.
5. **P1 GRAPH:** Pandora source census/projection contract.
6. **P1 SKILLS:** recent user skill pack intake when supplied.

---

# Recent GMH ledger

## GMH-0010 — CausalBench wheel-boundary correction
CI caught source-only benchmark/wheel coupling; final boundary corrected without shipping benchmark corpus.

## GMH-0011 — Product census delta R2
Recovered portfolio ontology, revenue-now lanes and anti-merge rules; persisted census delta in Library.

## GMH-0012 — Causal Spine exact-head technical gate closed
Head `8753edf5...` green across all required CI. PR body reconciled; technical COMMENT review `4998639258`; PR remains draft/unmerged.

## GMH-0013 — Universal Artifact Identity integration map
Recovered ArchiveOS/ContinuityOS identity primitives and designed UAI as a shared contract+adapter layer, not a new subsystem. Persisted `UNIVERSAL_ARTIFACT_IDENTITY_INTEGRATION_MAP_R1_20260822.md` in Library. Implementation intentionally held pending current core adjudication.

---

# Resume protocol

Read CURRENT → fresh-read provider state → execute one bounded step → provider readback → update CURRENT → preserve authority ceiling.

If CURRENT conflicts with physical provider evidence: **provider evidence wins; correct CURRENT.**
