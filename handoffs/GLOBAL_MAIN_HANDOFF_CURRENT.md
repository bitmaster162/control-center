# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T09:43:53+07:00

## Canonical location
`bitmaster162/control-center` → `global/main-handoff-current` → `handoffs/GLOBAL_MAIN_HANDOFF_CURRENT.md`

Provider physical evidence overrides stale handoff text.

## Hard authority boundary

`source != build != deployment != runtime != effect != authority`

Defaults:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge/deploy/runtime mutation solely from this handoff
- no workflow rerun solely from this handoff
- no destructive Drive action solely from this handoff
- generic `го` is not an exact destructive approval token

---

# 1. Responsibility map

`Robert/Human Sovereign → Control Center → {HANRI, TRIAXIS} → Knowledge Foundry → {ContinuityOS, ArchiveOS} → EvidenceStore → {SCT, Retrieval/Graph} → domain products`

- Control Center = accepted intent/current-truth projection/effect gate.
- HANRI = freshness/contradiction/attention/shadow proposals; no self-approval.
- TRIAXIS = logically independent adversarial verifier.
- ContinuityOS = event/replay/continuity lineage.
- ArchiveOS = exact raw/source custody.
- Knowledge Foundry = claims/evidence/contradictions/causal processing.
- EvidenceStore = one canonical relational backend per runtime; PostgreSQL target.
- retrieval/vector/graph = derived.
- SCT = provider-independent Person/Decision continuity; no execution authority.
- Pandora = derived graph/time/causal/simulation surface; no canonical authority.
- BitEvo = commercial/operator umbrella, not truth infrastructure.

---

# 2. P0 CORE — Causal Spine

Rule:
`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`

Missing/unproven frontier:
`CAUSAL_SPINE_INCOMPLETE`

No-pivot only with bounded evidenced search.

Repo:
`bitmaster162/continuityos`

Issue:
#111

Draft PR:
#115

Exact technical candidate at last provider gate:
- base `master@021e2d521efc4df0ce390b38a919bc2f0b675460`
- head `8753edf511ec9cc195ca0369a8741279a5eda5a8`
- 25 commits / 11 changed files / +1460 / -0
- OPEN / DRAFT / UNMERGED

Exact-head CI PASS:
- P0 Unified Shadow Continuity `32544706744`
- CodeQL `32544706731`
- review-gates `32544706828`
  - Ubuntu Python 3.11 PASS
  - Windows Python 3.11 PASS

Closed:
- CS-R1 cross-subject binding
- CS-R2 rehashed authority/effect laundering
- CS-R3 state-id evidence binding
- direct CausalBench exact-head gate
- wheel/source benchmark separation

Technical COMMENT review only; no self-APPROVE.

State:
`CANDIDATE_TECHNICALLY_GREEN / DRAFT / UNMERGED / INDEPENDENT_OR_OWNER_MERGE_GATE_OUTSTANDING`

No merge from this handoff.

---

# 3. Universal Artifact Identity — v1.1 design

UAI is a shared contract + adapters, not another OS/database/service.

Core separation:

```text
artifact_id          = logical/provider-backed artifact identity
artifact_version_id  = exact version identity when determinable
provider_object_id   = provider-native object identity
provider_revision_id = provider revision identity
sha256_raw           = exact byte identity
location/locator     = custody location
observation          = provider/current-state observation
semantic_family_id   = semantic grouping
```

Invariant:

`provider_object_identity != byte_identity != semantic_family_identity`

## Self-audit correction
Physical identity must not itself grant or encode operational authority.

UAI v1.1:
- removes `authority_ceiling` from core identity;
- retains only non-authoritative governance labels;
- adds explicit `identity_basis`:
  - `PROVIDER_REVISION_AND_HASH`
  - `PROVIDER_REVISION`
  - `RAW_HASH`
  - `PROVIDER_OBSERVATION_ONLY`
- exact `artifact_version_id` remains null for provider-observation-only state.

Preferred exact identity basis:
when immutable provider revision and raw SHA both exist, bind both.

Dedup:
- T0 EXACT
- T1 DERIVED EQUIVALENT
- T2 RELATED

No dedup relation grants deletion authority.

