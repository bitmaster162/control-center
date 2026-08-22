# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL CURRENT-TRUTH SNAPSHOT  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T10:24:00+07:00

Historical detail is preserved in Git history. Fresh provider physical evidence overrides this file where they conflict.

## AUTHORITY

`source != build != deployment != runtime != effect != authority`

Defaults:
- `execution_authority=NONE`
- `can_trade=false`
- `capital_permission=DENY`
- no merge/deploy/runtime/destructive storage/workflow-rerun/outreach/trading/capital effect is granted by this handoff
- generic `го` is not exact destructive approval

## SYSTEM

`Robert → Control Center → {HANRI, TRIAXIS} → Knowledge Foundry → {ContinuityOS, ArchiveOS} → EvidenceStore → {SCT, Retrieval/Pandora} → domain products`

Control Center owns accepted-state/effect gates. ContinuityOS owns append-only event/replay lineage. ArchiveOS owns raw custody. PostgreSQL is target relational substrate; retrieval/vector/graph remain derived. Pandora has no truth/approval authority. BitEvo is commercial/operator umbrella, not another OS/database.

## P0 CORE — CAUSAL SPINE

Repo `bitmaster162/continuityos`, Issue #111, draft PR #115.

Rule:
`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`.

Last exact candidate:
- base `021e2d521efc4df0ce390b38a919bc2f0b675460`
- head `8753edf511ec9cc195ca0369a8741279a5eda5a8`
- OPEN / DRAFT / UNMERGED

Exact-head PASS already recorded:
- P0 Unified Shadow Continuity `32544706744`
- CodeQL `32544706731`
- review-gates `32544706828` Ubuntu+Windows
- CS-R1/R2/R3 closed
- direct CausalBench gate closed

State:
`TECHNICALLY_GREEN / INDEPENDENT_OR_OWNER_MERGE_GATE_OUTSTANDING`.

No merge authority.

## UAI — GMH-0023+

UAI v1.1 invariant:
`provider_object_identity != byte_identity != semantic_family_identity`.

Identity separates:
- logical artifact identity
- exact version identity
- provider object/revision
- raw SHA-256
- custody locator
- provider observation
- semantic family

Physical identity carries no operational authority. T0/T1/T2 never grants deletion.

Deterministic ID contract:
- `artifact_id` binds `source_system + provider_object_id`
- rename/move with stable provider object preserves logical artifact
- exact version binds artifact + identity basis + provider revision/hash
- `PROVIDER_OBSERVATION_ONLY` cannot mint exact `artifact_version_id`
- immutable provider revision with conflicting raw hashes => `IDENTITY_CONFLICT`
- `derived_from` must remain acyclic

Executable `ArtifactIdentityBench v0`:
- **23/23 PASS**
- 3 real T0 fixtures: AXIOM v35, LifeOS, MAWorld
- exact bytes do not collapse provider identity
- rename/revision/conflict/observation-only/name-collision/cycle/canonical-SHA checks PASS
- no authority/effect grant fields in UAI identity schema

Artifact pack:
`ARTIFACT_IDENTITY_BENCH_PACK_R1_20260822`.

## ATB — GMH-0024

ATB v2.1 layering:
`provider-native / ATOF → ATIF → optional OTel/OpenInference → ATB → UAI/ArchiveOS/ContinuityOS/EvidenceStore → Pandora`.

Core semantics:
- `bundle_grants = NONE`
- `observed_effects[]` records what actually happened
- observed successful effect != permission to repeat it
- `effect_replay_policy = PROHIBITED`
- no hidden/private chain-of-thought requirement
- raw provider evidence and declared normalization losses are preserved

Executable `AgentTrajectoryReplayBench v0` locally PASS:
- **31/31 checks PASS**
- 5 scenarios
- complete internal trajectory supports structural/input replay without claiming deterministic replay
- ATOF→ATIF fixture requires explicit loss declaration
- subagent parent/child delegation preserved
- successful external effect can be recorded while `bundle_grants.external_effect=false`
- effect receipt + provider readback remain separately bound
- missing raw source downgrades input replay instead of inventing completeness
- hidden/private CoT is not required
- member digest/size tamper detected
- sequence conflict detected

Pack:
`AGENT_TRAJECTORY_REPLAY_BENCH_PACK_R1_20260822`.

Repo implementation of UAI/ATB remains held pending research adjudication.

## CURRENT TRUTH / CURRENTNESS — GMH-0025

Evidence ladder:
`DISCOVERED_REFERENCE → PROVIDER_OBJECT_CONFIRMED → EXACT_BYTES_CONFIRMED → WORKSPACE_ACTIVITY_CONFIRMED → SOURCE_CUSTODY_CONFIRMED → BUILD_CONFIRMED → DEPLOYMENT_CONFIRMED → RUNTIME_CONFIRMED → EFFECT_CONFIRMED`.

No level is inferred from filename/version/date alone.

