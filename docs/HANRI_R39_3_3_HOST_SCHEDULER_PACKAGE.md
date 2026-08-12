# HANRI R39.3.3 — Host Scheduler Package

R39.3.3 packages the accepted semantic attention loop and cadence controller for a reversible Windows Scheduled Task deployment. This release does **not** itself authorize or install the task.

## Runtime contract

The OS task provides one fixed 5-minute heartbeat. `Invoke-R39.3.3AttentionHeartbeat-PS51.ps1` decides whether a full attention cycle is due. `MultipleInstances=IgnoreNew` prevents scheduler overlap; a second local lease protects manual/concurrent invocations.

The cadence transaction is commit-after-success: when a full scan is due, R39.3.1 must finish successfully and produce its receipt before R39.3.2 records `RUN_FULL_ATTENTION`. A failed full loop therefore leaves the cadence due instead of recording a fictitious successful run.

## Install transaction

`Install-R39.3.3AttentionTask-PS51.ps1` defaults to dry-run. It computes a host-specific SHA-256 action over the exact source HEAD/tree, runtime manifest, existing task XML hash, task name, principal, paths and scheduler settings. Installation requires the exact command printed by the dry-run:

`APPROVE_R39_3_3_SCHEDULER:<action_hash>`

Before touching Task Scheduler, apply mode stages the runtime and authoritative R64 human-decision receipt and executes a real local heartbeat preflight. Existing task XML and application root are backed up. Registration is followed by fresh XML readback. Any register/readback failure removes the new task and restores the prior task/application state.

## Rollback / uninstall

Uninstall is a separate effect and a separate hash gate. Dry-run prints `APPROVE_R39_3_3_UNINSTALL:<hash>`. Apply unregisters the R39 task, retires the installed application directory, and restores the prior task XML when one existed before installation.

## Safety boundary

The task does not grant HANRI approval, self-application, provider-write, messaging, dispatch, trading, or capital authority. `can_trade=false` and `capital_permission=DENY` remain invariant. Dynamic scheduler self-reconfiguration is forbidden; adaptation happens inside the cadence controller over the fixed heartbeat.
