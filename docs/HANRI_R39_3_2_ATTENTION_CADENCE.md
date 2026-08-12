# HANRI R39.3.2 — Attention Cadence Controller

R39.3.2 decides when a full R39.3.1 semantic attention cycle is due. It does not install or modify a scheduler.

## Architecture

A future Windows Scheduled Task may provide a fixed 5-minute heartbeat. The cadence controller converts each heartbeat into one of:

- `RUN_FULL_ATTENTION`
- `SKIP_NOT_DUE`
- `SKIP_OVERLAP`

The task itself remains static. Adaptive cadence is state-driven, so HANRI does not rewrite its own scheduler.

## Cadence policy

- coverage loss or unresolved negative outcome: 5 minutes
- active material proposal: 10 minutes
- normal balanced observation: 15 minutes
- 3+ semantic `NO_DELTA` cycles: 30 minutes
- 6+ semantic `NO_DELTA` cycles: 60 minutes

Any real semantic change resets the quiet progression through the R39.3.1 loop state.

## Overlap control

The product contract requires `MultipleInstances=IgnoreNew` for a future Windows Scheduled Task and a 10-minute execution/lease envelope. The controller also models an active lease as `SKIP_OVERLAP`. Installation and concrete host lease wiring are separate effect-gated work.

## Authority boundary

R39.3.2 is advisory/local-state only. It does not install or modify Scheduled Tasks, call providers, execute human decisions, apply skills, modify systems, message the operator, auto-dispatch work, trade, or obtain capital permission.

A future scheduler installation is a host write and requires a separate exact effect authorization after host preconditions and rollback are prepared.