Executable `CurrentTruthBench v0` locally PASS:
- **14/14 PASS**
- real fixtures: Pandora, MAWorld, LifeOS, BitEvo, Fable, AXIOM/OKX
- source does not imply deployment
- deployment does not imply runtime
- runtime does not imply effect
- Vercel READY does not imply GitHub quality-gate PASS
- workspace activity does not imply active service
- search miss does not prove non-existence
- same/similar name does not prove identity
- fresh provider readback beats stale narrative for current-state adjudication

Pack:
`CURRENT_TRUTH_BENCH_PACK_R1_20260822`.

### Fable

Provider evidence separates at least:
1. `fable-observer` research workspace (`Q33_fable-observer`, `13_fable-observer`)
2. `FABLE-5 (claude-fable-5)` external auditor/runtime identity from memory-install audit lineage
3. `fable-mythos-agents-2026` guide/site/material family

The Fable/Mythos guide describes a target architecture for improving agents; that supports guide/material classification, not runtime identity.

State:
`FABLE_OBSERVER_RESEARCH_WORKSPACE_CONFIRMED / FABLE_MYTHOS_GUIDE_SITE_FAMILY_CONFIRMED / FABLE5_AUDITOR_RUNTIME_ROLE_SEPARATE / SOFTWARE_SOURCE_RUNTIME_RELATIONSHIPS_UNPROVEN`.

### Forge

Drive folder `1Ls5QvD_MgUKrQhS3DrAJPMR6GOMyXiR2` is `PFI_RESEARCH_CONTENT_PIPELINE_FAMILY`.

Its own index records:
`PFI signals → guide + TG post + fishka → later x402 endpoint`.

It is not automatically Money Forge / MAWorld Knowledge Foundry / AXIOM Forge components.

### AXIOM / Parasite Hunter / OKX

GitHub `bitmaster162/okx-nft-bot` is current active source, default `master`; latest observed merge on 2026-08-22:
`7bc97f7f14f5ffa130ec4c8a70fb1c2a523543fa` / PR #114 / R90 fail-closed effect-safety repairs.

Drive separately exposes:
- `parasite_hunter_axiom_*` v13/v15/v16/v17/v26/v35/v62/v67 artifact lineage
- multiple `okx-nft-parasite-hunter` folders
- `Q26_parasite-hunter-game`
- `38_parasite-hunter-game`
- Meshy-ready bundle family

This supports a broader domain/product-family adjacency, but exact source provenance between AXIOM HTML artifacts and the current GitHub repo remains unproven.

State:
`OKX_NFT_CURRENT_SOURCE_CONFIRMED / AXIOM_ARTIFACT_LINEAGE_CONFIRMED / BROADER_FAMILY_ADJACENCY_CONFIRMED / EXACT_SOURCE_PROVENANCE_UNPROVEN`.

Do not auto-merge; use `UNPROVEN_RELATION` or bounded T2 candidate until explicit build/path/hash evidence exists.

### LifeOS

Drive exposes multiple `lifeos` provider folders.

Git-style provider inventory now gives concrete source-tree evidence including:
`apps/lifeos/lifeos_core.py`
and associated LifeOS tests/files with blob IDs.

Separate repeated `15_LIFEOS_RESEARCH_ADDENDUM.md` objects remain a T0/custody family.

State upgraded to:
`SOURCE_TREE_EVIDENCED / PROVIDER_WORKSPACE_CONFIRMED / LIVE_REPO_HEAD_UNRESOLVED / BUILD_DEPLOYMENT_RUNTIME_UNPROVEN`.

### MAWorld

Drive exposes concrete folders:
- `MAWorld`
- `maworld_core`
- `_MAWORLD_STAGING`
- `maworld-pfi-autopull-daily`

`maworld-pfi-autopull-daily` is provider-visible and updated on 2026-08-22, proving current workspace/storage activity only.

Git-style provider inventory includes `libs/maworld_core/*`, including:
- `action_authority.py`
- `agent_containment.py`
- `agent_mandate.py`
- `agent_mandate_v2.py`
- `agent_registry.py`
- `agents_runner.py`
- `arena_bridge.py`
- additional modules

State upgraded to:
`SOURCE_TREE_EVIDENCED / CURRENT_WORKSPACE_ACTIVITY_CONFIRMED / LIVE_REPO_HEAD_UNRESOLVED / DEPLOYMENT_RUNTIME_UNPROVEN`.

Repeated `MAWORLD_KNOWLEDGE_FOUNDRY_ARCHITECTURE_V1.md` objects remain a separate exact/custody identity family.

### Pandora

Drive source custody confirmed in `continuity-os-graph` (`16jblEO8nnfVUm6cbFXyfyck2hJosMD7O`) with `pandora_engine.py`, `build_epoch_viz.py`, `epoch_graph_3d.html`, `pandora_compute_glsl.html`, `universe.json` and supporting source.

Current GitHub indexed search still does not resolve its repo identity. Search absence is not non-existence.

State:
`DRIVE_SOURCE_CUSTODY_CONFIRMED / DEPLOYMENT_UNPROVEN / RUNTIME_UNPROVEN`.

## PANDORA

Decision: Pandora remains a derived graph/time/causal/simulation lens over UAI + ContinuityOS + Causal Spine + ATB; never canonical truth/effect authority.

First integration boundary: OFFLINE VIEW ONLY.

