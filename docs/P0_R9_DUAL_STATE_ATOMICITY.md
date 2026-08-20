# P0 TORTURE / REPLAY R9 — Dual-State Atomicity + Lease Epoch Lineage

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R9 hardens the next boundary after R8.1. R8.1 binds receipt identity and authority root, but it does not prove that Human Gate state and the paired receipt index move together, nor that lease renewal/reacquisition forms a monotonic lineage.

R9 adds:

- `control_center.shadow_human_gate_lease_epoch_lineage.v1`
- `control_center.shadow_human_gate_dual_state_commit_candidate.v1`
- `control_center.shadow_human_gate_dual_state_readback_snapshot.v1`
- `control_center.shadow_human_gate_dual_state_atomicity_verification.v1`
- `control_center.shadow_dual_state_atomicity_projection.v1`

## Lease lineage

A transition must bind the exact previous/current lease digests and retained authority root. The current lease must reference the previous lease digest, advance `lease_epoch` by exactly one, strictly increase the fencing token and use a new lease id. `RENEW` keeps the same writer; `REACQUIRE` may change writer identity.

The explicit ABA guard is:

`LEASE_ID_CHANGES_AND_EPOCH_TOKEN_MONOTONIC`.

A stale renewal, skipped/replayed epoch, non-increasing fencing token, reused lease id or broken parent digest fails closed.

## Dual-state write set

The R9 commit candidate binds one transaction precondition and one two-record write set:

`Human Gate state + paired receipt index`

under:

`ONE_BACKEND_TRANSACTION_TWO_LOGICAL_RECORDS`.

Both logical generations must advance exactly `N -> N+1`. The candidate also binds exact R8.1 recovery, exact lease lineage, case/challenge, commit/idempotency identity, retained authority root and backend transaction id.

P0 does not execute this transaction.

## Crash consistency

R9 readback accepts only two coherent states:

- both records still at the prior pair;
- both records at the next pair.

Any mixed state such as `new Human Gate + old receipt index` or `old Human Gate + new receipt index` is rejected as `dual_state_split_or_unknown_readback_detected`.

`BEFORE_ATOMIC_DUAL_WRITE` requires the prior pair and a fresh compare before any new candidate.

`AFTER_ATOMIC_DUAL_WRITE_BEFORE_ACK` requires the next pair and allows only dedup/reconciliation, never a second write.

## Evidence ceiling

`dual-state protocol verified != durable backend transaction`

`coherent readback candidate != live read-after-write proof`

`lease epoch lineage verified != live lease registry`

R9 remains `PROTOCOL_VERIFIED_NO_DURABLE_BACKEND`, with no Human Gate write, lease/receipt registry write, backend write, current-truth promotion or execution authority.

Fixed ceiling: `merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `lease_registry_write=false`, `commit_receipt_registry_write=false`, `backend_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
