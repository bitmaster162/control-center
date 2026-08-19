# P0 TORTURE / REPLAY R6 — Asymmetric Human Custody

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R6 removes the R5 shared-secret verifier-key property from the preferred custody path. It does not claim that Control Center itself performs WebAuthn or public-key signature mathematics.

## Trust split

R6 consumes an externally verified asymmetric authenticator assertion and independently verifies all semantic, temporal, key-epoch and replay bindings around that assertion.

The exact cryptographic claim is:

`EXTERNAL_ASYMMETRIC_SIGNATURE_VERIFIER_ASSERTION`

The exact non-claim is:

`local_signature_math_verified=false`

Therefore R6 is stronger than the R5 HMAC custody path against verifier-secret sharing, but the external asymmetric verifier remains inside the trusted computing base until a production WebAuthn/public-key verifier is implemented and independently validated.

## Credential registry

`control_center.shadow_human_credential_registry_snapshot.v1` binds:

- human subject;
- device;
- custody provider;
- credential id digest;
- public-key digest;
- algorithm (`ED25519` or `ES256`);
- key epoch;
- ACTIVE / REVOKED / RETIRED status;
- validity interval;
- optional authenticator sign counter.

The expected registry digest is supplied independently. A revoked, expired, wrong-device, wrong-key, wrong-algorithm or wrong-epoch credential is rejected.

## Nonce epoch registry

`control_center.shadow_human_nonce_epoch_registry_snapshot.v1` is cumulative. It binds an externally expected registry digest, authority root, epoch number/window, previous epoch digest, all previously consumed nonce digests and challenge ids.

R6 rejects:

- nonce reuse;
- challenge-id reuse;
- challenges outside the active nonce epoch;
- stale or substituted registry snapshots;
- non-monotonic authenticator sign counters when the credential supports a counter.

Only next registry candidates are produced. No durable registry write is performed in P0.

## Authenticator assertion

`control_center.shadow_asymmetric_authenticator_assertion.v1` must bind the exact R5 challenge fields plus:

- credential/public-key digests;
- algorithm and key epoch;
- signature digest;
- expected verifier id/key id;
- origin and RP id;
- exact reveal choice/time;
- `signature_verified=true` from the external asymmetric verifier;
- authenticator `user_present=true` and `user_verified=true`;
- sign-counter transition when supported.

`user_verified=true` is an authenticator property, not legal identity or proof of a specific physical person's presence.

## Output

Successful verification emits:

`control_center.shadow_asymmetric_human_approval_verification.v1`

TradingOS may then bind that exact retained digest to the R4 reveal and domain history as:

`bitevo.shadow_asymmetric_reveal_closure.v1`

Control Center may render that closure only as:

`NON_AUTHORITY_ASYMMETRIC_REVEAL_PROJECTION`

## Evidence ceiling

R6 proves, relative to independently retained registry and approval digests:

- exact case/packet/Twin/reveal binding;
- asymmetric credential identity and key epoch as asserted by the external verifier;
- origin/RP policy binding;
- nonce/challenge single-use candidate state;
- credential revocation/validity/counter checks;
- no-effect boundary.

R6 does **not** prove:

- local mathematical signature verification inside Control Center;
- biometric/legal identity;
- physical human presence;
- durable global nonce enforcement;
- durable credential-registry mutation;
- current truth;
- execution permission.

Fixed ceiling:

`merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
