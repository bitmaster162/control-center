# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL CURRENT-TRUTH SNAPSHOT  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T09:50:15+07:00

This compact CURRENT supersedes verbose presentation, not history. Full prior detail remains in Git history, especially commit `d939b078b84864e6531096b4d409e394be0d0a16`, and in the resealed working snapshot.

## HARD BOUNDARY

`source != build != deployment != runtime != effect != authority`

Defaults:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge/deploy/runtime mutation solely from this handoff
- no workflow rerun solely from this handoff
- no destructive Drive action solely from this handoff
- generic `го` != exact destructive approval

## SYSTEM MAP

`Robert → Control Center → {HANRI, TRIAXIS} → Knowledge Foundry → {ContinuityOS, ArchiveOS} → EvidenceStore → {SCT, Retrieval/Pandora} → domain products`

Control Center owns accepted intent/effect gating. HANRI is freshness/conflict/shadow. TRIAXIS is independent adversarial verification. ContinuityOS owns event/replay lineage. ArchiveOS owns raw custody. EvidenceStore target is one canonical PostgreSQL relational backend per runtime. Retrieval/vector/graph are derived. Pandora has no truth/approval authority. BitEvo is the commercial umbrella, not a second OS/database.

## P0 CORE — CAUSAL SPINE

Repo `bitmaster162/continuityos`, Issue #111, draft PR #115.

Rule:
`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`

Exact candidate:
- base `master@021e2d521efc4df0ce390b38a919bc2f0b675460`
- head `8753edf511ec9cc195ca0369a8741279a5eda5a8`
- 25 commits / 11 files
- OPEN / DRAFT / UNMERGED

Exact-head CI PASS:
- P0 Unified Shadow Continuity `32544706744`
- CodeQL `32544706731`
- review-gates `32544706828` on Ubuntu + Windows

CS-R1/R2/R3 and direct CausalBench gate closed. State:
`TECHNICALLY_GREEN / INDEPENDENT_OR_OWNER_MERGE_GATE_OUTSTANDING`.
No merge.

## UAI v1.1

Universal Artifact Identity is a contract + adapters, not another service.

Core invariant:
`provider_object_identity != byte_identity != semantic_family_identity`

Identity fields separate logical artifact, exact version, provider object/revision, raw SHA, custody locator, observations and semantic family. Physical identity carries no operational authority.

`identity_basis`:
- PROVIDER_REVISION_AND_HASH
- PROVIDER_REVISION
- RAW_HASH
- PROVIDER_OBSERVATION_ONLY

Observation-only state cannot mint exact version identity. T0/T1/T2 dedup never grants deletion.

## ATB v2.1

`provider-native/ATOF → ATIF → optional OTel/OpenInference → Robert ATB → UAI/ArchiveOS/ContinuityOS/EvidenceStore → Pandora`

ATB is an evidence/custody envelope, not a competing interchange standard.

Critical invariant:
`observed effect != authority grant`.

- `bundle_grants` always NONE/FALSE
- `observed_effects[]` can truthfully record what happened
- effect replay is PROHIBITED
- no hidden/private CoT requirement

Local schemas validated Draft 2020-12. Benchmark specs exist for ArtifactIdentityBench v0 and AgentTrajectoryReplayBench v0.

## STANDARDS DIRECTION

ADAPT/INTEGRATE:
W3C PROV, OCI-style digest/size/media descriptors, ATIF, ATOF, OTel GenAI, OpenInference, OpenLineage, CloudEvents, purl/ECMA-427 for package subtype, DSSE, in-toto/SLSA patterns.

BENCHMARK/DEFER:
Sigstore/Rekor and SCITT transparency layers.

Principle:
`standardize commodity envelopes; keep proprietary causal/authority/effect/current-state semantics`.

## PHYSICAL IDENTITY CURRENTNESS

Currentness ladder:
`DISCOVERED_REFERENCE → PROVIDER_OBJECT_CONFIRMED → EXACT_BYTES_CONFIRMED → SOURCE_CUSTODY_CONFIRMED → BUILD_CONFIRMED → DEPLOYMENT_CONFIRMED → RUNTIME_CONFIRMED → EFFECT_CONFIRMED`.

Exact T0 real fixtures:
- AXIOM v35 SHA `3e3bb7b41b849418cc1cb0dc2d9b1ff2389f77a1c08a08b9b074fb13ce352fe6`
- LifeOS SHA `abcc11a59684d8069e9b8da5f8847b1ad989188c873095f35844b33deeec312b`
- MAWorld SHA `59572f4251ca840ad77470ad92d997f345f5c8fd98c3ec7ccddcd985a79edd06`

Provider identities remain distinct; no deletion authority.

Fable is split: `fable-observer` research project != `FABLE-5 (claude-fable-5)` auditor/runtime != `fable-mythos-agents-2026` site family. Relation remains UNPROVEN.

