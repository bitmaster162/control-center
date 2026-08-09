# Causal Spine Archive Protocol R26

## Unit of progress

A valid archive-improvement cycle contains three separately identified physical sources:

1. **ORIGIN** — the earliest relevant intent, need or design.
2. **PIVOT** — the material correction, falsification, supersession or operator decision.
3. **CURRENT** — the newest physical implementation/state/receipt.

```text
ORIGIN != PIVOT != CURRENT
```

A direct origin/current bridge is insufficient when a material correction occurred between them.

## Causal claim ceiling

The scanner may prove file identity, content class, time, hash, scope and version collision. It may not prove semantic causality by selection alone. Causal promotion requires primary evidence or Human adjudication.

## Lineage cursors

Keep separate:

- `SOURCE001_PRIMARY_CURSOR` — 536-conversation primary export.
- `LEGACY_2503_CURSOR` — 473-conversation legacy raw export and cumulative analytical steps.
- `COWORK_SESSION_CURSOR` — Cowork/session/artifact lineage.
- `CURRENT_RETURN_CURSOR` — current physical agent returns.

Numerical equality between cursors has no meaning without source identity.

## Scope-bound completeness

Every completeness statement requires:

```text
scope_id
scope_manifest_sha256
numerator
denominator
evidence_ceiling
per-file ledger
```

`99/99 HANDOFF_RECOVERY` cannot be restated as `all archives complete`.

## Stop rule

Stop the cycle when it changes none of:

- an accepted decision;
- a current-state conflict;
- a regression case;
- a source/attachment gap;
- a product/research candidate;
- a next physical gate.
