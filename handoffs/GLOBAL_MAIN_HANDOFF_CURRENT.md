# GLOBAL MAIN HANDOFF — CURRENT

**Status:** ACTIVE / CANONICAL WORKING SOURCE  
**Owner:** Robert  
**Maintainer:** ChatGPT  
**Timezone:** Asia/Bangkok  
**Last updated:** 2026-08-22T08:53:20+07:00

## Canonical location

`bitmaster162/control-center` → branch `global/main-handoff-current` → `handoffs/GLOBAL_MAIN_HANDOFF_CURRENT.md`

This is the live cross-project resume/current-state source. Historical detail remains in Git history and named evidence artifacts.

## Global authority boundary

`source != build != deployment != runtime != effect != authority`

Defaults unless a fresher exact project gate overrides them:
- `can_trade=false`
- `capital_permission=DENY`
- `execution_authority=NONE`
- no merge/deploy/runtime mutation solely from this handoff
- no workflow rerun solely from this handoff
- no destructive Drive action solely from this handoff
- generic `го` is not an exact destructive approval token

Provider physical evidence wins over stale handoff text.

---

# Global architecture — accepted working model

`Robert/Human Sovereign → Control Center → {HANRI, TRIAXIS} → Knowledge Foundry → {ContinuityOS, ArchiveOS} → EvidenceStore → {Sovereign Twin, Retrieval/Graph} → domain products`

Boundaries:
- Control Center = accepted intent/current-truth projection/effect gate.
- HANRI = freshness/contradiction/attention/shadow proposals; no self-approval.
- TRIAXIS = logically independent adversarial verifier.
- ContinuityOS = event/replay/continuity semantics.
- ArchiveOS = exact raw evidence/provenance custody.
- Knowledge Foundry = claims/evidence/contradiction/causal processing; no self-promotion to truth.
- EvidenceStore production direction = one canonical relational backend per runtime, PostgreSQL target, bitemporal `valid_time` + `transaction_time`.
- pgvector/lexical/graph indexes = derived retrieval/projections, not truth authority.
- SCT/Person Twin/Decision Twin = provider-independent read-only projection, `execution_authority=NONE`.
- BitEvo = commercial/operator umbrella, not a second infrastructure truth owner.
- Pandora = graph/epoch/time/causal visualization and optional simulation projection; no canonical truth authority.

Logical responsibility and physical storage/process topology are separate decisions. Shared PostgreSQL does not imply one monolithic process.

---

# P0 CORE — Causal Spine

Accepted rule:
`ORIGIN + MATERIAL CORRECTION/PIVOT + CURRENT PHYSICAL STATE`

Missing/unproven frontier => `CAUSAL_SPINE_INCOMPLETE`.
`NO_MATERIAL_PIVOT_FOUND` requires completed bounded-search evidence.
A causal pass grants no source/canonical/merge/deploy/runtime/trading/capital/effect authority.

## Live GitHub lane

Repo: `bitmaster162/continuityos`  
Issue: `#111`  
Draft PR: `#115`  
Branch: `agent/causal-spine-v1`  
Base: `master@021e2d521efc4df0ce390b38a919bc2f0b675460`  
Fresh head: `8753edf511ec9cc195ca0369a8741279a5eda5a8`

Fresh PR readback:
- OPEN
- DRAFT
- UNMERGED
- mergeable TRUE
- 25 commits
- 11 changed files
- 1460 additions / 0 deletions

Scope remains narrow:
- Causal Spine implementation
- 3 strict Draft 2020-12 schemas + package marker
- CausalBench v0
- causal unit/adversarial/schema/benchmark tests
- one `pyproject.toml` package-data line

Closed/regression-covered defects:
- CS-R1 cross-subject current-state binding
- CS-R2 rehashed authority/effect laundering
- CS-R3 `state_id` provider-evidence binding

## Exact benchmark / wheel boundary

