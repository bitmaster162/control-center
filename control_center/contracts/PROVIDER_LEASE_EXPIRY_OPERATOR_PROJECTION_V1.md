# Provider Lease Expiry Operator Projection V1

## Purpose

Expose the bounded freshness lease in the Control Center Cockpit without turning presentation state into authority.

This projection is read-only. It grants no dispatch, acceptance, apply, execution, root write, registry write, deploy, external-message, trading, capital, merge, or self-application authority.

## Inputs

Primary input:

- `control_center/data/provider_freshness_evidence.current.v1.json`

Optional hold input:

- a future controller diagnostic projection produced from `Provider Freshness Refresh Controller V1`.

Absence of an optional hold projection MUST NOT be interpreted as proof that provider drift is impossible. It only means no explicit controller HOLD diagnostic is currently supplied to the Cockpit.

## Lease clock

`expires_at = observed_at + max_age_seconds`

For the current evidence:

- observed_at: `2026-08-12T04:59:00+07:00`
- max_age_seconds: `21600`
- expires_at: `2026-08-12T10:59:00+07:00`

The Cockpit computes lease state from the viewer clock. This avoids committing a generated status that becomes false merely because time passes.

## Operator states

Exactly four operator-facing states are permitted:

### `FRESH`

`now < expires_at - 3600 seconds`

The capture remains inside its bounded lease with more than one hour remaining.

### `EXPIRING`

`expires_at - 3600 seconds <= now < expires_at`

The capture is still valid under the existing six-hour evidence lease, but a read-only recapture will soon be required.

The one-hour threshold is presentation policy only. It does not alter the six-hour authority-critical freshness contract.

### `EXPIRED`

`now >= expires_at`

The current freshness evidence may no longer be used by the current-truth CI until a strictly newer read-only provider capture is evaluated and, if exact, the evidence file is refreshed.

Expiry does not imply provider drift.

### `DRIFT_HOLD`

An explicit current refresh-controller HOLD diagnostic takes precedence over the clock states when the controller has detected authority-critical mismatch or invalid/incomplete provider capture requiring operator review.

`HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED` maps to `EXPIRED`, not `DRIFT_HOLD`.

Other explicit controller HOLD verdicts map to `DRIFT_HOLD` and must display the diagnostic reason. The Cockpit must never auto-repair snapshot/root/registry/runtime state from this condition.

## Presentation requirements

The Cockpit MUST display:

- operator state;
- `observed_at`;
- exact `expires_at`;
- remaining time when not expired;
- `max_age_seconds`;
- explicit note that freshness is `FRESH_AT_CAPTURE`, not continuous;
- explicit note that the panel is projection-only and does not refresh evidence by itself.

The browser may update the countdown/state as wall-clock time advances. It MUST NOT perform provider calls, GitHub writes, scheduler actions, or automatic evidence refresh.

## Fail-closed display behavior

Malformed or unavailable freshness evidence must render an error/unknown condition in the panel and must not be silently presented as `FRESH`.

No UI state may mutate Human Gate, Command Queue, effect candidates, runtime state, or canonical Drive truth.