Concrete Drive `forge` folder `1Ls5QvD_MgUKrQhS3DrAJPMR6GOMyXiR2` is a `PFI_RESEARCH_CONTENT_PIPELINE_FAMILY`, not automatically Money Forge/Knowledge Foundry/AXIOM Forge.

Pandora source custody is confirmed in Drive folder `continuity-os-graph` `16jblEO8nnfVUm6cbFXyfyck2hJosMD7O`, including `pandora_engine.py`, `build_epoch_viz.py`, `epoch_graph_3d.html`, `pandora_compute_glsl.html`, `universe.json` and related source. Last internal observation: local/not deployed. Live runtime not freshly proven.

## RESEARCH SEQUENCE

Gemini correlated cluster → Claude R1 no-web skepticism → ChatGPT live-web correction → **Claude Web Deep Research R2 now outstanding** → GPT Deep Research R3 only after Claude R2 adjudication.

Claude R2 is explicitly tasked to falsify both prior Claude and ChatGPT, primary-source verify current versions, find >=10 missed 2026 primitives, and adjudicate UAI/ATB/security/provenance/moat/commercial architecture.

## P0 CASH

Single current cash lane:
`Agent Authority & Evidence Audit`.

Vercel production `bitevo_agent_site` is READY at Git SHA `6a9d20537da01f9e5cb1ae1a06d627f2fa0f9e00`.

Current public ladder:
- Free Scope/Authority Triage
- `$1,500` Entry Audit — first paid target
- `$4,900` Primary Audit
- Hardening/Repair after verified findings

Current truth:
`LIVE_OFFER / PROSPECT_PACK_READY / NO_PAYMENT_PROOF`.

Staged `ENTRY_AUDIT_PROSPECT_PACK_R1_20260822` is `sent=false`, not a customer case/certification. External outreach/payment/testing remains a human effect gate.

Decision Sprint = secondary HOLD; current route 404; Roman draft remained NOT_SENT. Forensics = secondary ONE_GATE_FROM_SALE; current route 404 and private cases stay separate.

## BITEVO QUALITY-GATE FORENSIC

Production Vercel is READY, but GitHub Actions on main SHA `6a9d205...` is RED.

Confirmed defect: GitHub CI generated `provider=github / CI_BOUND`, then old workflow required the same build receipt to pass Vercel and Cloudflare `PROVIDER_BOUND` verifiers. This is a deterministic provider-context design defect. Do not fake provider env vars.

Isolated candidate:
- repo `bitmaster162/bitevo-agent-site`
- branch `agent/provider-context-quality-gate-fix`
- head `8e230699baa19561ed3189cb53f7e769ac9d985b`
- draft PR #8
- exactly one workflow file changed
- main untouched; no deploy

Normal PR trigger created run `32547206641`; no rerun requested. It completed FAILURE within seconds, with both jobs exposing zero executable steps and job logs unavailable/BlobNotFound.

State:
`PRE_EXECUTION_JOB_FAILURE / ROOT_CAUSE_UNKNOWN / CANDIDATE_UNVALIDATED_BY_CI`.

Current base `main@6a9d205...` is also quarantined by `main-history-audit`: it was observed as a direct push and the detector requires merged-PR lineage. Do not weaken this governance control just to get green CI.

`VERCEL_READY != REPOSITORY_QUALITY_GATE_PASS`.

## STORAGE CLEANUP BOUNDARY

Old R59 non-actionable after rollback/authority drift; R59R2 exact owner token required where applicable; R60 HOLD. Drive destructive actions are not authorized by this handoff.

## CURRENT QUEUE

1. Ingest and independently adjudicate Claude Web R2 when returned.
2. Causal Spine independent/owner merge-gate; no merge.
3. UAI v1.1 / ATB v2.1 review; implementation held until adjudication.
4. P0 CASH Authority Audit only; prospect pack ready; any send is human-gated.
5. BitEvo PR #8 remains draft/unmerged until executable CI evidence + explicit main-history resolution.
6. Continue exact identity/currentness census.
7. Pandora graph projection can now bind confirmed Drive source custody.
8. After Claude R2, generate GPT Deep Research R3 packet.

## RECENT LEDGER

GMH-0010 CausalBench wheel boundary.  
GMH-0011 product census.  
GMH-0012 Causal Spine technical green.  
GMH-0013 UAI map.  
GMH-0014 ATB + physical T0 evidence.  
GMH-0015 live-web standards correction.  
GMH-0016 Claude Web R2 packet.  
GMH-0017 UAI/ATB schemas + benchmark specs.  
GMH-0018 UAI v1.1/ATB v2.1 self-audit + Pandora/Fable/Forge resolution.  
GMH-0019 P0 CASH resolved to Authority Audit.  
GMH-0020 BitEvo CI provider-context defect isolated in draft PR #8; PR CI classified pre-execution/unknown; Entry Audit prospect pack staged/not sent.

## RESUME

Fresh provider read → one bounded action → provider readback → update CURRENT.
If handoff conflicts with provider physical evidence: **provider wins**.
