# Execution Scope Binder V1

## Purpose

Produce a deterministic, read-only, non-authority answer to one question: **is there a source-bound current executable effect, and if so what exact object/provider/mutation/executor/readback scope is bound?**

The binder never authorizes, executes, deploys, dispatches, messages, trades, spends capital, mutates Return Registry, or changes canonical R64 roots.

## Source precedence

1. Canonical R64 control roots and exact provider readback.
2. Current role views under the same R64 authority anchor.
3. Current non-authority Control Center lifecycle / decision / effect / command projections.
4. Historical implementation and handoff evidence.
5. Historical Return Registry observations.

A historical registry `next` must not override a newer canonical runtime state.

## Fail-closed rules

- `HUMAN_NOW=0` means there is no current human effect gate to bind.
- `effect_candidates_total=0` means there is no current executable effect candidate.
- A semantically accepted historical return may remain evidence while being `HISTORICAL_EVIDENCE_ONLY`.
- Installed/watching in a canonical snapshot is not a fresh process-liveness proof. Runtime liveness remains unverified until a current provider/runtime readback is captured.
- A provider target, mutation set, executor, command, or rollback path must never be invented.
- Conflicting historical/current semantics are surfaced as divergence, not silently reconciled.

## Return Plane current rule

For the currently observed R64 sources:

- canonical CURRENT_STATE binds Return Broker to `INSTALLED_AND_WATCHING`, watcher generation `R59`;
- canonical ROLE_VIEWS binds CODEX-07 to `Return Plane / broker hardening`, state beginning `R59_`;
- registry R43 `ROBERT_MIGRATION_DECISION` is preserved as historical predecessor evidence only;
- there is therefore no current R43 execution gate.

## Required output

The projection must expose:

- authority anchor and exact root IDs/hashes;
- current broker canonical state;
- historical R43/R57/R59/R61 evidence references and evidence quality;
- current HUMAN_NOW and effect candidate counts;
- binding verdict;
- `execution_scope_bound`, `execution_authorized`, `historical_gate_suppressed`;
- runtime-liveness state;
- unresolved provider/mutation/executor/readback details;
- explicit source divergences;
- next read-only action.

## Current expected verdict

`NO_EXECUTABLE_GATE_STALE_R43_PREDECESSOR`

Next allowed action is read-only current broker runtime/repository identity readback. It is not an execution authorization.
