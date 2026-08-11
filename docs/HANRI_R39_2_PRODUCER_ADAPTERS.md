# HANRI R39.2 — Producer Adapters

R39.2 connects real Control Center artifacts to the R39.1 Attention Fabric without embedding HANRI inside producer transports.

## Boundary

The Control Center repository does not own the external Return Broker transport implementation. The canonical inter-agent contract already defines the broker as an artifact transport: strict return → broker/Drive slot → validator → registry → checkpoint. R39.2 therefore consumes the evidence artifacts **after they exist**. It does not patch, intercept or impersonate the broker.

## Producer surfaces

Default Windows bindings are derived from the accepted R36 runtime configuration:

- agent returns: `%USERPROFILE%\My Drive\Control canter\00_INBOX_RAW\agent_returns\_R23_INTAKE`
- R36 system state: `%LOCALAPPDATA%\ControlCenterHANRIR36\state`
- Return Sync R23 state: `%LOCALAPPDATA%\ControlCenterReturnSyncR23\state\latest_state.json`
- structured R36 event inbox: `%LOCALAPPDATA%\ControlCenterHANRIR36\event_inbox`
- HANRI R39 receipts: `%LOCALAPPDATA%\ControlCenterHANRIR39\receipts`

Only bounded JSON artifacts inside configured age/size/file-count windows are inspected.

## Coverage is not a finding

Continuous audit needs to represent two different facts:

1. `AUDIT_COVERAGE`: HANRI actually inspected evidence for SELF / AGENT / SYSTEM / OPERATOR. This satisfies attention coverage but creates no finding or proposal by itself.
2. Material observation: the inspected evidence contains a defect/friction/skill-gap/drift signal. This creates the normal R39 finding and proposal.

This prevents two opposite errors:

- treating a healthy audit as an improvement request;
- treating missing evidence as healthy state.

A material observation also counts as attention coverage. If a domain has neither material evidence nor an `AUDIT_COVERAGE` record, it remains an explicit attention blind spot.

## Adapter semantics

### RETURN_ARTIFACT

Material failure, explicit skill gap or tool misuse → `AGENT_RETURN`.
Otherwise → `AUDIT_COVERAGE(domain=AGENT)`.

### SYSTEM_RECEIPT

FAILED / ERROR / DEGRADED / DOWN / HALTED, or STALE / UNKNOWN / CONFLICT freshness → `SYSTEM_HEALTH`.
Otherwise → `AUDIT_COVERAGE(domain=SYSTEM)`.

### OPERATOR_EVENT_ARTIFACT

Only explicitly human-bound events (`ROBERT`, `HUMAN`, `OPERATOR`, or explicit operator_event marker) are eligible. Manual-repeat / friction / overload / bottleneck evidence → `OPERATOR_EVENT`; ordinary audited human events → OPERATOR coverage. Non-human events are skipped rather than misclassified.

### HANRI_RECEIPT

FAIL / REVISE / missed-defect / attention-self-review signals → `HANRI_SELF_TRACE`.
Otherwise → SELF coverage.

### RECOMMENDATION_OUTCOME_ARTIFACT

An explicit recommendation/proposal/candidate ID plus outcome status → `RECOMMENDATION_OUTCOME`. Incomplete outcome artifacts are skipped fail-closed.

## Secret boundary

Adapters never persist the arbitrary producer artifact body into an attention envelope. They extract only a small whitelist of status, identity, summary, repeated-count and recommendation fields. Persistence-bound strings pass through the accepted `enhanced_sanitize` secret boundary; raw credential values are not persisted and only fingerprints may appear in secret findings.

## Idempotence

Envelope identity binds:

`adapter_type + logical source ID + exact source SHA-256`

Same source bytes produce the same envelope ID. Changed source bytes produce a new ID. The producer runner writes one current bundle atomically under the dedicated R39 producer-current directory.

## Host runner

`Run-R39.2ProducerAdapters-PS51.ps1` performs:

```text
read configured producer artifacts
→ sanitize / classify
→ write local current attention bundle + adapter receipt
→ R39.1 Attention Fabric
→ findings / coverage / prioritized proposals receipt
```

It does **not** install a scheduler. Scheduling/cutover is a separate reversible host action and requires its own execution gate.

## Effect boundary

- producer source reads only
- local R39 attention bundle/receipt writes only
- provider_calls=false
- stable roots unchanged
- R36 runtime unchanged
- self_apply=false
- skill_install=false
- system_write=false
- operator_message=false
- auto_dispatch=false
- external_messages=false
- can_trade=false
- capital_permission=DENY
