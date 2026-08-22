# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T08:42:27+07:00

## Canonical location

GitHub:
- repo: `bitmaster162/control-center`
- branch: `global/main-handoff-current`
- path: `handoffs/GLOBAL_MAIN_HANDOFF_CURRENT.md`

This file is the live cross-project working source. It is updated after every material step.

## Authority boundary

`source != build != deployment != runtime != effect != authority`

This handoff records current truth, accepted owner decisions, evidence and next actions. It does **not** itself grant merge, deploy, runtime, destructive storage, trading or capital authority.

Global defaults unless a fresher exact project gate overrides them:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge solely from this handoff
- no deploy solely from this handoff
- no workflow rerun solely from this handoff
- no destructive Drive action solely from this handoff

## Maintenance rule

After every material step record:
1. step id;
2. time;
3. lane/project;
4. before;
5. action actually performed;
6. evidence/provider readback;
7. after;
8. authority effect;
9. blockers;
10. exact next action.

Provider physical evidence wins over stale text in this handoff.

---

# Accepted global architecture

```text
ROBERT / HUMAN SOVEREIGN
        |
        v
CONTROL CENTER
intent / accepted truth / approvals / effect authority
        |
   +----+----------------------+
   |                           |
   v                           v
 HANRI                       TRIAXIS
 freshness/conflict          independent adversarial verification
   |                           |
   +------------+--------------+
                v
         KNOWLEDGE FOUNDRY
 claims / evidence / contradictions / causal spines
                |
        +-------+-------+
        |               |
        v               v
 CONTINUITYOS         ARCHIVEOS
 events/replay        raw evidence custody
        |               |
        +-------+-------+
                v
          EVIDENCE STORE
                |
        +-------+--------+
        |                |
        v                v
 SOVEREIGN TWIN       RETRIEVAL
 Person/Decision      lexical/vector/graph
        |
        v
 DOMAIN CELLS
 TradingOS / NFT / VisionAssist / AI Skill Lab /
 Amora / Crypto Guides / other products
```

BitEvo is the commercial/operator **umbrella layer**:
customer-facing parent brand, offer packaging, routing, onboarding and cross-product commercial surface.
It must not become a second canonical DB, Control Center, ArchiveOS or ContinuityOS.

---

# P0 — Causal Spine

Human-accepted rule:

`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`

Missing or unproven frontier:

`CAUSAL_SPINE_INCOMPLETE`

Allowed no-pivot state:
`NO_MATERIAL_PIVOT_FOUND`
only with bounded evidenced search completion.

Required states:
- COMPLETE
- INCOMPLETE_ORIGIN
- INCOMPLETE_PIVOT
- INCOMPLETE_CURRENT_STATE
- SEARCH_INCOMPLETE
- CONTRADICTED
- SUPERSEDED

Passing the causal gate grants no merge/deploy/runtime/trading/capital/effect authority.

## Current GitHub lane

Repo: `bitmaster162/continuityos`

Issue:
- #111 `P0: Implement Causal Spine Gate + CausalBench v0`

Protected master baseline at lane creation:
- HEAD `021e2d521efc4df0ce390b38a919bc2f0b675460`
- tree `803d89c3e81ea3a83147cd63879a32f8a88c9afe`

Candidate:
- branch `agent/causal-spine-v1`
- draft PR #115
- base `master@021e2d521efc4df0ce390b38a919bc2f0b675460`
- **fresh actual head:** `4ab6c77f714770f2c278dbe9f51cf6f38b9fe474`
- **23 commits**
- **10 changed files**
- **1434 additions / 0 deletions**
- unmerged
- no deployment/runtime effect

Historical review defects CS-R1/CS-R2/CS-R3 are described in the PR body as closed at an earlier candidate head, but the actual provider head has advanced again. The PR body is stale relative to current provider state.

Exact next action:
reconcile exact current head `4ab6c77...`, changed files, exact-head CI and independent review evidence before any merge-gate conclusion. No merge.

---

# Memory / Knowledge architecture

## Universal Artifact Identity

