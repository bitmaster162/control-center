# HANRI R39.2.1 — Attention Coverage Closure

## Why this patch exists

The first real R39.2 host pilot passed but reported:

- `SELF=2`
- `AGENT=1`
- `SYSTEM=15`
- `OPERATOR=0`
- `COVERAGE_COMPLETE=false`
- `SCAN_SKIPS=54`

Two gaps were identified.

### 1. Canonical operator feedback was not recognized by the adapter

The accepted HANRI event schema already defines `event_type="OPERATOR_FEEDBACK"` as a first-class event. R39.2 nevertheless required either:

- `actor` equal to `ROBERT`, `HUMAN` or `OPERATOR`; or
- an explicit `operator_event` / `human_event` boolean.

That could reject a valid human-feedback event emitted by HANRI/system code where `actor` identifies the emitter rather than the human subject.

R39.2.1 treats `OPERATOR_FEEDBACK` itself as the schema-bound proof that the event belongs to the OPERATOR attention domain. It normalizes such an event to:

- `operator_event=true`
- `subject_id=ROBERT`
- evidence ref `EVENT_SCHEMA:OPERATOR_FEEDBACK`

This only establishes attention coverage. It does **not** create a material finding unless the event independently carries a real signal such as `MANUAL_REPEAT`, friction, overload or repeated correction.

### 2. Scan skips were opaque

R39.2 exposed only one aggregate `scan_skip_count`. R39.2.1 adds:

- `scan_skip_reason_counts`
- `scan_skip_source_counts`
- the existing exact `scan_skips` ledger

This makes stale files, missing paths, unsupported JSON and other scan exclusions directly auditable.

## Host closure rule

The next real host pilot should distinguish three outcomes:

1. **Coverage closed** — `OPERATOR > 0`, all four domains covered.
2. **No canonical operator feedback exists** — OPERATOR remains a real blind spot; do not synthesize an event.
3. **Operator evidence exists but is excluded for another reason** — use skip breakdown to repair the exact producer contract.

`COVERAGE_COMPLETE=false` is not an execution failure. It is an attention-integrity finding.

## Safety boundary

R39.2.1 remains a read-only producer observation layer:

- no provider calls;
- no scheduler installation;
- no stable-root writes;
- no R36 runtime modification;
- no synthetic operator events;
- no self-apply;
- no skill install;
- no system write;
- no operator message;
- no auto-dispatch;
- `can_trade=false`;
- `capital_permission=DENY`.
