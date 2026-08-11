# Provider Drift Operator Attention Bridge V1

## Purpose

Project a verified provider-drift HOLD into a bounded, read-only SYSTEM ATTENTION lane in the Control Center Cockpit without creating or mutating HUMAN_NOW, effect candidates, command routing, dispatch authority, execution authority, or any provider/root/runtime state.

## Sources

- `control_center/data/provider_refresh_controller_status.current.v1.json`
- `control_center/data/command_queue.generated.v1.json`

## Output

`control_center/data/provider_system_attention.generated.v1.json`

Schema: `control_center.provider_system_attention.v1`
Projection kind: `NON_AUTHORITY_OPERATOR_ATTENTION_PROJECTION`

## Deterministic mapping

### Neutral / no current drift HOLD

When the source diagnostic verdict is `NO_HOLD_DIAGNOSTIC_RECORDED`:

- `system_attention` MUST be empty.
- This MUST NOT be interpreted as proof that provider drift is absent.
- `HUMAN_NOW` and effect-candidate counts are copied only as invariants and MUST remain unchanged.

### Verified drift HOLD

Only exact verdict `HOLD_PROVIDER_DRIFT_DETECTED` may create a provider drift system-attention item.

Exactly one item is emitted:

- id: `SYSATTN::PROVIDER_DRIFT_HOLD`
- state: `DRIFT_HOLD`
- owner: `CONTROL_CENTER`
- requested action: `READ_ONLY_PROVIDER_DRIFT_INVESTIGATION`
- human_now: `false`
- human_gate: `false`
- effect_candidate: `false`
- dispatch_authorized: `false`
- apply_authorized: `false`
- execution_authorized: `false`
- write_authorized: `false`
- auto_fix: `false`

The item may surface controller error codes and bounded mismatch rows already present in the diagnostic artifact. It MUST NOT invent remediation commands.

### Other HOLD classes

`HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED` remains a lease-expiry condition and is not promoted as provider drift attention.

`HOLD_INVALID_OR_INCOMPLETE_CAPTURE` is not provider drift and MUST NOT be relabeled as drift attention.

## Separation from HUMAN_NOW

SYSTEM ATTENTION is not a human gate queue. The bridge MUST prove that:

- Command Queue `HUMAN_NOW` length before/after is identical.
- effect-candidate count before/after is identical.
- no command id is created or inserted into Command Queue.
- no Human Gate Packet is created.
- no effect candidate is created.

## Safety

This projection never authorizes or performs:

- Drive/provider writes;
- snapshot/root/manifest/pointer writes;
- Return Registry writes;
- runtime/routing mutation;
- agent dispatch;
- semantic acceptance or apply;
- execution/deploy;
- external messages;
- trading or capital effects;
- self-application.

A real drift HOLD requires a separately governed read-only investigation first. Any subsequent mutation requires separate explicit effect authority.
