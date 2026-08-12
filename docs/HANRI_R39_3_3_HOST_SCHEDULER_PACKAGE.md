# HANRI R39.3.3 — Host Scheduler Package

## Purpose

R39.3.3 packages the accepted R39.3.1 semantic attention loop and R39.3.2 cadence controller for a Windows Scheduled Task without changing R36, stable Control Center roots, providers, or effect authority.

The package is **install-ready but not self-installing**. `Install-R39.3.3AttentionScheduler-PS51.ps1` is dry-run by default and requires an explicit `-Apply -ExpectedCommit <sha> -ExpectedTree <sha>` host write gate.

## Task contract

- Task name: `ControlCenter-HANRI-R39-Attention`
- Fixed heartbeat: 5 minutes
- Multiple instances: `IgnoreNew`
- Start when available: true
- Execution time limit: 10 minutes
- At-logon trigger plus fixed 5-minute repetition
- Production runner: `Run-R39.3.3AttentionHeartbeat-PS51.ps1`

The fixed task does not rewrite its own schedule. R39.3.2 decides whether each heartbeat is:

- `RUN_FULL_ATTENTION`
- `SKIP_NOT_DUE`
- `SKIP_OVERLAP`

Adaptive full-attention cadence remains 5/10/15/30/60 minutes according to coverage loss, negative outcomes, active proposals, normal operation, and sustained semantic `NO_DELTA`.

## Production hot path

The scheduled heartbeat does **not** run pytest or git. On a due cycle it executes only the accepted local evidence pipeline:

1. R39.2.2 producer adapters;
2. R39.3.1 semantic attention fabric (`SEMANTIC_ENVELOPE_V2`);
3. R39.3.1 continuous attention state transition;
4. R39.3.2 cadence commit based on the newly observed loop state.

On a not-due heartbeat, the expensive producer/fabric/loop path is skipped.

The cadence decision is probe/commit. A due probe does not mutate durable cadence state before the full attention cycle finishes. The final interval is committed from the **new** loop receipt, so a newly discovered coverage loss or negative outcome can immediately select the 5-minute urgent cadence.

## Overlap containment

Two independent guards exist:

- Windows Scheduled Task `MultipleInstances=IgnoreNew`;
- an exclusive local process lease (`FileShare.None`).

A concurrent/manual second invocation returns `SKIP_OVERLAP` and does not mutate cadence state.

## Isolated install layout

The installer copies the accepted `hanri_runtime/r28` bytes to an isolated local app tree. The scheduled process therefore does not depend on the current git branch or mutable worktree after installation.

The existing R64 human-decision receipt is copied into the isolated evidence tree and SHA-bound in `INSTALL_MANIFEST.json`. Dynamic R36 state, return intake, operator-event inbox, R23 sync state, and R39 receipts continue to be read from their existing read-only producer surfaces.

## R36 side-by-side invariant

R36 remains the accepted live engine and is not a rollback target for R39.3.3. The installer:

1. requires the R36 Scheduled Task to exist and be enabled;
2. records the exact exported R36 task XML SHA before installation;
3. never disables, stops, unregisters, or rewrites R36;
4. records and compares the R36 task XML SHA after installation.

`Verify-R39.3.3AttentionScheduler-PS51.ps1` re-checks the same R36 baseline.

## Installation transaction and rollback

Before any R39.3.3 task registration the installer:

- runs R39.3.3/R39.3.2/R39.3.1 regression tests;
- exports an existing R39 attention task if one exists;
- backs up the prior isolated app and live state;
- copies and hashes the accepted runtime/evidence snapshot;
- executes one manual full-attention preflight and requires complete SELF/AGENT/SYSTEM/OPERATOR coverage with zero execution effects.

Only after those gates pass is the R39 attention task registered. The installer then starts the task once and requires a fresh heartbeat receipt.

Any failure after cutover starts removes the new R39 task and restores the recorded predecessor app/state/task. R36 is outside the rollback write set.

A later explicit rollback uses `Restore-R39.3.3AttentionScheduler-PS51.ps1 -Apply`.

## Effect boundary

The scheduled attention loop remains proposal/evidence infrastructure only:

- provider calls: 0
- human decision execution: false
- self-apply: false
- skill install: false
- system write: false
- operator message: false
- auto-dispatch: false
- external messages: false
- `can_trade=false`
- `capital_permission=DENY`

Installing or removing the Windows Scheduled Task is a separate host write effect and requires explicit operator authorization. It does not grant HANRI permission to apply any recommendation.
