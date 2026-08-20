# Provider Drift Hold Diagnostic Projection V1

## Purpose

Expose a bounded, read-only operator diagnostic when the Provider Freshness Refresh Controller returns `HOLD_PROVIDER_DRIFT_DETECTED`.

This projection is not authority and cannot repair or rewrite provider state. It exists only so the Control Center Cockpit can display why a freshness refresh was held.

## Current-state semantics

The committed current artifact path is:

`control_center/data/provider_refresh_controller_status.current.v1.json`

The absence of a drift HOLD does **not** prove that provider drift is absent. The neutral state is therefore:

`NO_HOLD_DIAGNOSTIC_RECORDED`

with `absence_does_not_prove_no_drift=true`.

Only an explicit Refresh Controller verdict `HOLD_PROVIDER_DRIFT_DETECTED` may produce:

- `hold_active=true`;
- `operator_state=DRIFT_HOLD`;
- a bounded mismatch list;
- the exact controller error codes that caused the HOLD.

`HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED` is lease expiry, not provider drift, and remains an `EXPIRED` presentation concern. `HOLD_INVALID_OR_INCOMPLETE_CAPTURE` is an invalid-capture condition and must not be mislabeled as provider drift.

## Diagnostic content

A drift diagnostic may include only bounded comparison fields required to explain the HOLD:

- stable-root file name;
- mismatched field (`drive_file_id`, `sha256`, `bytes`, `modified_time`, or pointer ordering);
- expected value;
- observed value;
- controller error code;
- capture `observed_at` and provider label.

It does not carry provider credentials, raw file payloads, external messages, secrets, remediation commands, or execution instructions.

## Safety boundary

The artifact MUST assert all of the following:

- `diagnostic_grants_authority=false`;
- `refresh_authorized=false` while HOLD is active;
- `root_write_authorized=false`;
- `registry_write_authorized=false`;
- `runtime_mutation_authorized=false`;
- `routing_mutation_authorized=false`;
- `dispatch_authorized=false`;
- `apply_authorized=false`;
- `execution_authorized=false`;
- `deploy_authorized=false`;
- `external_message_authorized=false`;
- `can_trade=false`;
- `capital_permission=DENY`;
- `self_application=false`.

No diagnostic state may authorize an automatic fix. A provider mismatch requires a separately governed investigation and, if any write becomes necessary, a separate exact human effect gate.

## Cockpit mapping

`provider_lease.js` may map only:

`HOLD_PROVIDER_DRIFT_DETECTED -> DRIFT_HOLD`

An invalid/unknown HOLD artifact must fail visibly instead of being displayed as a factual drift claim.

## CI invariants

CI rejects at least:

- neutral artifact claiming provider health or no drift;
- drift state without exact `HOLD_PROVIDER_DRIFT_DETECTED`;
- drift HOLD without bounded mismatch evidence;
- mismatch entries outside the allowed field set;
- embedded remediation/auto-fix authority;
- write/deploy/trading/capital authority leakage;
- invalid-capture HOLD mislabeled as drift;
- expired-recapture HOLD mislabeled as drift;
- operator state inconsistent with the controller verdict.
