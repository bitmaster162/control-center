# HANRI R38 — Live Truth Projection

## Problem

The Control Center dashboard was a verified static snapshot, not a live truth resolver.
That allowed a source to remain labelled `CURRENT` after a newer accepted source had
superseded it. The UI refresh button also only reloaded the same HTML bytes.

Examples observed before R38:
- R35 runtime sources still carried `CURRENT` after R36 was accepted/live.
- old operational handoff/package evidence could continue supporting current agent status.
- append-only Current Truth contains older sections by design, but the projection layer
  did not distinguish historical facts from current-state claims.

## R38 contract

R38 adds a deterministic read-only truth projection resolver.

```text
verified source observations
-> explicit supersession
-> source-specific TTL policy
-> current-state evidence-ref rewrite
-> freshness propagation
-> projection health receipt
-> schema-compatible dashboard snapshot
```

The resolver returns two objects:
- `snapshot`: remains compatible with the existing v1 dashboard schema;
- `receipt`: exact audit of applied supersession, TTL checks, ref rewrites, degradation
  and the no-effect boundary.

Superseded sources are represented as `freshness=STALE` in the v1 snapshot and receive
an audit marker in `notes` (`SUPERSEDED_BY:<source_id>`). The exact mapping is also
recorded in the R38 receipt.

## Current state versus history

Supersession is applied only to:
- KPIs;
- current actions;
- systems;
- agents;
- decisions.

Historical `events` remain append-only and retain their original evidence references.
R35 being historical does not make the fact that R35 once passed invalid.

## Freshness

No universal TTL is invented. `r38.truth-projection-policy.json` declares source-specific
TTL rules and their basis. When evidence is too old, the current-state claim becomes
`STALE` or `UNKNOWN`; it may not render as fresh green truth.

## Browser boundary

R38 does not put Drive/GitHub credentials into the browser. The static dashboard may
reload its file, but provider reads and projection regeneration occur outside the browser
through bounded Control Center/HANRI tooling.

## Effect boundary

R38 projection reconciliation is read-only:
- no provider writes;
- no external messages;
- no self-application;
- TradingOS untouched;
- `can_trade=false`;
- `capital_permission=DENY`.

A generated dashboard replacement remains a separate `WRITE_REVERSIBLE` effect requiring
an exact hash-bound human approval, fresh BEFORE readback, AFTER readback and rollback
contract.