Relational target:
`sources, artifacts, artifact_versions, artifact_locations, artifact_observations, artifact_relations, semantic_families`.

Implementation remains held until current architecture adjudication.

---

# 4. Agent Trajectory Bundle — v2.1 design

Do not invent a competing trajectory interchange standard.

Layer:

```text
provider/runtime raw
 -> ATOF when native
 -> ATIF normalized portable trajectory
 -> optional OTel GenAI / OpenInference projection
 -> ROBERT ATB
 -> UAI + ArchiveOS + ContinuityOS + EvidenceStore
 -> Pandora projection
```

ATB = evidence/custody envelope.

## Self-audit correction: effect != authority

Old draft incorrectly forced all recorded effect booleans false.

ATB v2.1 separates:

### `bundle_grants`
Always NONE/FALSE.
The bundle itself grants no merge/deploy/runtime/external/trading/capital authority.

### `observed_effects[]`
May truthfully record:
- requested
- blocked
- attempted
- succeeded
- failed
- unknown

for:
merge/deployment/runtime/message/file/destructive-storage/trade/wallet/capital/other effects.

Observed effects bind effect receipts and provider readbacks where available.

`effect_replay_policy=PROHIBITED`.

Therefore:
`recorded successful effect != permission to repeat effect`.

Replay classes:
- STRUCTURAL
- INPUT
- SEMANTIC
- DETERMINISTIC only when proven
- effect replay prohibited

No hidden/private chain-of-thought requirement.

---

# 5. Standards adoption

Current live-web direction:

## ADAPT / integrate
- W3C PROV / PROV-O as provenance vocabulary/adapter
- OCI-style `mediaType + digest + size` physical member descriptors
- ATIF trajectory adapter
- ATOF runtime adapter where emitted
- OpenTelemetry GenAI observability adapter
- OpenInference observability adapter
- OpenLineage for ingestion/job lineage
- CloudEvents for event transport envelopes
- purl/ECMA-427 only for software-package subtype
- DSSE for typed signing envelopes
- in-toto/SLSA v1.2 attestation patterns

## BENCHMARK / defer from MVP
- Sigstore/Rekor public transparency/signature integration
- IETF SCITT transparency services / receipts

Important live external status:
- W3C PROV-O remains stable Recommendation.
- CloudEvents stable release currently v1.0.2; main is 1.0.3-wip.
- OpenLineage is event-based with START/RUNNING/COMPLETE/ABORT/FAIL/OTHER.
- ECMA-427 standardized Package-URL in Dec 2025.
- SLSA v1.2 is Approved.
- DSSE provides type-bound signing without JSON canonicalization.
- Sigstore Bundle format combines verification material and signatures/DSSE.
- SCITT is now RFC 9943, published 2026, for signed-statement transparency and receipts.

Standardization principle:
`standardize commodity envelopes; keep proprietary causal/authority/effect/current-state semantics`.

---

# 6. Physical identity/current-state census R2

## AXIOM
Concrete HTML lineage exists.

Verified T0 exact sample:
two distinct provider objects share:
`sha256 3e3bb7b41b849418cc1cb0dc2d9b1ff2389f77a1c08a08b9b074fb13ce352fe6`

State:
`ARTIFACT_LINEAGE_CONFIRMED / SOURCE_REPO_UNRESOLVED`

## LifeOS
Verified T0 exact sample:
`sha256 abcc11a59684d8069e9b8da5f8847b1ad989188c873095f35844b33deeec312b`

State:
`DUPLICATE_FAMILY_CONFIRMED / CURRENT_RUNTIME_UNPROVEN`

## MAWorld
Verified T0 exact sample:
`sha256 59572f4251ca840ad77470ad92d997f345f5c8fd98c3ec7ccddcd985a79edd06`

State:
`ARCHITECTURE_FAMILY_CONFIRMED / CURRENT_RUNTIME_UNPROVEN`

## Fable — resolved semantic split

At least three distinct identities:

1. **Fable 5 Observer research project**
   - explicit `PROJECT_ID=fable-observer`
   - dedicated folder `Q33_fable-observer`
   - Drive ID `1Emk-WDKT2gD1SdJeOFoymXr5lm8S6m2j`
   - research packet: deep-research prompt/evidence/preflight/return-ingest

