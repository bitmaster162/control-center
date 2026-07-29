# R64-P1 Controller → FABLE Runtime Handoff

## Decisions

1. R63 controller state is formally `ACCEPTED`.
2. R64 remains an implementation/dashboard layer; no new authority generation is created.
3. The canonical dashboard frame is the R64 UI.
4. The R63 operator dashboard is merged into the required `Audit` tab.
5. Snapshot contract v1.0.0 is normative for deterministic runtime regeneration.
6. D4 remains `P0_CLAIMED_NOT_RECEIPTED`; no green/closed rendering until three validated closure receipts exist.
7. HANRI governor is dispatched to shadow/install-gate only; live R28 is not replaced.
8. D5 remains `SEND_APPROVED_PENDING_CHANNEL`; no message is recorded as sent without an authenticated channel receipt.
9. CONTROL_FREEZE remains active.

## Runtime action

FABLE may regenerate `data/snapshot.json`, `data/snapshot.js` and standalone HTML from verified sources using this contract. It must preserve exact evidence states and never convert claims to receipts.

## Required next receipts

- CODEX-01 contract-bound dashboard shadow return;
- Antigravity P0 closure receipts;
- HANRI governor shadow/install-gate return;
- R28 5-minute cadence execution receipt if the cadence action is actually run.

`can_trade=false`; `capital_permission=DENY`; `deploy_permission=DENY`; `self_application=false`.
