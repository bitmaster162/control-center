# Provider Freshness Refresh Controller V1

## Purpose

Provide a deterministic, fail-closed controller for refreshing `provider_freshness_evidence.current.v1.json` after a new read-only provider capture.

The controller is a non-authority engineering component. It does not query Drive by itself, does not mutate provider state, and never grants dispatch, semantic acceptance, apply, execution, deploy, trading, capital, external-message, root-write, registry-write, merge, or self-application authority.

## Inputs

1. Current `provider_snapshot.current.v1.json`.
2. Current `provider_freshness_evidence.current.v1.json`.
3. Applied `canonical_reseal_execution_receipt.generated.v1.json`.
4. A new raw capture with schema `control_center.provider_refresh_capture.v1` produced only by read-only provider calls.
5. Current wall-clock time.

A raw capture contains observation facts only:

- `observed_at`;
- provider identity;
- exact five-root set;
- Drive file ID;
- provider `modified_time`;
- byte length;
- SHA-256 computed from provider-returned bytes;
- optional pre-capture live PR head, explicitly informational/self-referential.

It must not contain an apply/authorization decision.

## Deterministic verdicts

### `REFRESH_EVIDENCE_ONLY_ALLOWED`

All five authority-critical roots exactly match the current snapshot and reseal receipt, pointer-last ordering holds, capture is newer than current evidence, and capture is not future-dated beyond tolerance.

This verdict permits exactly one engineering projection update:

`control_center/data/provider_freshness_evidence.current.v1.json`

It does **not** permit changing the provider snapshot, Drive roots, Return Registry, runtime, routing, canonical state, PR merge state, or any effect authority.

A fresh PR/head/base/status verification is still required immediately before that GitHub evidence-file write.

### `NO_REFRESH_REQUIRED_CURRENT_LEASE_FRESH`

The supplied capture is the same capture as current evidence (or not newer), all authority-critical facts are exact, and the current evidence lease remains valid. No write is needed.

### `HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED`

Current evidence is expired and the supplied capture does not provide a strictly newer exact observation. No write is allowed.

### `HOLD_PROVIDER_DRIFT_DETECTED`

Any authority-critical Drive ID, SHA-256, byte length, root identity set, reseal binding, or pointer-last ordering differs from current expected truth.

The controller returns diagnostic differences only. It must not rewrite the snapshot, roots, manifest, pointer, registry, or evidence to normalize the mismatch.

### `HOLD_INVALID_OR_INCOMPLETE_CAPTURE`

The raw capture is malformed, incomplete, future-dated beyond tolerance, uses the wrong provider/capture mode, embeds authority grants, or otherwise fails the capture contract.

## Monotonic refresh rule

A replacement freshness evidence receipt must have `observed_at` strictly greater than the current evidence observation. Equal timestamps are idempotent/no-refresh only when the root facts are identical. Older captures never extend the lease.

## Candidate evidence

For `REFRESH_EVIDENCE_ONLY_ALLOWED`, the controller may deterministically emit a candidate `control_center.provider_freshness_evidence.v1` object from the raw capture.

The candidate must:

- bind to the exact current provider-snapshot Git blob SHA;
- preserve `FRESH_AT_CAPTURE` and `continuous_freshness=false`;
- preserve the 21,600-second lease and 300-second future-skew tolerance;
- preserve exact five-root facts from the raw capture;
- mark Control Center GitHub head as informational/self-referential;
- contain all safety booleans false and `capital_permission=DENY`.

The controller itself never writes the candidate.

## Fail-closed invariant

`provider drift != snapshot repair`

`provider drift != canonical mutation`

`provider drift != evidence refresh`

A mismatch produces HOLD until separately adjudicated from provider evidence.
