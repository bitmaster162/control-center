# P0 TORTURE / REPLAY R8.1 — Paired Receipt Identity + Authority-Root Anchor

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R8.1 hardens the two explicit R8 v1 gaps without enabling any writer.

## 1. First-class receipt identity

R8 v1 stores commit ids and idempotency keys as parallel sequences. R8.1 adds:

`control_center.shadow_human_gate_commit_receipt_index_snapshot.v2`

Each entry is one first-class object:

`(commit_id, idempotency_key_sha256, receipt_reference_sha256)`

The v2 index must preserve the exact positional commit/idempotency pairing from the legacy v1 index and binds one receipt-candidate reference to that exact pair. Crossed/swapped pairs, duplicate commit ids, duplicate idempotency keys and duplicate receipt references fail closed.

`receipt_reference_kind=EXPECTED_RECEIPT_CANDIDATE_SHA256_SHADOW_ONLY` is deliberate: this remains a protocol/evidence object, not proof that a durable backend receipt was issued.

## 2. Retained authority-root anchor

R8.1 adds:

`control_center.shadow_human_gate_writer_authority_anchor.v1`

The anchor binds one independently expected `authority_root_sha256` to the exact current writer lease, legacy receipt index and paired v2 receipt index. It carries `retained_reference_required=true` and no write/apply/effect authority.

The hardened recovery wrapper:

`control_center.shadow_human_gate_crash_recovery_verification.v2`

requires the exact retained legacy recovery digest, paired-index digest, authority-anchor digest and authority-root digest. If the legacy recovery says the receipt is indexed, the exact `(commit,idempotency,receipt_reference)` tuple must exist once. If it says the receipt is not indexed, that target commit/idempotency identity must be absent.

The resulting status is:

`FENCING_AND_CRASH_RECOVERY_HARDENED_SHADOW_ONLY`

with `paired_receipt_identity_verified=true` and `authority_root_anchor_consumed=true`.

TradingOS consumes the same independently retained authority-root/anchor references in `bitevo.shadow_writer_fencing_recovery_closure.v2`. Control Center may render that closure only through `control_center.shadow_writer_recovery_projection.v2` / `NON_AUTHORITY_WRITER_RECOVERY_PROJECTION_V2`.

## Adversarial coverage

R8.1 rejects swapped parallel pairings, wrong receipt references, wrong retained anchor digests, rehashed authority-root substitution, cross-case/cross-plane substitution, missing pair/anchor guards, HOLD-to-PASS widening and durable-commit overclaims.

## Evidence ceiling

R8.1 closes the two R8 v1 representation/trust-binding gaps at contract level. It still does **not** prove a live lease store, a real single-writer backend, an issued durable receipt, durable receipt-index persistence, crash-safe fsync/transaction semantics, live read-after-write, current truth or execution permission.

`paired receipt identity verified != durable receipt issued`

`authority-root anchor consumed != live authority backend proven`

Fixed ceiling: `merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `lease_registry_write=false`, `commit_receipt_registry_write=false`, `backend_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
