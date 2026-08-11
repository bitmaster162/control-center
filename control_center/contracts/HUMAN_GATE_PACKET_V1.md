# Human Gate Packet V1

## Purpose

`Human Gate Packet V1` is a deterministic, non-authority decision packet for items already present in Control Center `HUMAN_NOW`.

It compresses the evidence required for a human sovereign decision without changing authority, semantic state, apply state, execution state, or readback state.

## Source chain

A packet may be emitted only when the same decision/work-order identity is coherently bound across:

1. `control_center.command_queue.v1`
2. `control_center.work_order_lifecycle.v1`
3. `control_center.decision_effect_ledger.v1`
4. `control_center.effect_readback_plane.v1`
5. the common exact R64 authority anchor

The packet is a projection over those sources. It is not an authority source.

## Eligibility

A packet exists only for a command in `Command Queue V1 -> HUMAN_NOW` where:

- the matching Decision Ledger decision is `OPEN`;
- `human_ripe=true`;
- decision owner is `ROBERT`;
- decision class is `HUMAN_EFFECT_AUTHORIZATION`;
- the work-order is bound in Work Order Lifecycle;
- the effect candidate is bound in Effect/Readback Plane;
- all four sources bind to exact `R64 ACTIVE` and pointer SHA-256 `3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef`.

No blocked dispatch exception, Control Center semantic review, or project-owner review may be promoted into a Human Gate Packet.

## Packet fields

Each packet must contain:

- packet identity;
- exact command / decision / work-order / return identities;
- project, slot, gate and current lifecycle/effect stages;
- current semantic/apply/effect/execution/readback state;
- evidence bindings to the four source projections;
- exact allowed human responses;
- per-response consequences and non-consequences;
- bounded effect scope;
- executor binding state;
- execution authorization requirement;
- required execution receipt contract;
- required post-effect readback contract;
- explicit forbidden implications.

## Decision semantics

For the current effect-gate class:

### `AUTHORIZE_APPLY`

This response may grant bounded **effect authorization for the exact packet scope only**.

It does **not** by itself:

- select or bind an executor;
- grant execution authority;
- execute the effect;
- create an execution receipt;
- mark the work-order APPLIED;
- create readback evidence;
- close the lifecycle;
- authorize deploy, trading, capital use, external messaging, or any unrelated effect.

If no executor is already source-bound, executor binding remains a separate required control event.

### `HOLD`

This response grants no effect or execution authority. The gate remains unresolved/held and the current NOT_APPLIED state remains unchanged until a later explicit bounded decision.

### `REJECT_EFFECT`

This response denies the proposed effect for this packet. It does not revoke the already-grounded semantic ACCEPTED return; it keeps the effect unapplied unless a later separately-authorized successor proposal is created.

## Executor rule

The packet must never invent an executor. If upstream sources do not bind an executor, emit:

- `executor_binding.state = UNBOUND_REQUIRES_SEPARATE_BINDING`
- `executor_binding.executor = null`
- `execution_authorized = false`

A future executor binding is not itself permission to execute.

## Receipt rule

After any real effect execution:

1. an execution receipt is mandatory and must bind packet ID, decision ID, work-order, executor identity, exact effect scope, execution timestamp, result, and provider/object identifiers sufficient for readback;
2. a post-effect readback receipt is mandatory and must independently bind the execution receipt and prove resulting provider/current state;
3. closure is impossible until the readback receipt is verified.

Receipts are evidence only and never grant authority.

## Global invariants

- packet membership never grants authority;
- generic `go` / `го` / continuation language is not an effect authorization token;
- semantic ACCEPTED never implies APPLY;
- effect authorization never implies execution authorization;
- execution authorization never implies execution occurred;
- execution receipt never implies successful readback;
- no closure without verified post-effect readback;
- no self-approval or self-application;
- `can_trade=false`;
- `capital_permission=DENY`;
- `deploy=DENY`;
- no external message without exact separate SEND;
- TradingOS remains DO NOT TOUCH and cannot enter this packet class without its own owner authority chain.