Every physical item gets:
- artifact_id
- source_system
- provider_object_id
- provider_revision_id
- path/locator
- mime type
- size
- raw SHA-256
- normalized SHA-256 when appropriate
- source created/modified times
- observed_at
- custody role
- parent/derived relations
- semantic family id

Dedup:
- T0 EXACT = same bytes/hash
- T1 DERIVED = same logical object, different representation/version/export
- T2 RELATED = distinct evidence for same event/decision/project state

Rule: collapse meaning first; physical deletion only after separate custody/recovery proof and exact approval.

## Universal ingestion

```text
DISCOVER
-> IDENTIFY
-> HASH RAW
-> PRESERVE RAW
-> PARSE
-> NORMALIZE
-> CLASSIFY
-> EXACT DEDUP
-> SEMANTIC FAMILY
-> AUTHORSHIP
-> PROVENANCE
-> EVENT EXTRACTION
-> CAUSAL FRONTIER EXTRACTION
-> CONTRADICTION DETECTION
-> CURRENT-STATE OBSERVATION
-> TRANSACTIONAL SQL WRITE
-> READBACK VERIFY
-> RETRIEVAL INDEX
-> GRAPH PROJECTION
```

Planned sources:
ChatGPT Library, Drive, GitHub, local Windows, servers, deployment providers, Gemini, Claude, Codex, Manus, Antigravity, supplied Telegram exports, ZIP/MD/JSON/HTML/PDF/DOCX/XLSX/logs/DBs.

## Agent Trajectory Bundle

```text
AGENT_TRAJECTORY_BUNDLE/
  RUN_MANIFEST.json
  INPUT_REFERENCES.json
  ENVIRONMENT.json
  TOOL_EVENTS.jsonl
  MODEL_EVENTS.jsonl
  DECISIONS.jsonl
  OUTPUTS/
  PATCHES/
  SCREENSHOTS/
  RECEIPTS/
  FINAL_RESPONSE.md
  REDACTION_REPORT.json
  MANIFEST.sha256
```

ArchiveOS/raw objects = custody.  
ContinuityOS = replay/event lineage.  
PostgreSQL = queryable relations.  
Control Center = accepted state/authority projection.

## Knowledge substrate

Target:
- PostgreSQL canonical relational substrate
- pgvector derived vector retrieval
- PostgreSQL FTS/trigram initially
- SQLite edge/local mode
- ArchiveOS content-addressed raw object custody
- graph as derived projection, not separate truth authority

Core families:
sources/artifacts/versions/locations/segments; entities/events; causal spines/frontiers; claims/evidence/counterevidence/contradictions; decisions/outcomes; project states/current observations; agent runs/events/outputs; skills; effects/receipts; commercial events; embeddings/retrieval.

Temporal rule:
- valid_time
- transaction_time

---

# Pandora / Graph program

Pandora is a real existing line, not a new name.

Verified Drive evidence includes:
- `PANDORA.md`
- `pandora_engine.py`
- append-only Epoch DAG
- branch/epoch visualization
- 3D force-directed graph playback
- Closure(P,R) operational ontology
- Pandora Spatial Runtime research
- ContinuityOS↔Pandora integration research

Target graph layers:
- G0 provenance graph
- G1 event/supersession graph
- G2 claim/evidence graph
- G3 causal-spine graph
- G4 decision/outcome graph
- G5 agent-trajectory graph
- G6 project/product/dependency graph
- G7 Person/Decision Twin graph

Pandora becomes visualization/time playback/causal browser/graph-diff/simulation surface.
It does not own canonical truth or approvals.

---

# External adoption policy

Use the best legally compatible public/open-source components and patterns; do not copy proprietary closed implementations or violate licenses.

Evaluate/adapt:
- Graphiti / Zep
- Mem0
- Letta
- OpenAI Agents SDK
- Microsoft Agent Framework
- Google ADK
- other current best-fit graph/memory/orchestration components

Do not rebuild commodity infrastructure where an integration is superior.

Potential moat:
```text
unique multi-year evidence corpus
+ cross-model/cross-provider trajectories
+ causal correction history
+ authority/effect separation
+ measured calibration
+ proprietary failure/contradiction benchmarks
+ customer cases
+ integrations/data gravity
+ switching costs
```

