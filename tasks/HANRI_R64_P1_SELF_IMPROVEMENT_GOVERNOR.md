# HANRI-R64-P1 — bounded self-improvement governor shadow and install gate

## Runtime identity

- Current live runtime: HANRI R28 at `%LOCALAPPDATA%\ControlCenterHANRIR28\`.
- Candidate: R64-P1 governor above R28, Control Center and ContinuityOS.
- The candidate is not a replacement until an explicit install/cutover approval exists.
- Authority remains R63. No new control generation is created.

## Git and state baseline

Before implementation:

1. resolve candidate repository root and verify clean baseline HEAD/tree;
2. capture R28 executable/script hashes, processes, scheduled tasks, state/checkpoint hashes and current interval;
3. create a read-only state snapshot and recovery receipt;
4. identify all writers and external consumers;
5. stop if baseline or writer ownership is ambiguous.

## Shadow capabilities

- observe registered systems and source freshness;
- detect drift, pointer/role-view inconsistency, recurring delivery failures and decision recurrence;
- create bounded improvement candidates with evidence class and action class;
- test candidates only in disposable copies/shadow state;
- compare baseline and candidate with deterministic metrics;
- learn from Robert's ACCEPT/REJECT/REVISE/HOLD receipts;
- emit proposals and install-gate packets.

## First regression targets

1. decision-intake loop: preserve `pending_human_decisions=0` and no recurrence;
2. pointer/role-view consistency;
3. return-delivery completeness and broker dedup by `(slot, work_order_id, sha256)`.

## Prohibitions

- no self-application;
- no direct mutation of R28 state, current roots or permanent registry;
- no service/task replacement;
- no production deploy;
- no automatic credential rotation;
- no invented probabilities or improvement scores;
- no control-generation creation.

## Cadence change

The 1-minute → 5-minute R28 interval change is a separate reversible host action. It requires an execution receipt showing old/new schedule, next-run time, missed-run policy and rollback command. A script's existence is not execution proof.

## Install gate

Return `INSTALL_GATE_READY` only after:

- shadow tests pass;
- zero live writes are proven;
- rollback/recovery drill passes;
- resource usage is bounded;
- operator-visible diff and risk analysis exist;
- R28 remains available and unchanged;
- explicit Robert approval is still required for install/cutover.

## Terminal states

- `SHADOW_PASS_INSTALL_GATE_READY`
- `REVISE`
- `BLOCKED_BASELINE_OR_AUTHORITY_CONFLICT`

Return strict ZIP/SHA/READY-last through the broker. `can_trade=false`; `capital_permission=DENY`; `self_application=false`.
