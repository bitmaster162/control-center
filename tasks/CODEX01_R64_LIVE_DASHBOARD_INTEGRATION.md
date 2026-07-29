# CODEX01-R64 — HANRI / Universe live dashboard integration

## Goal

Turn the provided R64 snapshot dashboard into the real read-only operator surface.

## Required start

- resolve the existing dashboard repository identified by `dashboard/api` and `dashboard/web`;
- verify repository root, branch, HEAD, tree and status;
- compare against the R64 baseline project; do not overwrite an unrelated dashboard;
- dirty/ambiguous baseline → stop.

## Read-only adapters, priority order

1. R63 Control Center current files;
2. ContinuityOS canonical state, checkpoints and proof ledger;
3. Return Broker / current return registry;
4. HANRI decisions, candidates and P0 register;
5. Fable/Codex/Claude/Work/Antigravity accepted returns;
6. product/deployment surfaces with source timestamp.

## Required UI

- Universe overview;
- systems with independent operational/truth/execution badges;
- agents and work orders;
- decisions and pending approvals;
- shared memory layers;
- evidence/timeline;
- P0 security status;
- communications/returns;
- open loops and next action;
- direct links to system cockpits.

Unknown or stale adapter data must render `UNKNOWN` or `DEGRADED`, never green.

## Acceptance

Robert can answer in five minutes:

- what exists;
- what works;
- what is verified;
- what is blocked;
- who is working;
- what requires his approval;
- where evidence lives;
- what changed since the last snapshot.

Return launch instructions, browser screenshots, tests, source hashes and strict broker delivery. No production deploy without separate approval.
