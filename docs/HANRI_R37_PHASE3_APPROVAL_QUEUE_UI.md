# HANRI R37 Phase 3 — Approval Queue UI

## Purpose

Phase 3 makes the R37 human gate visible inside Control Center without moving sovereign authority into the browser.

The UI is a read-only approval projection. It can display an exact approval command for a pending action and copy that command to the clipboard. It cannot approve, execute, retry, replay, or call a provider.

## Queue contract

Policy version: `37.2.0-approval-queue-v1`.

Each item exposes only a minimal safe summary:

- action hash;
- actor;
- operation;
- effect class;
- logical target;
- provider and provider target ID;
- snapshot ID when applicable;
- exact before/after SHA-256 when applicable;
- status and expiry;
- execution receipt status/hash when available.

Arbitrary action args are never projected into the queue. This prevents credentials, message bodies, tokens, or unrelated payload fields from leaking through the UI.

## Status model

- `PENDING_APPROVAL`: exact approval command may be copied.
- `APPROVED_NOT_EXECUTED`: approval already exists; no replay command is shown.
- `EXECUTED_VERIFIED`: independent receipt proves the effect; no replay command is shown.
- `DENIED`: policy denied the candidate.
- `EXPIRED`: approval window elapsed; no replay command is shown.
- `ROLLED_BACK`: effect was reverted and rollback was verified.
- `FAILED`: execution/rollback did not reach a verified state.
- `NOT_APPLICABLE`: candidate does not require human approval.

## Sovereign boundary

`APPROVE_R37_EFFECT:<action_hash>` is only a human instruction token for the controlling operator channel. Copying it is not approval. The browser does not create approval records and does not call the Effect Gateway.

A real effect still requires:

1. exact current candidate;
2. exact action hash;
3. non-expired sovereign approval outside the browser;
4. executor-side action re-hash;
5. fresh provider precondition readback;
6. bounded write;
7. independent post-write readback;
8. receipt or rollback.

## Current evidence row

The initial queue projection contains the already completed first R37 governed effect as `EXECUTED_VERIFIED`:

- action hash `7a4e0938832b1a35c6d9c6b483ee206be4d924847c7602ef2bde4c5c81f0ffd0`;
- Google Drive dashboard target ID `15GG9ElRV6Ed0gzGkB2b02JumHS58jU2r`;
- before SHA `f29de43fb2bafcb54049159267331ceec8c46b5d2153291b9ba15bc8bbca75e3`;
- after SHA `a711c55e2443732dd4e004838a988ae3f8d9a7c88fac1f1350a90ede0441bee7`;
- receipt SHA `65abda776e26c4bf787d3e6c21decbc4d7b39d4f882dd2d6c980a2c153dedbf7`.

No approval command is exposed for the completed row, so the UI cannot encourage accidental replay.

## Preserved ceilings

- stable authority roots unchanged;
- no new authority generation;
- no external messages;
- TradingOS untouched;
- `can_trade=false`;
- `capital_permission=DENY`;
- `auto_approval=false`;
- `auto_execution=false`.

## Acceptance boundary

Merge/CI accepts only the product implementation. Deploying the Approval Queue into the live Drive dashboard is itself a new `WRITE_REVERSIBLE` effect and must receive its own exact hash-bound approval.
