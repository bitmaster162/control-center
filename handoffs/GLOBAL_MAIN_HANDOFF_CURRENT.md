# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T08:51:09+07:00

## Canonical location

- repo: `bitmaster162/control-center`
- branch: `global/main-handoff-current`
- path: `handoffs/GLOBAL_MAIN_HANDOFF_CURRENT.md`

This is the live cross-project resume/current-state source. Full historical detail remains recoverable from Git history and named evidence artifacts; CURRENT stays compact enough to be replaced safely after every material step.

## Authority boundary

`source != build != deployment != runtime != effect != authority`

This handoff records evidence, decisions, current state and next actions. It never self-grants effect authority.

Global defaults unless a fresher exact project gate overrides them:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge solely from this handoff
- no deploy solely from this handoff
- no workflow rerun solely from this handoff
- no destructive Drive action solely from this handoff
- generic `го` is not an exact destructive approval token

Provider physical evidence wins over stale handoff text.

---

# 1. Global architecture — current accepted model

```text
ROBERT / HUMAN SOVEREIGN
        |
        v
CONTROL CENTER
accepted intent / current-truth projection / effect gate
        |
   +----+--------------------+
   |                         |
   v                         v
 HANRI                     TRIAXIS
 freshness /               independent adversarial
 contradiction /           verification
 attention
   |                         |
   +-----------+-------------+
               v
       KNOWLEDGE FOUNDRY
 claims / evidence / contradictions / causal relations
               |
       +-------+-------+
       |               |
       v               v
 CONTINUITYOS       ARCHIVEOS
 events/replay      raw evidence custody
       |               |
       +-------+-------+
               v
          EVIDENCESTORE
  canonical relational state + provenance
               |
       +-------+-------+
       |               |
       v               v
 SOVEREIGN TWIN     RETRIEVAL / GRAPH
 Person/Decision    derived indexes/projections
       |
       v
 DOMAIN CELLS
 TradingOS / NFT / VisionAssist / AI Skill Lab /
 Amora / Crypto Guides / other products
```

BitEvo = commercial/operator umbrella and customer-facing adapter. It is not a second canonical DB, Control Center, ArchiveOS or ContinuityOS.

Logical responsibility and physical storage/process topology are separate decisions. Shared PostgreSQL does not automatically mean one monolithic service.

---

# 2. Causal Spine — P0 CORE

Accepted completeness rule:

`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`

Missing/unproven frontier => `CAUSAL_SPINE_INCOMPLETE`.

`NO_MATERIAL_PIVOT_FOUND` is valid only with completed bounded-search evidence.

Required states:
- `COMPLETE`
- `INCOMPLETE_ORIGIN`
- `INCOMPLETE_PIVOT`
- `INCOMPLETE_CURRENT_STATE`
- `SEARCH_INCOMPLETE`
- `CONTRADICTED`
- `SUPERSEDED`

Passing the causal gate grants no source/canonical/merge/deploy/runtime/trading/capital/effect authority.

## Live GitHub lane

Repo: `bitmaster162/continuityos`  
Issue: `#111 — P0: Implement Causal Spine Gate + CausalBench v0`  
Draft PR: `#115`  
Branch: `agent/causal-spine-v1`  
Base: `master@021e2d521efc4df0ce390b38a919bc2f0b675460`  
Fresh head: `c2da7c239f71117fc651adfb4fa1bfaca115d94e`

Fresh compare:
- ahead_by: 24
- behind_by: 0
- merge-base: exact base above
- changed files: 11
- additions: 1450
- deletions: 0

Exact scope:
1. `bench/causalbench.py`
2. `continuityos/causal_spine_schemas/__init__.py`
3. `continuityos/causal_spine_schemas/causal_spine_event_v1.schema.json`
4. `continuityos/causal_spine_schemas/causal_spine_receipt_v1.schema.json`
5. `continuityos/causal_spine_schemas/causal_spine_v1.schema.json`
6. `continuityos/gate/causal_spine.py`
7. `pyproject.toml` — one package-data line only
8. `tests/test_causal_spine_schema_package_v1.py`
9. `tests/test_causal_spine_strict_provenance_v1.py`
10. `tests/test_causal_spine_v1.py`
11. `tests/test_causalbench_v0.py`

