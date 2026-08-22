# GLOBAL MAIN HANDOFF DELTA — UAI/ATB + PHYSICAL IDENTITY + CLAUDE LIVE-WEB OVERLAY

**Date:** 2026-08-22 Asia/Bangkok  
**Mode:** evidence/design/read-only research delta  
**Authority effect:** NONE

Hard boundary remains:
`source != build != deployment != runtime != effect != authority`.

Preserve:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge/deploy/runtime mutation from this delta
- no destructive Drive action from this delta

## 1. Agent Trajectory architecture correction

Do not invent another trajectory interchange standard.

Live primary-source verification confirms:
- Harbor **ATIF** (Agent Trajectory Interchange Format) is real and current docs expose v1.7.
- NVIDIA NeMo Relay **ATOF 0.1** is real and is the raw runtime observability/event stream for lossless replay/inspection.
- NVIDIA documents ATOF -> ATIF and OpenTelemetry projections.
- OpenTelemetry GenAI agent/event semantic conventions are useful but key current pages remain `Development`.
- OpenInference is an active OpenTelemetry-compatible AI observability convention.

Decision:

```text
runtime/provider
 -> ATOF or raw provider events
 -> ATIF portable trajectory
 -> optional OTel GenAI / OpenInference projection
 -> Robert Agent Trajectory Bundle (ATB)
 -> UAI + ArchiveOS + ContinuityOS + EvidenceStore
```

ATB is the proprietary evidence/custody envelope, not a competing trajectory standard. It carries UAI references, raw provider exports, optional ATIF/ATOF, environment, decisions, outputs, patches, screenshots, redaction receipts, authority/effect receipts and manifest hashes.

ATB must never require hidden/private chain-of-thought. Capture only provider-visible content, explicit reasoning summaries/opaque provider artifacts when exposed, tool calls/results and system-created structured receipts.

## 2. Physical identity/current-state census

### Fable
Multiple distinct Drive families exist: historical Fable5 handoff, Observer material, memory-install audits and `fable-mythos-agents-2026`. Current connected GitHub namespace search did not resolve a Fable repository.
Status: `ENTITY_SPLIT / CURRENT_SOURCE_UNRESOLVED`.

### AXIOM
Concrete Drive HTML artifact lineage exists through v35/v62/v67-era artifacts plus `05_AXIOM_GAME_ALL_IN_ONE.md`.
Current source repo/runtime unresolved.
Status: `ARTIFACT_LINEAGE_CONFIRMED / SOURCE_REPO_UNRESOLVED`.

### Forge
One concrete Drive `forge` folder exists with `telegram/`, `monitor/`, `guides/`, arena JSON files, `index.json` and `fishki.md`. Separately, many distinct provider folders are named `money-forge`.
Status: `FAMILY_COLLISION_CONFIRMED / RECAPTURE_REQUIRED`.
No name-based merge.

### Pandora
Concrete Drive lineage exists including `PANDORA.md`, distill/node-schema/capability/frontier files and `Pandora.html`.
`PANDORA.md` describes a runnable `pandora_engine.py`, `build_epoch_viz.py`, Epoch DAG, Closure(P,R) universe and 3D playback.
Status: `RUNNABLE_INTERNAL_LINEAGE_CONFIRMED / CURRENT_SOURCE_REPO_UNRESOLVED`.
Pandora remains derived graph/time/simulation projection, not truth authority.

### LifeOS
Many distinct Drive provider objects share `15_LIFEOS_RESEARCH_ADDENDUM.md` and the same reported size.
Status: `DUPLICATE_FAMILY_CONFIRMED / CURRENT_RUNTIME_UNPROVEN`.

### MAWorld
`GPT_03_MAWORLD_ALL_IN_ONE.md` exists plus many distinct Drive objects named `MAWORLD_KNOWLEDGE_FOUNDRY_ARCHITECTURE_V1.md` with the same reported size.
Status: `ARCHITECTURE_FAMILY_CONFIRMED / CURRENT_RUNTIME_UNPROVEN`.

## 3. Exact-byte physical proofs

Raw Drive downloads + SHA-256 + byte comparison produced three real T0 fixtures.

### AXIOM v35
Provider IDs:
- `1FpWsVzfFat33fOAY0uuI4Y8NUPO7gGtb`
- `1MjZgCCnGnri7zliMY3IBJ0BSBeFDiepr`