2. **FABLE-5 external auditor/runtime identity**
   - memory/control-plane audit explicitly says:
     `Auditor: FABLE-5 (claude-fable-5), external runtime`
   - this is an auditor/runtime role, not proof of a software product.

3. **fable-mythos-agents-2026 site/material family**
   - folder ID `1GbbRzC0dHu0ZKsx-JJ5ZIPsBAlot2PwN`
   - contains `index.html`

GitHub org search currently has no `fable-observer` code hit.

State:
`FABLE_OBSERVER_PROJECT != FABLE5_AUDITOR_RUNTIME != FABLE_MYTHOS_SITE_FAMILY`

Relation:
`UNPROVEN_RELATION`.

## Forge — concrete folder reclassified

Concrete Drive `forge` folder:
`1Ls5QvD_MgUKrQhS3DrAJPMR6GOMyXiR2`

Its own index says:

`PFI signals → guide + TG post + fishka → (later) x402 endpoint`

Children:
- telegram generated posts
- guides generated research notes
- monitor M2M digests
- fishki candidate ideas
- arena robustness evidence

Therefore this exact provider folder is:
`PFI_RESEARCH_CONTENT_PIPELINE_FAMILY`

It is not proven identical to:
- Money Forge
- Knowledge Foundry
- AXIOM Forge modules
- commercial Forge product

Global `forge` name remains unsafe as entity key.

## Pandora — source custody now confirmed

Provider folder:
`continuity-os-graph`
Drive ID:
`16jblEO8nnfVUm6cbFXyfyck2hJosMD7O`

Direct source includes:
- `pandora_engine.py` — `14e-soWtTXb4mEjoksWK_qL6V3qoNuuC8`
- `build_epoch_viz.py` — `1ScZ7puLFJnlho4mQ0aJTAulFdewJbs1Q`
- `epoch_graph_3d.html` — `1s-FcYSbXEu1K-_ZC1NzkVux7zs0frrhR`
- `pandora_compute_glsl.html` — `1keZASBI542_bTHhciMIbG8-X9dAa8PEB`
- `universe.json`
- `arena_to_epochs.py`
- `_SERVE_GRAPH.bat`
- graph datasets/build scripts

Last internal ecosystem observation says this line was local and **not deployed**.

State:
`CURRENT_SOURCE_CUSTODY_CONFIRMED / LAST_INTERNAL_DEPLOYMENT_OBSERVATION=NOT_DEPLOYED / LIVE_RUNTIME_NOT_FRESHLY_PROVEN`

---

# 7. Currentness ladder

Use separate evidence states:

```text
DISCOVERED_REFERENCE
PROVIDER_OBJECT_CONFIRMED
EXACT_BYTES_CONFIRMED
SOURCE_CUSTODY_CONFIRMED
BUILD_CONFIRMED
DEPLOYMENT_CONFIRMED
RUNTIME_CONFIRMED
EFFECT_CONFIRMED
```

Never jump levels by inference.

---

# 8. Benchmark program

External:
- LoCoMo
- LongMemEval
- BEAM
- CaMeL / AgentDojo class
- MasDrift
- SEAgent-related security research
- others only after primary-source verification

Internal:
- CausalBench
- CurrentTruthBench
- AuthorityLeakBench
- ContradictionBench
- EffectBench
- ColdStartBench
- CrossModelHandoffBench
- AgentTrajectoryReplayBench
- DecisionCalibrationBench
- ArtifactIdentityBench

## New local benchmark-ready contracts

`ArtifactIdentityBench v0` mandatory invariants include:
- same bytes across provider objects => T0 but preserve provider identities
- same filename never sufficient
- provider immutable revision/hash conflict => IDENTITY_CONFLICT
- exact version incomplete without revision/hash
- T0/T1/T2 never grants deletion
- rename/move does not automatically create new logical artifact
- derived/vector/graph similarity never becomes physical identity

Real fixtures:
AXIOM v35, LifeOS, MAWorld plus semantic collision fixtures for Fable/Forge and source-vs-runtime fixture for Pandora.

`AgentTrajectoryReplayBench v0` tests:
- structural/input/semantic replay
- ATIF/ATOF mapping loss
- subagent tree
- UAI member resolution
- redaction provenance
- authority forgery rejection
- effect replay prohibition
- hidden CoT absence tolerance
- digest/size mismatch rejection

