# P0 TORTURE / REPLAY R8 — Writer Lease / Fencing / Crash Recovery

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R8 hardens the gap left by R7. R7 proves a compare-and-swap transition candidate, but it does not model a writer lease, fencing token, crash points, receipt deduplication or recovery after an ambiguous write.

## Protocol surface

New schemas:

- `control_center.shadow_human_gate_writer_lease_snapshot.v1`
- `control_center.shadow_human_gate_commit_receipt_index_snapshot.v1`
- `control_center.shadow_human_gate_fenced_commit_attempt.v1`
- `control_center.shadow_human_gate_durable_commit_receipt_candidate.v1`
- `control_center.shadow_human_gate_crash_recovery_verification.v1`
- `control_center.shadow_writer_recovery_projection.v1`

A writer lease binds one writer id, one lease id, one lease epoch, one monotonic fencing token, the exact prior Human Gate state digest/generation and a bounded issue/expiry window. The lease is an externally retained shadow snapshot; R8 does not create or persist a lease.

A fenced commit attempt consumes the exact R7 atomic-consume verification, exact writer-lease digest and exact receipt-index digest. It rejects replayed commit ids/idempotency keys and requires the attempt to occur inside the lease window.

The durable-commit receipt object is deliberately a **candidate shape only**. It specifies the fields a future durable backend receipt must bind: exact attempt, commit/idempotency identity, writer lease, fencing token, state transition, backend transaction digest and acceptance time. It always carries:

- `receipt_issued=false`
- `write_performed=false`
- `durable_commit_proven=false`
- `live_backend_observed=false`

## Fencing and split brain

Recovery consumes a fresh current lease digest. A higher current fencing token makes the old writer stale. A different lease/writer using the **same** fencing token is rejected as split-brain evidence.

This gives the protocol rule:

```text
old token < current token  -> old writer fenced
same token + different lease/writer -> REJECT split brain
current token + same lease + live window -> current writer candidate
```

No live lease backend is claimed.

## Crash recovery

R8 models three crash points:

1. `BEFORE_WRITE`
   - readback must still equal the prior state;
   - no receipt identity may be indexed;
   - any retry requires a fresh compare/CAS; blind retry is forbidden.

2. `AFTER_WRITE_BEFORE_RECEIPT`
   - readback shows the next state but no receipt is indexed;
   - status becomes `WRITE_OBSERVED_RECEIPT_ABSENT_HOLD`;
   - retry is forbidden until external backend reconciliation.

3. `AFTER_RECEIPT_BEFORE_ACK`
   - readback shows the next state and the commit/idempotency identity is already indexed;
   - recovery is dedup/ack only;
   - a second commit is forbidden.

The receipt index is also a no-write snapshot. Partial identity (commit id without an idempotency key or vice versa) is rejected.

## TradingOS binding

TradingOS binds the exact R7 Human Gate consume closure and exact R8 recovery verification as:

`bitevo.shadow_writer_fencing_recovery_closure.v1`

Control Center may render that closure only as:

`NON_AUTHORITY_WRITER_RECOVERY_PROJECTION`

The end-to-end result remains `HOLD / WAIT`.

## Evidence ceiling

R8 verifies lease/fencing/recovery semantics and exact candidate receipts. It does **not** prove:

- a live single-writer backend;
- a durable lease registry;
- a durable receipt registry;
- an actual backend write;
- an issued durable commit receipt;
- crash-safe fsync/transaction semantics;
- read-after-write from a live store;
- current truth;
- execution permission.

R8 v1 also leaves two explicit hardening gaps for the next pass:

1. the receipt index stores commit ids and idempotency keys as parallel sequences rather than one first-class paired receipt-entry object; membership is checked, but exact pair identity is not yet independently bound;
2. lease and receipt-index snapshots are independently hash-bound, but their authority root is not yet promoted into the cross-plane TradingOS closure as a separate retained trust anchor.

Therefore R8 v1 is `PASS WITH CONDITIONS`, not a production-qualified durability boundary.

```text
fencing protocol verified
!= live fenced writer
receipt candidate verified
!= durable receipt issued
crash recovery semantics verified
!= crash-safe production store
```

Fixed ceiling:

`merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `lease_registry_write=false`, `commit_receipt_registry_write=false`, `backend_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