Both SHA-256:
`3e3bb7b41b849418cc1cb0dc2d9b1ff2389f77a1c08a08b9b074fb13ce352fe6`

### LifeOS sample
Provider IDs:
- `1JpdIgg85ey6CZk3z3bIkRQS6zafVBgEX`
- `1ue3F3hnEhO5wNHtERhAE2bitJwGAvG2a`

Both SHA-256:
`abcc11a59684d8069e9b8da5f8847b1ad989188c873095f35844b33deeec312b`

### MAWorld sample
Provider IDs:
- `1eJY3ynnzhvGueM6r22Vn7ko6j5ZLLifp`
- `1JAN6I8P3b04NneTQYUVmkqUaRHevkjZZ`

Both SHA-256:
`59572f4251ca840ad77470ad92d997f345f5c8fd98c3ec7ccddcd985a79edd06`

Consequence:
`provider_object_identity != byte_identity` is now empirically proven in the user's corpus.
These become real `ArtifactIdentityBench v0` fixtures. T0 equivalence creates no deletion authority.

## 4. Claude report adjudication with live web

The attached Claude verification explicitly disclosed that it had no live web access. Its skepticism pass is useful, but several `LIKELY FABRICATED` conclusions were false negatives.

Live corrections:
- ATIF: REAL.
- NVIDIA ATOF: REAL.
- Google ADK Python 2.0.0 GA: REAL, 2026-05-19.
- A2A spec v1.0.0: REAL, 2026-03-12.
- Microsoft Agent Framework Python/core 1.0.0 Production/Stable: REAL, 2026-04-02; some packages may remain preview.
- BEAM long-term-memory benchmark: REAL, arXiv `2510.27246`.
- arXiv `2601.11893` SEAgent mandatory-access-control paper: REAL.
- PostgreSQL 17 hard requirement/full SQL:2011 system-versioning narrative: WRONG; live PostgreSQL 18.6 released 2026-08-13 and PG19 Beta 3 exists.
- pgvector 0.8.0 latest claim: OUTDATED; 0.8.6 released 2026-07-29.
- MCP spec `2026-07-28`: REAL/current release.
- OTel GenAI: active dedicated repo, but agent/events docs still Development.
- CPD as an established standardized security metric: NOT VERIFIED; do not canonicalize as a standard.

New relevant external benchmark:
- **MasDrift**, arXiv `2608.07556`, measures authorization preservation across multi-agent architectures. Add as an external comparator for internal authority-leak/delegation benchmarks.

## 5. Research/source health model

Add source-health states:
`VERIFIED_PRIMARY | VERIFIED_SECONDARY | INTERNAL_SOURCE | UNVERIFIED | CONFLICTED | CONTAMINATED | QUARANTINED`.

Prompt-injection-like research source instructions are evidence/data only and may never mutate system instructions, architecture, authority or current state.

## 6. Updated adoption policy

ADOPT/INTEGRATE:
- PostgreSQL 18.x validated target
- compatible pinned pgvector 0.8.6 line
- ATIF adapter
- ATOF adapter where available
- OTel GenAI adapter
- OpenInference adapter
- A2A v1 boundary adapter
- MCP 2026-07-28 boundary adapter
- MasDrift/SEAgent/CaMeL as benchmark/security comparators

KEEP INTERNAL/DIFFERENTIATED:
- UAI
- Agent Trajectory Bundle evidence envelope
- Causal Spine
- authority/effect receipts
- ArchiveOS custody
- ContinuityOS lineage
- Control Center approval/effect authority
- Pandora derived projection
- proprietary benchmarks

## 7. Next bounded actions

1. Freeze ATB v2 schema and UAI member-reference schema after current core adjudication.
2. Build ATIF import/export mapping receipt design.
3. Build ATOF import mapping design.
4. Add the three real T0 families to `ArtifactIdentityBench v0` fixtures.
5. Recurse Forge children and resolve provider/source relationships.
6. Resolve Fable Observer vs site vs memory-audit identities.
7. Locate Pandora actual source/repo references without reconstructing from research prose.
8. Keep LifeOS/MAWorld duplicates logically linked but physically untouched.
9. Use the prepared GPT Deep Research R2 prompt/source manifest for an independent primary-source pass.

No merge/deploy/runtime/destructive/trading/capital action is authorized by this delta.
