# HANRI R37 Phase 2 — Bounded Reversible Projection Executor

## Scope

Phase 2 adds one executable effect lane to the R37 governance layer:

`update_dashboard_projection` against exactly one Google Drive target:

- logical target: `Control canter/00_DASHBOARD_CURRENT/HANRI_R64_DASHBOARD_CURRENT_R36_FULL_VERIFIED.html`
- provider: `GOOGLE_DRIVE`
- provider target ID: `15GG9ElRV6Ed0gzGkB2b02JumHS58jU2r`
- effect class: `WRITE_REVERSIBLE`

No generic file writer is introduced.

## Authorization contract

Implementation alone does not authorize an effect.

A real write requires:

1. current target bytes captured as `before_bytes`;
2. exact desired bytes captured as `desired_bytes`;
3. action candidate containing both exact SHA-256 values;
4. R37 governance verdict `HUMAN_APPROVAL`;
5. non-expired approval bound to the exact `action_hash`;
6. provider target ID equal to the one hard-bound in executor policy;
7. target readback immediately before write still equal to approved `before_sha256`.

If any condition fails, zero writes are allowed.

## Execution contract

```text
read current target
→ compare exact before SHA
→ one bounded write
→ independent readback
→ compare exact after SHA
→ PASS / SEMANTIC_EFFECT_VERIFIED
```

If post-write readback does not equal the approved after SHA, or the provider call raises after write invocation:

```text
write captured before bytes
→ independent rollback readback
→ ROLLED_BACK only if before SHA is restored
→ otherwise ROLLBACK_FAILED
```

## Human identity limitation

The existing R37 phase-1 approval record is hash-bound and tamper-evident, but it is not a cryptographic identity signature. For this internal reversible pilot, a real effect still requires an explicit sovereign approval in the controlling operator session. Phase 2 must not claim that the approval artifact independently proves human identity.

## Preserved ceilings

- no CURRENT_POINTER write;
- no CURRENT_STATE write;
- no ROLE_INDEX write;
- no authority-generation mutation;
- no external messaging;
- TradingOS untouched;
- `can_trade=false`;
- `capital_permission=DENY`.

## Tests

The phase-2 regression suite covers:

- exact before/after hash binding;
- payload substitution after approval;
- provider target substitution;
- expired approval;
- target drift before write => zero writes;
- successful independent readback;
- corrupted post-write state => rollback;
- provider interruption after write => rollback.

## Acceptance boundary

CI PASS accepts the implementation candidate only. It does not authorize a Google Drive write.

The first real effect must be presented as an exact action card with:
- action hash;
- Drive file ID;
- before SHA-256;
- after SHA-256;
- snapshot ID;
- rollback SHA-256;
- approval expiry.

The operator must approve that exact card before execution.
