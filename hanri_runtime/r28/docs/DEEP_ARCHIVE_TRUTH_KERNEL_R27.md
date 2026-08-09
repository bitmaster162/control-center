# Deep Archive Truth-Kernel Pass R27

## Verdict

The archive's next limiting factor is not unread prose. It is **semantic accounting**: counts, scopes, evidence families, authority surfaces and implementation status are repeatedly mixed across different universes.

## New exact findings

### 1. Handoff collector arithmetic

The physical `HANDOFF_CANDIDATES.csv` has 206 rows. Exact reconstruction:

```text
safe rows                         183
  unique safe hashes               99
  additional safe duplicate rows   84
unsafe/excluded rows                23
--------------------------------------
total                              206
```

Across all 206 rows there are 121 unique hashes and 85 duplicate occurrences. The Fable report used `99 + 85 + 23` as if the terms were disjoint. They are not: one duplicate occurrence is inside the unsafe/excluded set. The collector itself is intact; the report's count semantics require revision.

### 2. Checkpoint evidence universes

The primary meta-audit states:

```text
all parsed checkpoint records: 970
  evidenced by local artifact: 327
  at most claimed:             643

strong-progress subset:        787
  at most claimed:             551
  derived remainder:           236
```

The consolidated report incorrectly phrases 327 and 551 as one partition of 787. The 327 figure belongs to the 970-record universe.

### 3. Proof ledger is narrative, not proof

233 records were inspected; zero had `proof_id`, hash/digest, signature or status. The correct classification is `NARRATIVE_EVIDENCE_DEBT`, not machine-verifiable proof.

### 4. Five BitEvo canon copies are one evidence family

Five Drive objects named `Bit Evo Unified Canonical State.docx` were downloaded and are byte-identical:

```text
size: 26,754 bytes
SHA-256: a96b9c26eb45a77b8341d04d5173cdd05df45f32524aa95910b43ae54c90b654
occurrences: 5
independent evidence families: 1
```

### 5. The original architecture was stronger than the implementation

The BitEvo canon already contains the right high-level rules: raw archive as source, derived layers recomputable, governed memory writes, contradiction tracking, event log/reducers/snapshots, energy budgeting and a human coevolution layer.

Current physical evidence does not show one implemented Unified Canonical State. MAIN-033 found no root Git baseline, three nested repositories, a current state inconsistent with historical cp-0388 and an absent expected-312 source. The July audit also documented conflicting mutation paths.

Therefore:

```text
UNIFIED_CANONICAL_STATE = COHERENT SPECIFICATION
CURRENT IMPLEMENTATION = FRAGMENTED / NOT YET ADMITTED
```

## Root-cause compression

The many archive failures compress into six durable clusters:

1. **Universe/denominator drift** — counts from different populations are mixed.
2. **Occurrence/evidence-family drift** — repeated copies become false corroboration.
3. **Authority-surface drift** — several mutation paths compete with the declared canonical writer.
4. **Specification/implementation drift** — canon prose is treated as deployed capability.
5. **Proof-identity debt** — narrative ledger rows lack machine-verifiable identity.
6. **Freshness drift** — historical liveness and post-fix claims are promoted without current readback.

## R27 improvement

HANRI R27 adds deterministic gates for these six clusters and introduces a minimal Truth Kernel schema. It remains shadow-only and cannot self-apply changes.
