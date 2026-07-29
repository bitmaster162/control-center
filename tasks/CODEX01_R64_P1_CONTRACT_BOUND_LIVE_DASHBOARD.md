# CODEX01-R64-P1 — Contract-bound live dashboard integration

## Decision binding

- Authority generation: `R63`, status `ACCEPTED`.
- Implementation layer: `R64-P1`; it is not a new control generation.
- Canonical UI: the R64 dashboard.
- Canonical projection contract: `contracts/hanri-dashboard-snapshot.schema.json` v1.0.0.
- The former R63 operator dashboard becomes the `Audit` tab; it must not remain a competing truth surface.

## Git start gate

1. Resolve the existing dashboard repository/root.
2. Record branch, baseline HEAD/tree and porcelain.
3. Compare it with the supplied R64 Git identity.
4. Dirty or ambiguous state → `BLOCKED_GIT_BASELINE`.

## Source adapters, read-only priority

1. R63 `CURRENT_POINTER`, `CURRENT_STATE`, `ROLE_INDEX`, `ROLE_VIEWS`.
2. Live HANRI R28 state in `%LOCALAPPDATA%\ControlCenterHANRIR28\state`.
3. ContinuityOS checkpoints/proof ledger/current operational state.
4. `CURRENT_RETURN_REGISTRY` and deterministic broker index.
5. Decisions, defect ledger and P0 closure receipts.
6. Accepted returns and product/deployment receipts.

Each adapter must emit source locator, evidence state, freshness state, `as_of` and optional SHA/Drive ID. An unavailable adapter produces `UNKNOWN` or `DEGRADED`; it cannot infer healthy state.

## Required implementation

- Generate `data/snapshot.json` deterministically.
- Validate it against snapshot contract v1.0.0.
- Generate `data/snapshot.js` from the exact same JSON bytes.
- Render the existing eight tabs plus `Audit`.
- Merge HANRI loop, authority acceptance, P0 receipts, defect ledger and artifact acceptance into `Audit`.
- Preserve snapshot fallback when live adapters fail.
- Generate one self-contained standalone HTML from the same payload.
- Display snapshot ID, contract version, authority generation/status, mode and payload SHA.

## Truth rendering

- Green only for `RECEIPTED` or `HASH_VERIFIED`, `CURRENT`, non-empty evidence refs.
- `CLAIMED` → yellow and visibly labelled.
- `UNKNOWN` → gray.
- `CONFLICTED`, `REJECTED`, failed gates and open P0 → red.
- `STALE` overrides green to yellow.
- Do not use a universal freshness threshold. Each source adapter declares its own contract and basis.

## Required tests

- schema validation positive and negative controls;
- missing mandatory source → degraded, not green;
- claimed P0 → yellow, never closed;
- stale receipted data → yellow;
- identical normalized input + explicit timestamp → byte-identical snapshot;
- standalone/server payload hash equality;
- no write calls to source roots;
- browser desktop/mobile smoke with zero console errors;
- links to exact evidence locators.

## Terminal states

- `LIVE_DASHBOARD_SHADOW_PASS_INSTALL_READY`
- `REVISE`
- `BLOCKED_GIT_OR_SOURCE_CONFLICT`

No production deployment, no source mutation, no authority update. Return strict ZIP/SHA/READY-last through the broker.

`can_trade=false`; `capital_permission=DENY`; `deploy_permission=DENY`.
