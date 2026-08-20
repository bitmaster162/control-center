# AGENT CONTROL PLANE V1

Status: REVIEW ONLY / NON-AUTHORITY PROJECTION

## Purpose

Convert exact provider readback of the R64 Control Center pointer plus the current Return Registry into an operator-facing fleet/dispatch projection.

This layer answers:

- which execution/observer slots are known;
- what each slot currently reports;
- which work order is bound to each slot;
- which pending work is blocked from dispatch;
- which bounded items deserve operator attention;
- which states remain registry observations rather than semantic acceptance or apply authority.

## Authority boundary

The Agent Control Plane is never an authority writer.

Canonical authority remains the accepted R64 pointer and stable roots.

Return Registry authority remains transport/registry custody only. A registry state such as `OUTCOME_PASS`, `PENDING_EXECUTION`, `HUMAN_GATE_READY`, `RLS_TEST_FAIL`, or `GATED_RESERVED` MUST NOT become `ACCEPTED` or `APPLIED` merely because it appears in the registry.

## Global dispatch gate

R64 currently binds all of the following:

- `NO_FURTHER_AGENT_WORK=true`
- `auto_dispatch=false`
- `auto_accept=false`
- `can_trade=false`
- `capital_permission=DENY`
- `deploy=DENY`
- external messages denied without exact separate human authorization
- `self_application=false`

Therefore V1 may observe and route pending work but MUST render dispatch as blocked. It MUST NOT issue a work order, resume a pending agent, or reinterpret a pending registry state as execution authority.

A later explicit bounded human gate may authorize a specific effect, but that authorization must be represented as a new source fact. It must not be inferred by this projection.

## Inputs

`agent_control_sources.current.v1.json` is a bounded non-authority provider snapshot. It carries:

1. exact R64 pointer identity and raw SHA;
2. current effect ceiling;
3. current Return Registry stable Drive identity and raw SHA;
4. normalized current registry slot observations;
5. immutable projection boundaries.

The source snapshot is evidence/provenance only. Committing it to GitHub does not move authority from Drive to GitHub.

## Slot projection

Each registry slot is projected with:

- slot ID;
- project hint when source evidence permits one;
- reported registry state;
- operational classification;
- work order;
- reported next gate/action;
- `dispatch_authorized=false`;
- global dispatch blocker;
- `semantic_authority=NONE_FROM_REGISTRY`;
- `apply_authority=NONE_FROM_REGISTRY`;
- rerun prohibition;
- explicit TradingOS do-not-touch marker when applicable.

## Pending dispatch queue

`PENDING_EXECUTION`, `PENDING_OBSERVATION_WINDOW`, and `GATED_RESERVED` are shown in a blocked dispatch queue.

This queue is informational. It is not a dispatch queue in the effectful sense.

## Operator attention

The Cockpit may show at most three attention items.

V1 uses deterministic priority:

1. failed execution / failed acceptance diagnostics;
2. explicit human gate ready;
3. Return Plane migration decision;
4. other explicit Robert decision;
5. other explicit next gate;
6. pending execution;
7. pending observation;
8. gated reserve.

One item per project is retained so a single failing project cannot consume the whole operator surface.

TradingOS is excluded from attention generation and remains `DO_NOT_TOUCH`.

Attention ranking is a projection heuristic, not a human decision and not effect authority.

## Fail-closed invariants

Validation MUST fail when:

- R64 pointer identity, SHA, activation, manifest, or provider readback drifts;
- `NO_FURTHER_AGENT_WORK` is not true;
- auto-dispatch or auto-accept becomes enabled in the source without a new contract;
- trading/capital/deploy/self-application ceilings drift;
- Return Registry stable identity/schema drifts;
- registry permits source mutation or completed-work reruns;
- registry transport/semantic boundaries are removed;
- operator attention exceeds three.

## UI

Control Center / Work Cockpit renders Agent Control as a dedicated operator section:

- global dispatch state;
- max-three attention queue;
- blocked pending queue;
- complete slot table.

The existing owner/project views remain separate. Agent Control does not collapse project ownership into agent-slot identity.
