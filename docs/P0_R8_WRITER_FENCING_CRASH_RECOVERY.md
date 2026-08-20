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

The durable-commit receipt object is deliberately a **candidate shape only**. It specifies the fields a future durable backend receipt must bind: exact attempt, commit/idempotency identity, writer lease, fencing token, state transition, backend transaction digest and acceptance time. It always carries `receipt_issued=false`, `write_performed=false`, `durable_commit_proven=false`, `live_backend_observed=false`.

## Fencing and crash recovery

A higher fresh fencing token makes the old writer stale. A different lease/writer using the same fencing token is rejected as split-brain evidence. R8 models `BEFORE_WRITE`, `AFTER_WRITE_BEFORE_RECEIPT` and `AFTER_RECEIPT_BEFORE_ACK`; blind retry is always forbidden, and any retry candidate requires a fresh compare/CAS.

TradingOS binds the exact R7 Human Gate consume closure and exact R8 recovery verification as `bitevo.shadow_writer_fencing_recovery_closure.v1`. Control Center may render it only as `NON_AUTHORITY_WRITER_RECOVERY_PROJECTION`. End-to-end remains `HOLD / WAIT`.

## CI evidence

The R8 Control Center code/workflow head `c4ae867709c90a7f7d1f709c94acb39785cf2619` produced P0 Unified Shadow Projection run `32306457762`, which completed FAILURE before executable steps were exposed; `offline-shadow-projection` returned `steps=null` and no logs. Classification: `CI_BLOCKED_PRE_JOB / NOT_A_CODE_TEST_FAILURE`. The later documentation-only head does not change R8 code semantics. No R8 Control Center CI PASS is claimed and no manual rerun was requested.

## Evidence ceiling

R8 verifies protocol semantics only. It does not prove a live single-writer backend, durable lease/receipt registries, an actual backend write, an issued durable receipt, crash-safe fsync/transaction semantics, live read-after-write, current truth or execution permission.

R8 v1 also leaves two explicit hardening gaps:

1. receipt index commit ids and idempotency keys are parallel sequences rather than one independently bound first-class receipt-entry tuple;
2. lease/index authority-root digests are not yet promoted into the TradingOS closure as a separate retained cross-plane trust anchor.

Therefore R8 v1 is `PASS WITH CONDITIONS`, not a production-qualified durability boundary.

Fixed ceiling: `merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `lease_registry_write=false`, `commit_receipt_registry_write=false`, `backend_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
