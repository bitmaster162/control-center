# HANRI R37 — Effect Governance Control Plane Pilot

## Scope

R37 is a **PRODUCT_DELTA** above the accepted/live R36 runtime. It does not create a new control-generation and does not replace the R36 heartbeat/runtime engine.

The first pilot is bound only to this repository's Control Center action candidates. No external-agent demo is required.

## Goal

Turn the existing HANRI supervisory path into a machine-verifiable effect gate:

```text
action candidate
→ normalize + secret boundary
→ exact action hash
→ risk/effect classification
→ policy verdict
→ ALLOW | DENY | HUMAN_APPROVAL
→ hash-bound approval record when required
→ future bounded executor
→ future independent readback
→ effect receipt / rollback
```

R37 phase 1 stops before execution. `enforcement_mode=SHADOW_ONLY` and `execution_authorized=false` are mandatory for every evaluated action.

## Control Center policy matrix

| Effect class | Pilot verdict | Notes |
|---|---|---|
| READ_ONLY | ALLOW | Read/inspect/search only |
| WRITE_REVERSIBLE | HUMAN_APPROVAL | Persistent internal write |
| WRITE_EXTERNAL | HUMAN_APPROVAL | Email/message/publish |
| AUTHORITY_CHANGE | HUMAN_APPROVAL, unless protected target override | Authority/credential/permission changes |
| IRREVERSIBLE | HUMAN_APPROVAL | Requires explicit sovereign gate |
| CAPITAL | DENY | Current authority ceiling |
| UNKNOWN | DENY | Fail closed |

Protected target overrides hard-deny direct writes to CURRENT_POINTER.json, CURRENT_STATE.json and ROLE_INDEX.json during the pilot. TradingOS is hard-denied under current R64 scope.

## Exact approval binding

For HUMAN_APPROVAL decisions, the approval record binds to the exact `action_hash`. The hash is calculated over normalized/sanitized actor, operation, target, effect class, args, scope and metadata. Any material mutation produces a different hash and invalidates the prior approval.

The R37 phase-1 approval record is **hash-bound but not cryptographically signed**. Authentic signature/identity binding is a later product hardening step; this pilot must not represent the record as a signed authorization token.

## Secret boundary

Action candidates are sanitized through the existing contextual secret boundary before persistence or hashing. Sensitive values are replaced by redacted fingerprints; raw secret values are not written into effect receipts.

## Pilot fixtures

`hanri_runtime/r28/data/r37_control_center_effect_candidates.json` contains five Control Center cases:

1. read current truth → ALLOW;
2. update dashboard projection → HUMAN_APPROVAL;
3. external follow-up message → HUMAN_APPROVAL;
4. direct CURRENT_STATE write → DENY;
5. TradingOS capital action → DENY.

Expected matrix: `ALLOW=1`, `HUMAN_APPROVAL=2`, `DENY=2`, `EXECUTION_EFFECTS_PERFORMED=0`.

## Host runner

```powershell
powershell -ExecutionPolicy Bypass -File .\hanri_runtime\r28\scripts\Run-R37EffectGovernancePilot-PS51.ps1
```

Success terminal:

```text
HANRI_R37_CONTROL_CENTER_SHADOW_PASS
ALLOW 1
HUMAN_APPROVAL 2
DENY 2
EXECUTION_EFFECTS_PERFORMED 0
```

## Non-goals in R37 phase 1

- no automatic execution;
- no external messages;
- no deployment to third-party agents;
- no mutation of canonical CURRENT_POINTER/CURRENT_STATE/ROLE_INDEX;
- no TradingOS effects;
- no capital effects;
- no automatic authority expansion;
- no claim that hash-bound approval is a cryptographic signature.

## Next product gate

After shadow evidence is accepted, R37 phase 2 may add one bounded **internal reversible executor adapter** for Control Center projection writes. It must require exact approval, verified Git baseline, independent target readback and rollback receipt before any wider action class is enabled.
