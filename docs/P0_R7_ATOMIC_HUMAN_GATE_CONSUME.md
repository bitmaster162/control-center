# P0 TORTURE / REPLAY R7 — Atomic Human Gate Consume / TOCTOU

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R7 addresses the gap left by R6.1: a challenge/nonce can be proven unused against a snapshot, but without an atomic consume protocol there is a time-of-check/time-of-use race between `unused` and any future durable consume.

## Protocol

R7 introduces a no-write compare-and-swap protocol:

```text
R6.1 asymmetric approval v2
  -> independently expected approval digest
  -> independently expected Human Gate state digest
  -> PREPARE
  -> fresh CURRENT STATE compare
  -> CAS MATCH
  -> COMMIT CANDIDATE
  -> independently expected commit-candidate digest
  -> atomic consume verification
```

Schemas:

- `control_center.shadow_human_gate_state_snapshot.v1`
- `control_center.shadow_human_gate_consume_prepare.v1`
- `control_center.shadow_human_gate_consume_compare.v1`
- `control_center.shadow_human_gate_consume_commit_candidate.v1`
- `control_center.shadow_human_gate_atomic_consume_verification.v1`
- `control_center.shadow_human_gate_consume_projection.v1`

The state snapshot binds generation, credential-registry digest, nonce-registry digest, consumed challenge ids, consumed nonce digests and previous state digest.

`PREPARE` requires the exact R6.1 approval digest and exact prior state digest. It rejects already-consumed challenge/nonce subjects and binds the R6.1 next credential/nonce registry candidates.

`COMPARE` requires a fresh current state digest and exact equality with the prepared state/generation/registry heads. Any intervening state change fails closed.

`COMMIT CANDIDATE` advances generation by exactly one and constructs the next Human Gate state candidate. It carries an explicit CAS precondition on the prior state digest.

P0 does not execute that CAS. The exact result is:

`PROTOCOL_VERIFIED_NO_DURABLE_COMMIT`

and:

`CANDIDATE_ONLY_NOT_DURABLY_ENFORCED`.

## Adversarial coverage

R7 tests:

- already consumed challenge;
- state drift after prepare;
- two prepares from the same state where only the first hypothetical CAS transition can remain current;
- stale generation/current-state substitution;
- wrong independently retained commit-candidate digest;
- durable-commit overclaim after local rehash;
- cross-case/approval mismatch when TradingOS binds the protocol back to R6.1.

TradingOS binds the exact R6.1 reveal closure and exact R7 atomic verification as `bitevo.shadow_human_gate_consume_closure.v1`. Control Center renders it only as `NON_AUTHORITY_ATOMIC_CONSUME_PROJECTION`.

## Evidence ceiling

R7 verifies the compare-and-swap protocol and the exact state transition candidate. It does **not** prove that a durable atomic writer executed the transition.

Therefore:

```text
CAS protocol verified
!= durable commit
!= durable global single-use enforcement
!= current truth
!= execution permission
```

A future write-enabled Human Gate would need a real single-writer/CAS store, an independently verified durable commit receipt, failure recovery and stale-writer fencing before this boundary can be promoted.

Fixed ceiling:

`merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
