# HANRI R28 — Human-AI Native Archive Provenance Improvement

A model-API-free, bounded recursive improvement supervisor for Robert's Control Center.

R28 retains the causal archive loop and adds a recovery-provenance boundary. R27 changed the archive loop from a two-point comparison to a three-point causal spine:

```text
ORIGIN intent
→ material CORRECTION / PIVOT
→ CURRENT physical state
→ smallest candidate delta
→ falsification
→ Robert decision
```

## Why the pivot matters

An origin/current comparison can erase the exact corrections that made the system proof-first. R27 therefore requires one oldest origin item, one correction/pivot item and one newest current item in the same bounded archive cycle. Missing any side produces `CAUSAL_SPINE_INCOMPLETE`.

## Core invariants

- Maximum recursive depth: 2.
- No material delta means STOP.
- No self-application.
- No external model APIs or network calls.
- No source/repository/runtime effects.
- Secret values are redacted to fingerprints.
- Human approval is required for every candidate delta.
- Coverage claims are scope-bound by `scope_id + manifest hash + numerator/denominator + evidence ceiling`.
- Primary Source-001 and legacy analytical cursors remain separate.
- Historical liveness cannot become current liveness without fresh target readback.
- Filesystem root is not a Git repository root without `git rev-parse --show-toplevel`.
- Probe counts, failure counts, evidence families and root causes are separate metrics.
- `can_trade=false`; capital permission `DENY`.

## One-time Windows installation

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\Install-R28ImprovementTask.ps1 -Apply
```

The task processes events each minute. The archive scan is rate-limited to once per 15 minutes and reuses unchanged file records.

Writes are limited to:

```text
%LOCALAPPDATA%\ControlCenterHANRIR28
%USERPROFILE%\My Drive\Control canter\00_CONTROL\HANRI_R28
```

## Record one step

```powershell
.\scripts\Record-R28Step.ps1 `
  -TaskId "TASK-123" `
  -StepId "STEP-01" `
  -EventType "STEP_END" `
  -ChecksJson '{"changed_evidence":true,"effect_rung":"TARGET_READBACK"}'
```

## Status

```powershell
.\scripts\Get-R28Status.ps1
```

## Important boundary

A chat response cannot keep a hidden model process alive. Persistent processing exists only after the local Scheduled Task is installed. R28 observes and proposes; it never self-applies.


## R27 truth-kernel controls retained in R28

R27 adds deterministic audits for numerical universes, arithmetic partitions, authority-surface multiplicity, specification/implementation separation, and machine-verifiable proof-ledger fields.

## R28 recovery-provenance controls

R28 separates `COPY_SAFE` from `SAFE_TO_DISTRIBUTE`, detects collector self-ingestion, prevents control metadata from inflating primary-source coverage, and requires independent source-effect and content-secrecy receipts.
