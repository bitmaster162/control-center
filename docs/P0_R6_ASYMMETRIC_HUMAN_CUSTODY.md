# P0 TORTURE / REPLAY R6 — Asymmetric Human Custody

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R6 removes the R5 shared-secret verifier-key property from the preferred custody path. It does not claim that Control Center itself performs WebAuthn or public-key signature mathematics.

## Trust split

R6 consumes an externally verified asymmetric authenticator assertion and independently verifies all semantic, temporal, key-epoch and replay bindings around that assertion.

Exact cryptographic claim:

`EXTERNAL_ASYMMETRIC_SIGNATURE_VERIFIER_ASSERTION`

Exact non-claim:

`local_signature_math_verified=false`

The external asymmetric verifier remains inside the trusted computing base until a production WebAuthn/public-key verifier is implemented and independently validated.

## Credential registry

`control_center.shadow_human_credential_registry_snapshot.v1` binds human subject, device, custody provider, credential/public-key digests, ED25519/ES256 algorithm, key epoch, ACTIVE/REVOKED/RETIRED status, validity interval and optional authenticator sign counter. The expected registry digest is independently supplied.

## Nonce epoch registry

`control_center.shadow_human_nonce_epoch_registry_snapshot.v1` is cumulative and binds an independently expected digest, authority root, epoch window, previous epoch digest, used nonce digests and challenge ids. R6 rejects nonce reuse, challenge reuse, challenges outside the epoch, stale/substituted snapshots, revoked/expired keys and non-monotonic authenticator counters.

Only next registry candidates are produced; P0 performs no durable registry write.

## Authenticator assertion

`control_center.shadow_asymmetric_authenticator_assertion.v1` binds the exact R5 challenge plus credential/public-key digests, algorithm/key epoch, signature digest, verifier identity, origin/RP id, reveal choice/time, externally verified signature status, authenticator user-presence/user-verification flags and sign-counter transition.

`user_verified=true` is an authenticator property, not legal identity or proof of a specific physical person's presence.

Successful verification emits `control_center.shadow_asymmetric_human_approval_verification.v1`. TradingOS binds that exact retained digest to the R4 reveal/history as `bitevo.shadow_asymmetric_reveal_closure.v1`. Control Center renders it only as `NON_AUTHORITY_ASYMMETRIC_REVEAL_PROJECTION`.

## Evidence ceiling

R6 proves, relative to independently retained registry/approval digests: exact case/packet/Twin/reveal binding, credential/key-epoch policy as asserted by the external verifier, origin/RP policy, nonce/challenge single-use candidate state, credential revocation/validity/counter checks and no-effect boundaries.

R6 does not prove local mathematical signature verification, biometric/legal identity, physical human presence, durable global nonce enforcement, durable credential-registry mutation, current truth or execution permission.

Fresh R6 code/workflow head `9696f7983f17d12613c262b71488dddae5592dff` produced P0 Unified Shadow Projection run `32301098137`, which completed before executable steps were exposed (`steps=null`, no job logs). Classification: `CI_BLOCKED_PRE_JOB / NOT_A_CODE_TEST_FAILURE`. No R6 CI PASS is claimed and no manual rerun was requested.

Fixed ceiling: `merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
