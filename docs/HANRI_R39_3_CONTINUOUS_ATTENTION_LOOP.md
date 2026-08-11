# HANRI R39.3 — Continuous Attention Loop

## Purpose

R39.0–R39.2 established one complete evidence-backed attention cycle across:

- SELF
- AGENT
- SYSTEM
- OPERATOR

The R39.2.2 real-host result closed all four domains with no material findings and no effects. R39.3 adds the missing temporal layer: HANRI remembers what it already inspected, what changed, what proposals existed, what outcomes were observed, and where attention should move next.

This is the first stateful `attention over attention` loop. It is **not** a scheduler installation and it does not apply recommendations.

## Semantic cycle versus wake

A scheduled process may wake frequently. A wake is not automatically a new semantic event.

R39.3 therefore separates:

- `wake_count` — increments whenever the loop is invoked;
- `semantic_cycle_count` — increments only when the canonical evidence-set hash changes;
- `NO_DELTA` — exact same evidence set as the prior wake;
- `SEMANTIC_DELTA` — changed evidence set;
- `INITIALIZED` — first accepted state.

Repeated identical evidence does not increment proposal `seen_semantic_cycles` and does not create duplicate findings.

## Durable attention memory

The local state stores only bounded metadata:

- canonical evidence-set SHA-256;
- current coverage and per-domain coverage memory;
- bounded proposal lifecycle metadata and proposal fingerprint;
- recommendation outcome status and evidence fingerprint;
- unresolved negative outcomes;
- next-attention mode/focus;
- a bounded transition history tail;
- a state SHA-256 that is verified before every successor transition.

A tampered prior state fails closed.

## Proposal lifecycle

A current proposal is tracked as `PROPOSAL_ONLY` unless an outcome changes its status.

If a proposal disappears from a later semantic evidence set, R39.3 records `NOT_CURRENTLY_OBSERVED`. It does **not** claim `VERIFIED_IMPROVED` from absence alone.

Recommendation outcomes are persistent memory:

- `REGRESSED` or `VERIFIED_NO_EFFECT` => unresolved negative outcome and `SELF_REVIEW_REQUIRED`;
- `VERIFIED_IMPROVED` supersedes the negative state for that recommendation ID.

## Next-attention modes

R39.3 selects an advisory attention focus only:

- `SELF_REVIEW_REQUIRED` — unresolved negative recommendation outcome;
- `COVERAGE_REPAIR_REQUIRED` — at least one SELF/AGENT/SYSTEM/OPERATOR domain is uncovered;
- `IMPROVEMENT_REVIEW` — current material evidence produced proposals;
- `EVIDENCE_REFRESH_FOCUS` — repeated no-delta wakes reached the configured threshold;
- `MAINTAIN_BALANCED_COVERAGE` — full coverage, no material proposals; next audit biases toward least-observed domains.

These are attention-routing recommendations, not execution authority.

## Self-feedback containment

R39.2.2 observes `%LOCALAPPDATA%\ControlCenterHANRIR39\receipts` as a HANRI evidence source.

If R39.3 wrote a fresh loop receipt into that same directory on every wake, the next producer cycle would ingest HANRI's own wake receipt as new evidence. That would create a recursive self-observation loop and defeat `NO_DELTA` semantics.

R39.3 therefore isolates generated runtime artifacts into sibling roots:

- `continuous_work`
- `continuous_state`
- `continuous_receipts`

None is inside the R39 receipt source. The existing R39 receipt source remains read-only.

## Current host runner

`Run-R39.3ContinuousAttentionLoop-PS51.ps1` performs one manual cycle:

1. verify local regressions;
2. collect R39.2.2 producer evidence;
3. run R39.1 Attention Fabric;
4. advance R39.3 durable loop state;
5. verify full coverage and all zero-effect boundaries;
6. emit local continuous state and receipt.

Running it again is safe. Identical evidence should produce `NO_DELTA`; real producer changes produce `SEMANTIC_DELTA`.

## Effect boundary

R39.3 remains proposal/attention state only:

- provider calls: false
- scheduler install: false
- human decision execution: false
- self-apply: false
- skill install: false
- system write: false
- operator message: false
- auto-dispatch: false
- external messages: false
- can_trade: false
- capital_permission: DENY

Scheduler installation, live provider projection and any accepted improvement effect remain separate governed actions.