Historical defects closed/regression-covered in source:
- CS-R1 cross-subject current-state binding
- CS-R2 rehashed authority/effect laundering rejection
- CS-R3 `state_id` provider-evidence binding

New exact-benchmark hardening:
`tests/test_causalbench_v0.py` now executes `bench.causalbench.run()` under full pytest and requires:
- 11/11 cases OK
- benchmark status PASS
- event readback PASS
- tamper rejection PASS
- rehashed effect forgery rejection PASS
- rehashed authority forgery rejection PASS
- `can_trade=false`
- `capital_permission=DENY`
- deployment false

Previous head `4ab6c77...` had all three workflows PASS. New head `c2da7c2...` triggered normal synchronize validation, no rerun requested:
- CodeQL `32544554859` — IN_PROGRESS at last read
- P0 Unified Shadow Continuity `32544554891` — IN_PROGRESS at last read
- review-gates `32544554868` — IN_PROGRESS at last read

PR remains draft/unmerged. PR body is still stale until exact-head CI closes.

**Next P0 action:** read exact-head CI for `c2da7c2...`; if green, reconcile PR body/current identity and perform independent technical review. Do not merge.

---

# 3. Memory / knowledge target

## Universal Artifact Identity

Every physical object should bind at minimum:
`artifact_id, source_system, provider_object_id, provider_revision_id, locator, mime_type, size_bytes, sha256_raw, observed_at, custody_role`, plus derived/parent/semantic-family relations where applicable.

Dedup levels:
- T0 EXACT — same bytes/hash
- T1 DERIVED — same logical object, different representation/version/export
- T2 RELATED — separate evidence for same event/decision/project state

Rule: collapse meaning first; physical deletion only under separate custody/recovery proof and exact authority.

## Universal ingestion

`DISCOVER -> IDENTIFY -> HASH RAW -> PRESERVE RAW -> PARSE -> NORMALIZE -> CLASSIFY -> DEDUP -> SEMANTIC FAMILY -> AUTHORSHIP -> PROVENANCE -> EVENT EXTRACTION -> CAUSAL FRONTIERS -> CONTRADICTIONS -> CURRENT-STATE OBSERVATION -> SQL WRITE -> READBACK -> RETRIEVAL -> GRAPH PROJECTION`

Planned sources include ChatGPT Library, Drive, GitHub, local machines, servers, deployment providers, Gemini, Claude, Codex, Manus, Antigravity and supplied archives/logs/docs.

## Storage direction

Accepted direction from internal work + Gemini cluster:
- one canonical relational EvidenceStore per runtime;
- PostgreSQL production target, exact version benchmark/current-support dependent;
- bitemporal `valid_time` + `transaction_time`;
- pgvector and lexical indexes are derived retrieval only;
- ArchiveOS/raw CAS preserves exact bytes/provenance;
- no peer canonical SQLite↔PostgreSQL synchronization;
- SQLite remains valid as standalone/local/test backend if one backend is canonical for that runtime.

Do not infer that shared PostgreSQL requires deleting ContinuityOS, ArchiveOS or Knowledge Foundry responsibility boundaries.

---

# 4. Agent Trajectory Bundle

Target portable bundle:

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
OpenTelemetry/OpenInference may be mappings/interoperability, not replacements for the canonical provider-neutral bundle.

---

# 5. Pandora / graph

Pandora is a real existing line with runnable engine / Epoch DAG / 3D graph playback and related integration research.

Target projection layers:
- G0 provenance
- G1 event/supersession
- G2 claim/evidence
- G3 causal spine
- G4 decision/outcome
- G5 agent trajectory
- G6 project/product/dependency
- G7 Person/Decision Twin