This is `POTENTIAL_MOAT` until measured.

---

# Governed Fleet

```text
WORK ORDER
-> FROZEN INPUT
-> SPECIALIST
-> INDEPENDENT VERIFIER
-> DETERMINISTIC CHECKS
-> ADVERSARIAL REVIEW
-> HUMAN/EFFECT GATE
-> RECEIPT
```

Agent roles:
census, parser, provenance, causal miner, contradiction hunter, currentness verifier,
researcher, builder, browser QA, Angel, Devil, Steelman, Premortem, Security,
TRIAXIS, Commercial, Benchmark/QA, Arbiter.

Deterministic functions:
hashing, exact dedup, schema checks, provenance FK checks, baseline checks,
effect admission, capital/risk limits, final causal completeness, provider identity comparison.

Portfolio WIP:
- P0 CASH = max 1 main offer
- P0 CORE = max 1 infrastructure frontier
- P1 PRODUCT = max 2 finish-to-market lanes
- P2 RESEARCH = parallel/bounded/read-only

---

# Decision Intelligence / Skills

Existing ContinuityOS capability:
`cos advocate` checks contradiction, staleness, evidence, canon, overconfidence,
honesty, reversibility, alternatives, assumptions, blast radius.

Requested aliases:
`/DEVIL /PREMORTEM /BLINDSPOT /STEELMAN /RIPPLE /REALPC /COMPARE /PRIMER /MENTALMODEL /MYTHS /TLDR /DECISIONS`

Additional:
`/THESIS /EVIDENCE /INVALIDATE /CATALYST /SCENARIOS /POSITION /COUNTERFACTUAL /POSTMORTEM /CALIBRATE /SOURCECHECK /REGIME /NO_TRADE`

Composites:
- `/REDTEAM = DEVIL + BLINDSPOT + PREMORTEM + STEELMAN`
- `/DECIDE = PRIMER -> THESIS -> EVIDENCE -> ANGEL -> DEVIL -> STEELMAN -> BLINDSPOT -> PREMORTEM -> RIPPLE -> REALPC -> INVALIDATE -> TRIAXIS -> DECISION_CARD`

No command gets trade/capital authority.

Additional recent user-created skill pack is pending exact inspection.

---

# Benchmarks

External:
- LoCoMo
- LongMemEval
- BEAM

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

---

# Commercial portfolio

Known families include substantially more than the first shortlist.

Trading/crypto:
TradingOS, Sovereign-Core/BTC Bot, TradeCore, Inner Circle, VIP products,
Trend-Flex, Tilt/Risk, MAX+BitEvo, Delist EWS, Arb Radar, Grid OS/Grid Mirror,
Crypto Guides, OKX NFT/Parasite Killer, Binance NFT, Sovereign Arena,
Trading Decision Audit/Decision Lab.

Core AI/memory/governance:
ContinuityOS, SCT, Person Twin, Decision Twin, DTaaP, GPT-S:CORE SDK,
ArchiveOS, Archive Tooling, Knowledge Foundry, Memory Router, Return Broker,
Control Center, HANRI, TRIAXIS, Pandora, MAWorld, LifeOS, RUAP,
Causal Memory/Spine, Cross-model Continuity, Agent Authority tooling.

AI services/education:
AI Skill Lab, AI Setup, AI Studio, AI Operations,
Agent Authority & Evidence Audit, Agent Reliability Audit,
Memory/Knowledge Consolidation Audit, Fleet Architecture/Governance,
AI Client Hunter, Consulting, Docs Pack, Knowledge Portal, courses/workshops,
Callable Clones, custom agents.

Consumer/accessibility/creative:
Amora, AI Tamagotchi, privacy-first AI companion, VisionAssist,
Bitfractal Vinyl Studio, Fargus Vinyl Winamp, Axiom Game, Fable5,
Pandora visual/simulation surfaces.

Investigation/evidence:
Matrixout, evidence engine, archive-to-evidence services,
forensic timeline/contradiction mapping, lawful research/recovery support.

Every product must become:
`SELL_NOW | ONE_GATE_FROM_SALE | FINISH_FIRST | RESEARCH | FREEZE | KILL`

