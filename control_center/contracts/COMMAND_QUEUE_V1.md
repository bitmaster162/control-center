# Control Center Command Queue V1

## Purpose

Provide one deterministic, non-authority routing and priority projection over Agent Control, Work Order Lifecycle, Decision / Effect Gate Ledger, and Effect Execution / Readback Plane.

The command queue answers only:
- what is ripe for Robert now;
- what remains in Control Center semantic review;
- what belongs to a project owner;
- what is blocked and must not be escalated as actionable.

It never grants dispatch, semantic acceptance, effect authorization, execution authorization, apply, merge, deploy, trading, capital, or external-message authority.

## Source chain

`AGENT_CONTROL -> WORK_ORDER_LIFECYCLE -> DECISION_EFFECT_LEDGER -> EFFECT_READBACK -> COMMAND_QUEUE`

All inputs are projections/observations. R64 Drive roots remain canonical authority.

## Queue classes

1. `HUMAN_NOW`
   - only an already-open, `human_ripe=true` decision may enter;
   - max 3 items;
   - a queue item is not a human decision and does not authorize an effect.

2. `CONTROL_CENTER_QUEUE`
   - open Control Center semantic adjudications;
   - operator-attention bindings rank ahead of ordinary semantic review;
   - no self-approval: the queue may route but not fill `decision_outcome`.

3. `PROJECT_OWNER_QUEUE`
   - owner-only items, including TradingOS;
   - Control Center may display/rout them but may not adjudicate or apply them.

4. `BLOCKED_QUEUE`
   - dispatch-authority exceptions that are not ripe;
   - remain blocked under R64 `NO_FURTHER_AGENT_WORK`;
   - not promoted into `HUMAN_NOW` merely because they name ROBERT as authority owner.

## Deterministic priority

Priority is routing priority, not execution priority:
- `HUMAN_NOW`: 1000 + deterministic rank bonus;
- Control Center items referenced by compressed operator attention: 900-series;
- other Control Center semantic items: 500-series;
- project-owner items: 300-series;
- blocked items: 100-series.

Tie-break: lexical `work_order` ascending.

## Effect/readback binding

For any command bound to an effect candidate, surface the effect stage exactly. Current effect authorization, execution authorization, execution receipt, readback receipt, and closure remain independent facts.

`ACCEPT != AUTHORIZE != EXECUTE != RECEIPT != READBACK != CLOSE`

## Fail-closed invariants

- no queue item may set `effect_authorized=true` or `execution_authorized=true`;
- no queue item may invent execution/readback receipts;
- no blocked decision may enter `HUMAN_NOW`;
- TradingOS must remain project-owner-only / DO NOT TOUCH;
- `HUMAN_NOW` must equal the ledger's open human-ripe set, capped at 3;
- every command must bind to an existing decision object;
- every effect binding must reference an existing effect candidate;
- duplicate work orders are forbidden;
- no command may be simultaneously actionable and blocked;
- queue generation is deterministic and non-authority.