At superseded head `c2da7c239f71117fc651adfb4fa1bfaca115d94e`:
- clean-source full pytest collected 1177 tests and completed `1165 passed, 12 skipped, 8 subtests passed`;
- this clean-source run included `tests/test_causalbench_v0.py`, therefore CausalBench itself passed on that exact source head;
- wheel build succeeded and included `continuityos/gate/causal_spine.py` plus all 3 causal schemas;
- Ubuntu wheel-only collection failed only because `tests/test_causalbench_v0.py` imported source-only `bench.causalbench`, while `bench/` is intentionally not shipped in the production wheel;
- CodeQL and P0 Unified Shadow Continuity were PASS on `c2da7c2...`.

Boundary correction committed at current head `8753edf5...`:
- source/editable CI still executes CausalBench v0;
- wheel-only test skips the benchmark only when the parent package `bench` itself is absent;
- any other `ModuleNotFoundError` is re-raised, so benchmark-internal missing dependencies are not masked;
- production wheel continues to be tested through packaged Causal Spine implementation/schema tests rather than packaging the benchmark corpus.

New normal synchronize-triggered workflows for `8753edf5...`:
- CodeQL `32544706731` — IN_PROGRESS at last read
- P0 Unified Shadow Continuity `32544706744` — IN_PROGRESS at last read
- review-gates `32544706828` — PENDING at last read

No workflow rerun requested. PR remains draft/unmerged.

**Exact next P0 action:** read exact-head CI for `8753edf5...`; if all required checks pass, reconcile stale PR #115 body to exact identity/evidence, perform independent technical review, keep draft/unmerged.

---

# Memory / knowledge / trajectory program

Universal Artifact Identity binds source/provider IDs, revision, locator, raw SHA-256, size/type, observed time, custody role, parent/derived relations and semantic-family identity.

Dedup:
- T0 EXACT = same bytes/hash
- T1 DERIVED = same logical object, different representation/version/export
- T2 RELATED = distinct evidence for same event/decision/project state

Universal ingestion target:
`DISCOVER → IDENTIFY → HASH RAW → PRESERVE RAW → PARSE → NORMALIZE → CLASSIFY → DEDUP → SEMANTIC FAMILY → AUTHORSHIP → PROVENANCE → EVENT EXTRACTION → CAUSAL FRONTIERS → CONTRADICTIONS → CURRENT-STATE OBSERVATION → SQL WRITE → READBACK → RETRIEVAL → GRAPH PROJECTION`

Agent Trajectory Bundle target:
`RUN_MANIFEST + INPUT_REFERENCES + ENVIRONMENT + TOOL_EVENTS + MODEL_EVENTS + DECISIONS + OUTPUTS + PATCHES + SCREENSHOTS + RECEIPTS + FINAL_RESPONSE + REDACTION_REPORT + MANIFEST.sha256`.

OpenTelemetry/OpenInference may map to the bundle; they do not replace the provider-neutral canonical trajectory contract.

---

# Governed fleet / skills / benchmarks

Fleet pattern:
`WORK ORDER → FROZEN INPUT → SPECIALIST → INDEPENDENT VERIFIER → DETERMINISTIC CHECKS → ADVERSARIAL REVIEW → HUMAN/EFFECT GATE → RECEIPT`

A2A/MCP/framework adoption is benchmark-first. Commodity transport may be replaced without deleting unique custody/authority semantics.

Decision aliases under design include `/DEVIL`, `/PREMORTEM`, `/BLINDSPOT`, `/STEELMAN`, `/RIPPLE`, `/REALPC`, `/COMPARE`, `/PRIMER`, `/MENTALMODEL`, `/MYTHS`, `/TLDR`, `/DECISIONS`, `/THESIS`, `/EVIDENCE`, `/INVALIDATE`, `/CATALYST`, `/SCENARIOS`, `/POSITION`, `/COUNTERFACTUAL`, `/POSTMORTEM`, `/CALIBRATE`, `/SOURCECHECK`, `/REGIME`, `/NO_TRADE`.
No skill gets autonomous trading/capital authority.