Historical pricing/revenue/readiness claims are not treated as current facts without revalidation.

Approved commercial direction:
1. Agent Authority & Evidence Audit
2. Agent Reliability / Continuity Audit
3. AI Setup / AI Studio
4. AI Operations
5. Sovereign Twin / Decision Mirror diagnostic
6. Trading Decision Audit / Decision Lab
7. AI Skill Lab
8. workshops/training
9. Archive/Knowledge consolidation
10. Agent fleet architecture/governance

Website changes require each site's own Git/deploy gate.

Commercial evidence chain:
`LEAD -> DISCOVERY -> SCOPED PAIN -> OFFER -> PROPOSAL -> PAYMENT -> DELIVERY -> MEASURED VALUE -> RENEWAL/EXPANSION`

---

# Storage/current cleanup boundary

Last known Library/Drive cleanup state before this global handoff:
- old R59 became non-actionable after authority drift and rollback
- R59R2 required exact owner gate
- R60 HOLD
- generic `го` is not destructive approval where exact token is required
- Drive writes/deletes DENY

Read freshest cleanup handoff again before any destructive storage action.

---

# Gemini Deep Research context

The Gemini master prompt must be sent with an evidence/context pack.
Gemini must reconstruct definitions from supplied evidence and classify every assertion:
`VERIFIED_CURRENT_PROVIDER_STATE | INTERNAL_SOURCE_BACKED | HISTORICAL | SPEC_ONLY | CANDIDATE | INFERENCE | UNKNOWN`.

It must not infer ContinuityOS, Pandora, SCT, HANRI etc. solely from the prompt.

---

# Current execution queue

## P0 CORE
Causal Spine:
fresh provider state is PR #115 head `4ab6c77...` with 23 commits / 10 changed files; PR body is stale. Reconcile exact-head diff -> exact-head CI -> independent review -> update PR metadata -> no merge.

## P0 KNOWLEDGE
continue global product/asset census -> discover Claude/agent-built shells -> aliases/duplicates/supersessions -> evidence-backed product registry.

## P1 GRAPH
locate Pandora canonical/source candidates -> define graph projection contract from Causal Spine/Knowledge Foundry -> integrate without graph truth split.

## P1 SKILLS
inspect user-supplied skill pack -> overlap with `cos advocate`/existing skills -> canonical/domain/local/alias/deprecated/reject.

## P0 CASH
complete product census -> identify true SELL_NOW -> verify current site/source/deploy -> prepare evidence-safe commercial pages.

---

# STEP LEDGER

## GMH-0001
Global handoff initialized as a single cross-project current-source concept.

## GMH-0002
ContinuityOS causal integration surface mapped read-only:
`evidence_common`, `state_resolution`, `current_effect_boundary`, `db`, `store`,
`operational_memory`, `memory_promotion`, `epochgraph`, benchmark/schema conventions.
Decision: Causal Spine is a narrow deterministic derived/read model, not a second memory/control plane.

## GMH-0003
Existing `agent/causal-spine-v1` branch hardened.
Local focused validation:
- 18/18 unit fixtures PASS
- CausalBench 8/8 PASS
- event readback PASS
- tamper rejection PASS
Provider compare then showed candidate 11 commits ahead, 0 behind, exactly 7 changed files.

## GMH-0004
Existing draft PR #115 discovered/reconciled.
Exact PR head observed:
`e7d14326684319b3aa169ea3a0d2a5b9ca2ce25f`
Independent review found CS-R1, CS-R2 and CS-R3 hardening requirements.
PR remains draft/unmerged.

## GMH-0005
Managed Library workspace `/GLOBAL_MAIN_HANDOFF` created.
Library accepted first CURRENT upload but subsequent overwrite/rename operations proved unreliable for that object.
Decision: Library is checkpoint/archive mirror, not sole mutable CURRENT pointer.

## GMH-0006
Dedicated GitHub branch created:
`bitmaster162/control-center:global/main-handoff-current`
to serve as updateable cross-project handoff surface.
No merge into Control Center default branch implied.

## GMH-0007
Previous large create-file write was interrupted before completion.
Provider readback of `handoffs/GLOBAL_MAIN_HANDOFF_CURRENT.md` returned `404`.
The failed attempt is not counted as a successful write.
Recovery action: recreate CURRENT with this compact complete form and verify provider readback.

