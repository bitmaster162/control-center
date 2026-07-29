# R64-P1 Dispatch — authority remains R63

## FABLE-5 runtime

```text
Apply HANRI Control Center R64-P1 as an implementation/dashboard patch.

Authority remains R63 ACCEPTED.
Do not create a control generation.

Use contracts/hanri-dashboard-snapshot.schema.json v1.0.0.
Regenerate data/snapshot.json, snapshot.js and standalone HTML only from verified sources.
Merge the R63 operator dashboard into the Audit tab.
Render CLAIMED yellow, UNKNOWN gray, CONFLICTED/REJECTED/open P0 red.
Green requires RECEIPTED/HASH_VERIFIED + CURRENT + evidence refs.

Publish the implementation package and standalone under 00_DASHBOARD_CURRENT.
Return exact Drive IDs, provider readback hashes and a no-authority-mutation receipt.

can_trade=false
capital_permission=DENY
deploy_permission=DENY
self_application=false
```

## CODEX-01

```text
Execute tasks/CODEX01_R64_P1_CONTRACT_BOUND_LIVE_DASHBOARD.md.
Use the supplied verified Git baseline and snapshot contract v1.0.0.
Shadow/read-only only. No production deploy.
Return strict ZIP/SHA/READY-last through the broker.
```

## Antigravity

```text
Execute tasks/ANTIGRAVITY_R64_P1_P0_RECEIPT_CLOSURE.md.
Do not repeat R63/R64 acceptance or workspace reorganization.
D4 remains open until P0-1/P0-2/P0-3 receipts pass their negative-test schema.
No secret values in receipts.
```

## HANRI implementation slot

```text
Execute tasks/HANRI_R64_P1_SELF_IMPROVEMENT_GOVERNOR.md.
Live runtime remains HANRI R28.
Build shadow candidate only; no self-application and no automatic cutover.
Return INSTALL_GATE_READY only after rollback/recovery and zero-live-write proof.
```

## Hold states

- D5 Roman: `SEND_APPROVED_PENDING_CHANNEL`; no sent receipt without explicit `SEND ROMAN` and authenticated channel.
- No new authority generation during CONTROL_FREEZE.
- CODEX-07 continues existing shadow event-bus/dedup work; do not restart it.
