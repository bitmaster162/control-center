# Provider Snapshot Freshness Gate V1

## Purpose

Prevent a locally consistent Control Center projection from being treated as current when its authority-critical provider snapshot may be older than the factual Google Drive stable roots.

This gate is read-only and non-authoritative. It grants no dispatch, acceptance, apply, execution, deploy, trading, capital, external-message, root-write, registry-write, or self-application authority.

## Scope classes

### AUTHORITY_CRITICAL

The five R64 stable-root objects whose exact provider bytes define the current canonical anchor:

- `CURRENT_STATE.json`
- `ROLE_INDEX.json`
- `ROLE_VIEWS.json`
- `MANIFEST.json`
- `CURRENT_POINTER.json`

A freshness receipt MUST bind each object to:

- Drive file ID;
- provider `modified_time`;
- exact byte length;
- SHA-256 computed from provider-returned bytes.

The receipt MUST prove exact equality with `provider_snapshot.current.v1.json` for all snapshot-declared canonical hashes and IDs available there. `CURRENT_POINTER.json` MUST be the latest-modified stable root, preserving the pointer-last reseal protocol.

### INFORMATIONAL_SELF_REFERENTIAL

The Control Center GitHub lane inside `provider_snapshot.current.v1.json` is informational only. A committed snapshot cannot contain its own eventual commit SHA without self-reference. Therefore the snapshot's `github_lanes.control_center.head_sha` MUST NOT be used as an authority-critical freshness condition.

A freshness receipt may record the pre-commit live PR/head observation, but it MUST mark that observation `authority_relevant=false` and `self_reference_exempt=true`.

## Freshness semantics

Freshness is `FRESH_AT_CAPTURE`, never continuous freshness.

- `continuous_freshness=false` is mandatory.
- The current evidence validity window is 21,600 seconds (6 hours).
- CI may validate an evidence receipt only while `now - observed_at <= max_age_seconds`.
- After expiry, CI MUST fail closed with `freshness_evidence_stale`; a new read-only provider capture is required.
- Evidence more than 300 seconds in the future MUST fail.

The six-hour window is a bounded operational lease for provider evidence. It is not proof that no provider change occurred within the window. Exact live provider freshness beyond the capture instant requires another provider readback.

## Current capture result

The V1 baseline capture was performed at `2026-08-12T04:59:00+07:00` using direct Google Drive reads. All five provider byte hashes and sizes matched the R64 resealed snapshot. Provider metadata also preserved pointer-last ordering.

## Fail-closed conditions

The validator MUST reject at least:

- missing or extra authority-critical root identity;
- Drive ID mismatch for snapshot-bound roots;
- SHA mismatch;
- byte-length mismatch;
- manifest SHA mismatch;
- `CURRENT_POINTER` not latest-modified among stable roots;
- stale or future-dated evidence;
- evidence claiming continuous freshness;
- informational self-referential GitHub state promoted to authority-critical status;
- any authority grant embedded in the freshness evidence.

## CI boundary

GitHub Actions has no assumed access to the user's private Drive provider. CI validates the captured provider evidence and its bounded age; it does not independently query Drive. The controller must refresh the evidence by read-only provider calls whenever the lease expires or before relying on the snapshot after suspected external mutation.