---

# 9. Product / commercial state

Portfolio is modeled with:
- Canonical Portfolio Register
- Extended Strategic Program Register
- Alias/Family Register
- Parent–Child/Dependency Graph
- Commercial Priority Register

Current operating strategy:
`one paid manual pilot + one P0 core frontier + bounded finish-to-market/proof lanes`

## P0 CASH — resolved current truth

The single current P0 CASH lane is:

`Agent Authority & Evidence Audit`

Fresh Vercel provider state:
- project: `bitevo_agent_site`
- project ID: `prj_U2iHyiwhJlO33r0u4uN65PpdzEiv`
- production deployment: `dpl_7coXfJt5BHYubLMejnpnt5q9rJH9`
- state: `READY`
- source: `bitmaster162/bitevo-agent-site`
- production Git SHA: `6a9d20537da01f9e5cb1ae1a06d627f2fa0f9e00`

Fresh production HTTP readback:
- `/intake` = 200
- `/agent-authority-audit` = 200
- `/pricing` = 200
- `/consulting` = 200

Current public commercial ladder:
1. Free Scope / Authority Triage — 20 min.
2. `$1,500` fixed Entry Audit — 1 critical action chain + 1 primary failure hypothesis + bounded reproduction + concise finding memo.
3. `$4,900` fixed Agent Authority & Evidence Audit — 5 working days after complete evidence/access + written scope; 1 staging/test workflow; up to 3 integrations; 10–20 agreed failure scenarios; one retest.
4. Hardening & Repair — separately quoted only after verified findings.

Recommended first paid target:
`$1,500 Entry Audit`.

Current commercial truth:
`LIVE_OFFER_AND_PRODUCTION_SURFACE / NO_PAYMENT_PROOF`

Public intake is intentionally local/browser-only and does not transmit, book, accept payment or authorize testing. Scheduling/payment/Rules of Engagement require an external agreed business channel.

### Current commercial False Green

Vercel production is READY on `main@6a9d205...`, but GitHub Actions run `32545562743` for the exact same SHA is `completed/failure`.

Jobs:
- `quality-gate`: FAILURE
- `main-history-audit`: FAILURE

The workflow definition proves `main-history-audit` is a detective control that fails when main history has no associated PR merged to main; this exact run was triggered by a push to main.

The standalone `quality-gate` root cause remains UNKNOWN because job logs are unavailable through the current connector. Do not infer its failure reason.

Therefore:
`VERCEL_READY != REPOSITORY_QUALITY_GATE_PASS`.

No rerun requested.

### Secondary commercial lanes

7-Day Operator Decision Sprint:
- internal truth `PRODUCT_DEFINED_NO_PAYMENT_PROOF`
- Roman outreach artifact remains `DRAFT_LOCKED / NOT_SENT`
- current production route `/operator-decision-sprint` = 404
- classification: `HOLD_AS_SECONDARY_COMMERCIAL_EXPERIMENT`

Blockchain Forensics / OSINT:
- real research/service dossier
- `NOT_A_SINGLE_SOFTWARE_PRODUCT`
- `READY_ONLY_AFTER_CASE_SCOPING_AND_REDACTION`
- current production route `/forensics` = 404
- classification: `ONE_GATE_FROM_SALE / SECONDARY`

No blanket Gemini KILL/FREEZE decisions accepted.

Exact P0 CASH evidence gate:
`reviewed prospect -> explicit/user-sent outreach -> response -> bounded scope -> payment/commitment -> Entry Audit delivery -> buyer acceptance/usefulness`.

Do not count page views, research reports, internal dogfood, free calls, drafts or deployment as paid-market proof.

---

# 10. Research sequence

A. Gemini correlated cluster  
B. Claude R1 no-web skepticism  
C. ChatGPT live-web correction  
D. Claude Web Deep Research R2 — packet dispatched/prepared  
E. GPT Deep Research — held until Claude R2 returns

Claude Web R2 must:
- falsify ChatGPT's external corrections
- primary-source verify current versions
- frontier-scan missed 2026 primitives
- adjudicate UAI/ATB
- audit provenance/signing/transparency/policy standards
- test moat and commercial claims
- return exact ACCEPT/MODIFY/REJECT delta

