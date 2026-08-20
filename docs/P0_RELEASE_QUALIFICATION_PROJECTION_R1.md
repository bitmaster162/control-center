# P0 RELEASE QUALIFICATION PROJECTION R1

Status: DRAFT CANDIDATE / NON-AUTHORITY / NO EFFECT

Control Center may display the TradingOS P0 release-qualification receipt only through:

`control_center.shadow_p0_release_qualification_projection.v1`

The projection requires the exact externally retained `release_qualification_sha256` and verifies that the upstream receipt remains:

- `P0_RELEASE_CANDIDATE_QUALIFIED_WITH_CONDITIONS`;
- `decision=HOLD`;
- `action=WAIT`;
- architecture closed only for candidate review;
- production/release/merge/deploy/runtime readiness all false;
- current-truth promotion false;
- semantic acceptance not performed;
- execution authority none;
- trading false and capital denied.

The projection is deliberately:

`NON_AUTHORITY_P0_RELEASE_QUALIFICATION_PROJECTION`

It creates zero effect candidates and authorizes zero executions. It cannot make the candidate current truth, merge-ready, deploy-ready, runtime-ready, or trading-capable.

The retained TradingOS qualification receipt for the frozen R1→R9 snapshot has SHA-256:

`9938c0c0f110e2309a08f5231ce976f6a4c65a57e7e9581b9f4fd95c69e1a6c2`

The underlying candidate manifest SHA-256 is:

`653660ea74d0401f4934dca7c250611937f98c0015fe136f4a1b9998ed28dacb`

Evidence ceiling: a verified release-qualification projection is a review artifact, not release authority.

Fixed ceiling: `apply=false`, `current_truth_write=false`, `human_gate_write=false`, `lease_registry_write=false`, `commit_receipt_registry_write=false`, `backend_write=false`, `runtime_activation=false`, `executor_dispatch=false`, `external_message=false`, `signal=false`, `order=false`, `can_trade=false`, `capital_permission=DENY`.