Pandora target role: graph/epoch/time playback, causal browser, diff and optional scenario/simulation surface. It does not own canonical truth or approval authority.

Graph engine choice remains benchmark-first.

---

# 6. Governed fleet / standards

Pattern:
`WORK ORDER -> FROZEN INPUT -> SPECIALIST -> INDEPENDENT VERIFIER -> DETERMINISTIC CHECKS -> ADVERSARIAL REVIEW -> HUMAN/EFFECT GATE -> RECEIPT`

Deterministic functions remain deterministic: hashes, schema validation, baseline checks, provider readback, provenance FK checks, effect admission, capital/risk constraints and final causal completeness.

A2A and MCP are valid interoperability candidates. Framework choice (Microsoft Agent Framework / OpenAI Agents SDK / Google ADK / custom bounded runtime) is benchmark-first, not a naming preference.

WIP:
- P0 CASH max 1 main offer
- P0 CORE max 1 infrastructure frontier
- P1 PRODUCT max 2 finish-to-market lanes
- P2 RESEARCH parallel but bounded/read-only

---

# 7. Decision Intelligence / skills

Existing ContinuityOS substrate: `cos advocate` with contradiction, staleness, evidence, canon, overconfidence, honesty, reversibility, alternatives, assumptions and blast-radius checks.

Requested aliases include:
`/DEVIL /PREMORTEM /BLINDSPOT /STEELMAN /RIPPLE /REALPC /COMPARE /PRIMER /MENTALMODEL /MYTHS /TLDR /DECISIONS`

Additional candidates:
`/THESIS /EVIDENCE /INVALIDATE /CATALYST /SCENARIOS /POSITION /COUNTERFACTUAL /POSTMORTEM /CALIBRATE /SOURCECHECK /REGIME /NO_TRADE`

Composites:
- `/REDTEAM = DEVIL + BLINDSPOT + PREMORTEM + STEELMAN`
- `/DECIDE = evidence/thesis/adversarial/invalidation/TRIAXIS -> Decision Card`

No skill gets autonomous trading/capital authority.

User will provide additional recent skill pack for exact intake/classification.

---

# 8. Benchmarks

External comparison candidates:
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

Gemini useful delta accepted: explicit Confused-Deputy/delegated-authority tests, untrusted-ingest taint, cross-tenant isolation, secret/PII redaction before telemetry persistence, provider effect readback and calibration metrics where mathematically appropriate.

---

# 9. Commercial/product program

BitEvo remains umbrella, not infrastructure truth owner.

Known families include trading/crypto, core AI/memory/governance, services/education, consumer/accessibility/creative and investigation/evidence products.

Every product must eventually classify from live evidence:
`SELL_NOW | ONE_GATE_FROM_SALE | FINISH_FIRST | RESEARCH | FREEZE | KILL | CURRENTNESS_UNKNOWN`

No blanket Gemini KILL/FREEZE was accepted for OKX NFT, Crypto Guides, AI Skill Lab, VisionAssist, Sovereign Arena, AI Setup or other products.

Current P0 commercial candidate:
**Agent Authority & Evidence Audit**.

Other accepted directions:
- Agent Reliability / Continuity Audit
- AI Setup / AI Studio
- AI Operations
- Sovereign Twin / Decision Mirror diagnostic
- Trading Decision Audit / Decision Lab
- AI Skill Lab
- Archive/Knowledge consolidation
- Agent fleet architecture/governance

Exact prices, margins, sales cycles and revenue targets remain hypotheses until observed.

Commercial evidence chain:
`LEAD -> DISCOVERY -> SCOPED PAIN -> OFFER -> PROPOSAL -> PAYMENT -> DELIVERY -> MEASURED VALUE -> RENEWAL/EXPANSION`

---

# 10. Gemini Deep Research intake / Claude adjudication

