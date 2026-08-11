# Provider Drift Resolution Transition V1

Status: REVIEW-ONLY CONTROL-CENTER ENGINEERING CONTRACT

## Purpose

This contract defines the only valid read-only control-plane transition from an active provider drift hold to a resolved provider drift state.

The transition exists to prevent two failure modes:

1. silently clearing `HOLD_PROVIDER_DRIFT_DETECTED` merely because a later status is non-HOLD;
2. leaving stale `SYSTEM ATTENTION` active after a strictly newer exact provider readback has already refreshed validated freshness evidence.

## Source chain

`provider_refresh_controller_status.current.v1.json`
→ `provider_freshness_evidence.current.v1.json`
→ `provider_drift_resolution.generated.v1.json`
→ `provider_system_attention.generated.v1.json`

The resolution projection is non-authority. It does not write provider roots, refresh evidence, mutate the command queue, create a Human Gate Packet, dispatch work, apply effects, deploy, trade, or grant capital authority.

## Drift identity

An active drift hold is bound by a deterministic SHA-256 fingerprint over these diagnostic fields only:

- `verdict`
- `source_capture`
- `controller_errors`
- `mismatches`

A resolution for one drift fingerprint cannot clear a different or later drift diagnostic.

## Valid transition

`HOLD_PROVIDER_DRIFT_DETECTED` may transition to `RESOLVED_BY_NEWER_EXACT_CAPTURE` only when all conditions are true:

1. the source diagnostic still has `verdict=HOLD_PROVIDER_DRIFT_DETECTED` and `hold_active=true`;
2. the freshness evidence schema is `control_center.provider_freshness_evidence.v1`;
3. evidence semantics are `FRESH_AT_CAPTURE` with `continuous_freshness=false`;
4. evidence `observed_at` is strictly newer than the drift diagnostic `source_capture.observed_at`;
5. the evidence contains exactly the five stable R64 roots;
6. `all_five_exact_at_capture=true`;
7. `pointer_last_by_provider_modified_time=true`;
8. `authority_critical_snapshot_match=true`.

Anything less leaves the drift unresolved.

## States

- `NO_ACTIVE_DRIFT_HOLD` — no active provider-drift hold is currently recorded. This does not prove drift is absent.
- `DRIFT_HOLD_UNRESOLVED` — an active drift hold exists but no strictly newer validated exact evidence resolves that exact drift fingerprint.
- `RESOLVED_BY_NEWER_EXACT_CAPTURE` — a strictly newer exact freshness evidence record resolves that exact drift fingerprint.

## Alert clearing rule

`SYSATTN::PROVIDER_DRIFT_HOLD` may be suppressed only when the resolution projection is `RESOLVED_BY_NEWER_EXACT_CAPTURE` and its `source_drift_fingerprint` equals the fingerprint of the currently supplied drift diagnostic.

A neutral/non-HOLD status alone is never a drift-resolution receipt.

## Authority ceiling

Every transition projection must preserve:

- `provider_write_authorized=false`
- `root_write_authorized=false`
- `registry_write_authorized=false`
- `runtime_mutation_authorized=false`
- `routing_mutation_authorized=false`
- `dispatch_authorized=false`
- `apply_authorized=false`
- `execution_authorized=false`
- `deploy_authorized=false`
- `external_message_authorized=false`
- `can_trade=false`
- `capital_permission=DENY`
- `self_application=false`

Resolution is evidence-driven alert lifecycle state only. It is not remediation authority.
