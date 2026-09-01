# Control Tower / Portfolio Lens Contract R1

Status: LOCAL CANDIDATE / READ_ONLY / NO PROVIDER EFFECTS

## Role

Control Tower is a deterministic portfolio-observation lens. It is not a second Control Center.

It consumes portable/fresh evidence such as RUAP `ruap.snapshot/v1` and emits a cross-project currentness view suitable for Control Center reconciliation.

## Input

R1 accepts RUAP Snapshot IR with:

- `schema = ruap.snapshot/v1`
- `authority_ceiling = OBSERVE_ONLY`
- explicit `sources`
- explicit `observations`

The lens preserves source identity and never treats snapshot recency as authority.

## Output planes

Every entity has separate planes:

- `source`
- `deployment`
- `runtime`
- `effect`
- `semantic_authority`

R1 may classify **source currentness** as:

- `CURRENT`
- `PARTIAL`
- `HOLD`
- `BLOCKED`

R1 deliberately emits:

- deployment = `UNKNOWN`
- runtime = `UNKNOWN`
- effect = `DENY`
- semantic_authority = `CONTROL_CENTER_ONLY`

unless a future contract explicitly adds separately verified provider/runtime inputs.

## Hard boundaries

- No provider writes.
- No effect token generation.
- No human gate consumption.
- No Control Center current-truth mutation.
- No ContinuityOS checkpoint mutation.
- No deploy.
- No trading/capital effects.
- `can_trade=false`
- `capital_permission=DENY`
- `deploy_permission=DENY`

## Relationship

`RUAP = portable evidence/context`

`Control Tower = read-only portfolio lens`

`Control Center = operational truth + routing + semantic/effect authority`

`ContinuityOS = durable checkpoint/proof/replay`

The Tower can recommend **NEXT READ**, never **EXECUTE**.