Four Gemini Deep Research reports were received and treated as one correlated research cluster, not four independent evidence sources.

Created sealed Claude packet:
- `GEMINI_DEEP_RESEARCH_ADJUDICATION_R1_20260822.md`
- `CLAUDE_OPUS_INDEPENDENT_ADJUDICATION_WORK_ORDER_R1_20260822.md`
- `CLAUDE_REVIEW_PACKET_MANIFEST_R1_20260822.json`
- `CLAUDE_GEMINI_ADJUDICATION_PACKET_R1_20260822.zip`

User delivered the packet to Claude.

Accepted from Gemini as direction/canon where already aligned:
Causal Spine, bitemporal EvidenceStore, raw CAS, derived vectors, governed fleet, trajectory archive, provider readback, authority-leak security, benchmark program and Agent Authority/Evidence Audit wedge.

Held for Claude independent adjudication:
- ArchiveOS topology
- ContinuityOS persistence vs service boundary
- HANRI vs Control Center separation
- Return Broker adapt/replace/kill
- SQLite edge boundary
- TRIAXIS structure
- Pandora scope
- Python vs mandatory Rust
- standards/framework adoption details
- enterprise-first vs portfolio-parallel product strategy

Rejected from automatic Gemini adoption:
blanket product shutdowns, freeze-all-non-core, immediate DNS shutdown, mandatory revenue/pricing numbers and enterprise-only portfolio destruction.

---

# 11. Storage cleanup boundary

Last known cleanup authority remains conservative:
- old R59 non-actionable after authority drift/rollback
- R59R2 required exact owner gate
- R60 HOLD
- Drive writes/deletes DENY in that cleanup lineage

Read freshest cleanup handoff before any destructive storage mutation.

---

# 12. Current execution queue

## P0 CORE — ACTIVE
Causal Spine PR #115 exact head `c2da7c2...`: exact CausalBench now CI-gated; synchronize checks running. Next = exact-head CI readback -> PR metadata reconciliation -> independent technical review -> no merge.

## P0 KNOWLEDGE — READY READ-ONLY
Continue evidence-backed product/asset census, especially Claude/agent-built product shells, aliases, duplicates and supersessions.

## P1 GRAPH — READY READ-ONLY
Locate Pandora canonical/source candidates and freeze projection contract from Causal Spine/Knowledge Foundry without graph truth split.

## P1 SKILLS — WAITING INPUT
Inspect user-supplied skill pack; classify canonical/domain/local/alias/deprecated/reject.

## P0 CASH — READY
Complete product census and establish true `SELL_NOW` offers with current source/deployment/customer evidence.

---

# 13. Recent GMH ledger

## GMH-0008 — Gemini research intake / Claude handoff
Four correlated Gemini reports were adjudicated. Consensus technical direction accepted with boundaries; destructive subsystem/product recommendations held/rejected pending independent evidence. Claude received a sealed independent adjudication packet. No effect authority granted.

## GMH-0009 — CausalBench exact CI gate
Fresh review found that `bench/causalbench.py` existed but was not directly executed by review-gates. Added `tests/test_causalbench_v0.py` to the existing candidate branch.

New exact head: `c2da7c239f71117fc651adfb4fa1bfaca115d94e`.

Compare to base: 24 ahead / 0 behind, 11 files, 1450 additions, 0 deletions. Scope remains Causal Spine plus one `pyproject.toml` package-data line.

Normal synchronize CI started automatically; no rerun requested. PR remains draft/unmerged.

Authority effect: candidate test/source write only; no merge, deployment, runtime, Drive, trading or capital effect.

---

# Resume protocol

1. Read this file first.
2. Fresh-read physical provider state for the next action.
3. Execute one bounded step.
4. Read back the result.
5. Update this CURRENT file immediately.
6. Preserve authority/effect boundaries.
7. Significant milestones may get immutable snapshots; CURRENT keeps the stable path.

If this file conflicts with provider evidence: **provider evidence wins; correct this file.**
