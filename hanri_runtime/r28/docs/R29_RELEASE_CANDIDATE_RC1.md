# HANRI R29 RC1 Promotion Gate

Status: `RC1_READY_FOR_LOCAL_INSTALL / NOT_YET_INSTALLED`

Verified parent baseline:

- R28 commit: `e8a1d944dec01a21bf43a3075b8b11fe1920fcd3`
- R28 tree: `2c1f27b2c4e234d7e2afcb4d190fda54aa027563`

R29 candidate review:

- review PR: `#3` (review-only; never merge into R28 baseline)
- CI run before RC freeze: `31322578203`
- validation: PASS
- pytest: PASS
- JS syntax: PASS
- deterministic assets: PASS

Install model:

1. exact clean Git branch `hanri/r29-release-candidate`;
2. exact expected commit passed explicitly to installer;
3. side-by-side install at `%LOCALAPPDATA%\ControlCenterHANRIR29\app`;
4. separate R29 state and Drive projection;
5. direct one-shot compile/run/readback first;
6. only after PASS, register/enable R29 scheduler and disable (not delete) R28 scheduler;
7. verify scheduled-run receipt and invariants;
8. rollback is scheduler switch back to preserved R28; no state deletion.

Hard invariants:

- `program_version=29.0.0`
- `shadow_only=true`
- `external_model_api=DENY`
- `self_application=false`
- `can_trade=false`
- R28 forensic baseline remains immutable.
