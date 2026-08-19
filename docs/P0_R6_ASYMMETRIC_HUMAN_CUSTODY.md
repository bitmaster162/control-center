# P0 TORTURE / REPLAY R6 — Asymmetric Human Custody

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

R6 removes the R5 shared-secret verifier-key property from the preferred custody path. It consumes an externally verified asymmetric authenticator assertion and independently verifies semantic, temporal, key-epoch and replay bindings around that assertion.

Exact cryptographic claim: `EXTERNAL_ASYMMETRIC_SIGNATURE_VERIFIER_ASSERTION`.
Exact non-claim: `local_signature_math_verified=false`.

`control_center.shadow_human_credential_registry_snapshot.v1` binds subject/device/provider, credential/public-key digests, ED25519/ES256 algorithm, key epoch, status, validity interval and optional authenticator sign counter. `control_center.shadow_human_nonce_epoch_registry_snapshot.v1` is cumulative and binds authority root, epoch window, prior epoch digest, used nonce digests and challenge ids. Both consume independently expected snapshot digests.

R6 rejects nonce reuse, challenge reuse, challenge outside the epoch, stale/substituted snapshots, revoked/expired/wrong-epoch keys, public-key transplant, wrong origin/RP, missing user verification and non-monotonic authenticator counters. It produces only no-write next registry candidates.

Successful verification emits `control_center.shadow_asymmetric_human_approval_verification.v1`. TradingOS binds that exact retained digest to the R4 reveal/history as `bitevo.shadow_asymmetric_reveal_closure.v1`. Control Center renders only `NON_AUTHORITY_ASYMMETRIC_REVEAL_PROJECTION`.

Evidence ceiling: R6 does not prove local mathematical signature verification, biometric/legal identity, physical human presence, durable global nonce enforcement, durable credential-registry mutation, current truth or execution permission. The external asymmetric verifier remains part of the trusted computing base.

Observed R6 code/workflow head `9696f7983f17d12613c262b71488dddae5592dff` produced run `32301098137`; later documentation-only head `7edaec04287fe91e1fbc18f26d5fb8c818eb0d7e` produced run `32301233711`. Both exposed `steps=null` and no job logs. Classification: `CI_BLOCKED_PRE_JOB / NOT_A_CODE_TEST_FAILURE`. Subsequent documentation-only commits preserve identical R6 code semantics. No R6 CI PASS is claimed and no manual rerun was requested.

Fixed ceiling: `merge=false`, `deploy=false`, `runtime_activation=false`, `human_gate_write=false`, `credential_registry_write=false`, `nonce_registry_write=false`, `current_truth_apply=false`, `executor_dispatch=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