## GMH-0008
**Time:** 2026-08-22T08:42:27+07:00  
**Lane:** GLOBAL / GEMINI DEEP RESEARCH / CLAUDE HANDOFF

Received four Gemini Deep Research reports and byte-identified them.

Research-cluster rule:
the four Gemini outputs are correlated model-family outputs, not four independent evidence sources.

Created:
- `GEMINI_DEEP_RESEARCH_ADJUDICATION_R1_20260822.md`
- `CLAUDE_OPUS_INDEPENDENT_ADJUDICATION_WORK_ORDER_R1_20260822.md`
- `CLAUDE_REVIEW_PACKET_MANIFEST_R1_20260822.json`
- `CLAUDE_GEMINI_ADJUDICATION_PACKET_R1_20260822.zip`

Accepted as canonical direction from Gemini:
- hard separation `source != build != deployment != runtime != effect != authority`;
- deterministic provider-bound Causal Spine;
- one canonical relational EvidenceStore per runtime;
- bitemporal semantics;
- vector retrieval as derivative only;
- raw content-addressed evidence preservation;
- governed fleet + sealed Work Orders + independent verification;
- portable agent trajectory archive;
- AuthorityLeak/Confused-Deputy security work;
- provider readback / effect reconciliation;
- benchmark program;
- Agent Authority & Evidence Audit as P0 commercial candidate.

Accepted only as direction / benchmark-first:
- PostgreSQL 17 specifically;
- exact schema/table count;
- A2A/MCP internal transport choices;
- Microsoft Agent Framework / OpenAI Agents SDK / Google ADK runtime choice;
- OpenTelemetry/OpenInference mapping details;
- ABAC/MAC implementation;
- mandatory cryptographic signatures;
- exact graph engine.

Held for Claude independent adjudication:
- ArchiveOS keep vs physical merge;
- ContinuityOS logical boundary vs service elimination;
- HANRI vs Control Center merge proposal;
- Return Broker adapt/replace/kill;
- SQLite standalone edge mode;
- TRIAXIS boundary;
- Pandora visual-only vs graph/simulation projection;
- Python vs mandatory Rust for deterministic Causal Spine.

Rejected from automatic adoption:
- blanket KILL/FREEZE of OKX NFT, Crypto Guides, AI Skill Lab, VisionAssist, Sovereign Arena or AI Setup;
- freeze-all-non-core repositories;
- immediate DNS/product shutdown;
- mandatory Gemini pricing/revenue targets;
- enterprise-only strategy that discards the broader portfolio without product-specific evidence.

Fresh ContinuityOS provider readback during this step:
- PR #115: OPEN / DRAFT / UNMERGED / mergeable
- base SHA `021e2d521efc4df0ce390b38a919bc2f0b675460`
- actual head `4ab6c77f714770f2c278dbe9f51cf6f38b9fe474`
- 23 commits
- 10 changed files
- 1434 additions / 0 deletions
- PR body remains stale and still names older head/counts.

External primary-source spot-check:
- A2A v1.0 is current production-ready standard; MCP and A2A are complementary.
- OpenTelemetry GenAI semantic conventions are actively used but continue to evolve; map to them, do not make them our sole canonical trajectory schema.
- Microsoft Agent Framework/Foundry supports A2A/MCP-oriented hosting patterns, but runtime adoption remains benchmark-first.

Authority effect:
research intake + documentation only.
No merge, deploy, runtime, destructive Drive, trading or capital action.

Exact next action:
send Claude the sealed review packet and require a strict ACCEPT/MODIFY/REJECT adjudication; then incorporate only the adjudicated delta into this Global Main Handoff before broader architecture refactors.

---

# Resume protocol

Read this file first, then:
1. verify physical provider/source state relevant to next action;
2. do not rely on stale statuses solely because they appear here;
3. execute one bounded step;
4. read back the result;
5. update this CURRENT file immediately;
6. preserve explicit authority/effect boundaries.

If this file conflicts with current provider physical evidence:
**provider evidence wins; correct this file.**