Internal benchmark program:
CausalBench, CurrentTruthBench, AuthorityLeakBench, ContradictionBench, EffectBench, ColdStartBench, CrossModelHandoffBench, AgentTrajectoryReplayBench, DecisionCalibrationBench.

---

# Gemini intake / Claude adjudication

Four Gemini Deep Research outputs were accepted as one correlated research cluster, not four independent sources.

Accepted direction:
Causal Spine, bitemporal canonical EvidenceStore, raw CAS, derived retrieval, governed fleet, trajectory archive, provider effect readback, authority-leak/confused-deputy security, benchmark program, and Agent Authority & Evidence Audit commercial wedge.

Held for Claude independent adjudication:
ArchiveOS topology; ContinuityOS storage/service boundary; HANRI vs Control Center separation; Return Broker adapt/replace/kill; SQLite edge boundary; TRIAXIS structure; Pandora scope; Python vs mandatory Rust; framework/standards choices; enterprise-first vs portfolio-parallel strategy.

Rejected from automatic Gemini adoption:
blanket product KILL/FREEZE, freeze-all-non-core, immediate product/DNS shutdowns, mandatory price/revenue targets, and enterprise-only destruction of broader option value.

Claude received the sealed adjudication packet. No Claude result has been accepted yet.

---

# Commercial/product program

Every product must eventually be classified from live evidence:
`SELL_NOW | ONE_GATE_FROM_SALE | FINISH_FIRST | RESEARCH | FREEZE | KILL | CURRENTNESS_UNKNOWN`.

P0 commercial candidate: **Agent Authority & Evidence Audit**.
Other live directions include Agent Reliability/Continuity Audit, AI Setup/Studio, AI Operations, Sovereign Twin diagnostic, Trading Decision Audit/Lab, AI Skill Lab, Archive/Knowledge consolidation and Fleet Architecture/Governance.

Exact pricing, margins, sales cycles and revenue targets remain hypotheses until observed.

Commercial evidence chain:
`LEAD → DISCOVERY → SCOPED PAIN → OFFER → PROPOSAL → PAYMENT → DELIVERY → MEASURED VALUE → RENEWAL/EXPANSION`.

---

# Storage cleanup boundary

Last known destructive cleanup lineage remains conservative:
- old R59 non-actionable after authority drift/rollback
- R59R2 required exact owner token
- R60 HOLD
- Drive writes/deletes DENY in that lane

Read freshest cleanup handoff before any destructive storage mutation.

---

# Current queue

1. **P0 CORE ACTIVE:** exact-head Causal Spine CI → PR metadata reconciliation → independent review → no merge.
2. **P0 KNOWLEDGE READ-ONLY:** product/asset census; Claude/agent-built shells; aliases/duplicates/supersessions.
3. **P1 GRAPH READ-ONLY:** Pandora canonical/source census and projection contract.
4. **P1 SKILLS WAITING INPUT:** user skill pack intake/classification.
5. **P0 CASH READY:** evidence-backed `SELL_NOW` classification and commercial packaging.

---

# Recent GMH ledger

## GMH-0008 — Gemini research intake / Claude handoff
Gemini cluster adjudicated with boundaries. Claude received sealed independent adjudication packet. No effect authority granted.

## GMH-0009 — Exact CausalBench CI gate added
Added `tests/test_causalbench_v0.py`; candidate became `c2da7c2...`. Scope remained narrow. Normal CI triggered automatically.

## GMH-0010 — Wheel-boundary defect caught and corrected
The new benchmark gate proved useful: clean-source full pytest including CausalBench passed, while Ubuntu wheel-only failed because source-only `bench/` is intentionally not shipped. Corrected the test boundary rather than polluting the production wheel with benchmark code. New head `8753edf5...`; new normal CI started. No rerun, merge, deploy or runtime effect.

---

# Resume protocol

Read this file first → fresh-read provider state → execute one bounded step → read back result → update CURRENT → preserve authority/effect ceilings.

If this file conflicts with provider evidence: **provider evidence wins; correct this file.**