Executable `PandoraProjectionBench v0`:
- **14/14 PASS**
- 17 nodes / 10 edges
- deterministic graph SHA `bfdb36ef9a7814031c16a6820018aed8751f9f0fd54ee257f8beb38122cc7dec`
- source custody does not infer deployment/runtime
- Fable/Forge collisions remain separate
- AXIOM↔OKX remains UNPROVEN
- all three T0 pairs preserve provider objects
- authority surface zero
- tamper detected

State:
`PANDORA_PROJECTION_CONTRACT_EXECUTABLE_PASS / OFFLINE_ONLY / NO_LIVE_INTEGRATION_AUTHORITY`.

Live MCP writes, Portal/Gate/Wormhole networking, Satellite HTTP, arbitrary Compute/WGSL, server inference and canonical write-back remain DENY.

## STANDARDS DIRECTION

Adapt/integrate where useful:
- W3C PROV / PROV-O
- OCI-style digest/size/media descriptors
- ATIF / ATOF adapters
- OTel GenAI / OpenInference observability projections
- OpenLineage
- CloudEvents
- purl for software-package subtype only
- DSSE
- in-toto / SLSA patterns

Benchmark/defer from MVP:
- Sigstore/Rekor public transparency integration
- SCITT transparency integration

Principle:
`standardize commodity envelopes; keep proprietary causal/authority/effect/current-state semantics`.

## RESEARCH

Sequence:
Gemini correlated cluster → Claude R1 no-web → ChatGPT live-web correction → **Claude Web Deep Research R2 outstanding** → GPT Deep Research R3 after Claude adjudication.

No Claude R2 result accepted yet.

## P0 CASH

Single lane: `Agent Authority & Evidence Audit`.

Vercel `bitevo_agent_site` production READY at Git SHA `6a9d20537da01f9e5cb1ae1a06d627f2fa0f9e00`.

Published ladder:
Free triage → `$1,500` Entry Audit first paid target → `$4,900` Primary Audit → hardening after verified findings.

State:
`LIVE_OFFER / PROSPECT_PACK_READY / NO_PAYMENT_PROOF`.

`ENTRY_AUDIT_PROSPECT_PACK_R1_20260822` remains staged only: `sent=false`; not customer evidence/certification. Outreach/payment/testing stays human-gated.

Decision Sprint = secondary HOLD. Forensics = secondary ONE_GATE_FROM_SALE.

## BITEVO CI

Production Vercel READY != GitHub quality PASS.

Confirmed design defect: GitHub CI generated `provider=github/CI_BOUND` then old workflow required the same receipt to satisfy Vercel/Cloudflare `PROVIDER_BOUND` checks.

Isolated candidate:
- repo `bitmaster162/bitevo-agent-site`
- branch `agent/provider-context-quality-gate-fix`
- head `8e230699baa19561ed3189cb53f7e769ac9d985b`
- draft PR #8
- one workflow file
- main untouched / no deploy

Normal PR run `32547206641` was automatic; no rerun. It failed before executable steps; jobs expose zero steps and logs were unavailable. State:
`PRE_EXECUTION_JOB_FAILURE / ROOT_CAUSE_UNKNOWN / CANDIDATE_UNVALIDATED_BY_CI`.

Current main `6a9d205...` also remains quarantined by `main-history-audit` due observed direct/non-PR main history. Do not weaken the governance signal.

## STORAGE

Old R59 non-actionable after rollback/authority drift; R59R2 exact owner token where applicable; R60 HOLD. No destructive Drive authority.

## QUEUE

1. Ingest + independently adjudicate Claude Web R2 when returned.
2. Causal Spine independent/owner merge gate; no merge.
3. Bind LifeOS `apps/lifeos/*` and MAWorld `libs/maworld_core/*` source-tree inventories to exact repo/commit if provider evidence exists.
4. Search build/export receipts connecting AXIOM HTML lineage to source provenance.
5. UAI/ATB/Pandora/CurrentTruth contracts are executable locally; repo implementation remains held pending research adjudication.
6. P0 CASH Authority Audit only; any send is human-gated.
7. BitEvo PR #8 remains draft/unmerged pending executable CI evidence + explicit main-history resolution.
8. Build GPT Deep Research R3 after Claude R2.

## RECENT

GMH-0020: BitEvo CI provider-context defect isolated; draft PR #8; Entry Audit prospect pack staged.  
GMH-0021: Pandora offline derived-projection contract created from confirmed Drive source custody.  
GMH-0022: PandoraProjectionBench v0 PASS 14/14; AXIOM/OKX adjacency separated.  
GMH-0023: UAI deterministic ID contract + ArtifactIdentityBench v0 PASS 23/23 with 3 real T0 fixtures.  
GMH-0024: AgentTrajectoryReplayBench v0 executable PASS 31/31 across 5 replay/effect scenarios.  
GMH-0025: CurrentTruthBench v0 PASS 14/14; LifeOS and MAWorld upgraded to source-tree/workspace-evidenced without inferring deployment/runtime.

## RESUME

Fresh provider read → one bounded action → provider readback → update CURRENT. Provider wins over stale handoff.