No Claude R2 result accepted yet.

---

# 11. Storage cleanup boundary

Destructive cleanup remains separately gated:
- old R59 non-actionable after rollback/authority drift
- R59R2 exact owner token required where applicable
- R60 HOLD
- generic `го` is not destructive approval
- Drive deletion/write authority not derived from this handoff

---

# 12. Current execution queue

1. P0 CORE: Causal Spine independent/owner merge-gate; no merge.
2. P0 RESEARCH: ingest Claude Web R2 when returned.
3. P0 KNOWLEDGE: continue exact identity/source/currentness resolution.
4. NEXT CORE: UAI v1.1 / ATB v2.1 contract review; repo implementation held.
5. P0 CASH: Authority Audit is the sole current cash lane; next = reconcile exact quality-gate failure read-only + prepare one evidence-safe Entry Audit prospect/sample packet; no send.
6. P1 GRAPH: Pandora projection contract now has confirmed Drive source custody.
7. AFTER CLAUDE R2: refresh GPT Deep Research R3 and dispatch.

---

# Recent GMH ledger

## GMH-0010
CausalBench wheel-boundary correction.

## GMH-0011
Product census delta R2.

## GMH-0012
Causal Spine exact-head technical gate closed; draft/unmerged.

## GMH-0013
UAI integration map created.

## GMH-0014
ATB architecture + physical identity census + T0 fixtures.

## GMH-0015
Live-web correction + W3C PROV / OCI / SLSA / OpenLineage / CloudEvents adaptation direction.

## GMH-0016
Claude Web Deep Research R2 sealed packet prepared before GPT.

## GMH-0017
UAI/ATB contract pack created and Draft 2020-12 schemas validated locally:
- `robert.uai.v1.schema.json`
- `robert.agent_trajectory_bundle.v2.schema.json`
- real identity fixtures
- ArtifactIdentityBench v0 spec
- AgentTrajectoryReplayBench v0 spec

No repository implementation.

## GMH-0018
Self-audit hardened UAI/ATB:
- UAI v1.1 removed authority semantics from identity and added explicit identity basis;
- ATB v2.1 separated no-grant bundle semantics from truthful `observed_effects[]`;
- effect replay explicitly prohibited;
- Pandora exact Drive source folder and source files confirmed;
- Fable semantic split confirmed;
- concrete `forge` folder classified as PFI research/content pipeline;
- live standards delta added: ECMA-427 purl, DSSE, Sigstore, SLSA v1.2, SCITT RFC 9943.

Authority effect:
documentation/contracts/read-only research only.
No merge, deploy, runtime mutation, destructive storage, trading or capital effect.

## GMH-0019
**Time:** 2026-08-22T09:43:53+07:00  
**Lane:** P0 CASH / BITEVO COMMERCIAL CURRENT TRUTH

Fresh provider reconciliation selected one current cash lane:
`Agent Authority & Evidence Audit`.

Verified:
- Vercel production project/deployment is READY on `main@6a9d205...`;
- live `/agent-authority-audit`, `/pricing`, `/consulting`, `/intake` surfaces;
- Free / $1,500 Entry / $4,900 Primary commercial ladder;
- bounded deliverables and explicit claim ceilings;
- public intake does not transmit/book/pay/authorize testing.

Commercial decision:
- first paid target = `$1,500 Entry Audit`;
- `$4,900 Primary Audit` remains the full engagement;
- Decision Sprint = secondary HOLD;
- Forensics = secondary ONE_GATE_FROM_SALE.

Payment/customer evidence remains unproven.

False Green recorded:
GitHub Actions run `32545562743` for the exact production SHA is FAILURE while Vercel is READY.
`main-history-audit` failure is consistent with its explicit direct/non-PR main-history detective control.
Standalone `quality-gate` root cause remains UNKNOWN pending read-only evidence; no rerun.

Authority effect:
read-only provider reconciliation + documentation only.
No outreach/send/payment/deploy/merge/runtime/destructive effect.

---

# Resume protocol

Read CURRENT → fresh provider read → one bounded step → readback → update CURRENT.

If CURRENT conflicts with provider evidence:
**provider evidence wins; correct CURRENT.**
