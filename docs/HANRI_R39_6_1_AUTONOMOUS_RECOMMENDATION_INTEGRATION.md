# HANRI R39.6.1 — Autonomous Recommendation Integration

## Purpose

R39.6.1 integrates the accepted R39.6 bounded recommendation compiler into the existing scheduler-owned R39 heartbeat without changing scheduler XML or execution authority.

Runtime chain:

```text
stable task action path
  -> R39.6.1 wrapper
      -> R39.5.1 core
          -> R39.4.1 core
              -> R39.3.3 core
          -> R39.5 improvement learning
      -> R39.6 bounded recommendations
```

The 5-minute Windows Task Scheduler heartbeat and the adaptive R39.3.3 full-attention cadence remain unchanged.

## Gating

R39.6 compilation is permitted only when:

- R39.5.1 integration receipt exists;
- policy is `39.5.1-autonomous-learning-integration-v1`;
- upstream status is `PASS`;
- `learning_pending=false`;
- upstream execution effects are zero;
- R39.5 learning state exists and has the accepted policy;
- R39.5 learning state execution effects are zero.

The R39.6 runner additionally verifies exact R39.5 learning receipt/state SHA binding, exact semantic-cycle binding, and the SHA of the R39.5 learning receipt recorded by R39.5.1.

## Execution decision

R39.6 is executed when any of these is true:

1. R39.5 learning executed on the current heartbeat;
2. a prior R39.6 pending marker exists;
3. R39.6 recommendation receipt is missing;
4. the recommendation receipt is stale relative to the current R39.5 `state_sha256`.

Unchanged learning state does not require recompilation. If recompilation occurs over an unchanged R39.5 digest, R39.6 itself remains deterministic and returns `NO_DELTA`.

## Failure semantics

Recommendation failure:

- does not alter scheduler configuration;
- does not apply a recommendation;
- writes `R39_6_1_RECOMMENDATION_PENDING.json`;
- returns a failed R39.6.1 integration receipt;
- retries on a later scheduler heartbeat;
- never reports disappearance as success.

Upstream R39.5.1 failure or `learning_pending=true` blocks R39.6 compilation and prevents ranking stale learning state.

## Recommendation authority

Every R39.6 recommendation remains:

- `PENDING_HUMAN_REVIEW`;
- `PROPOSAL_ONLY`;
- `execution_authority=NONE`;
- human decision required: `ACCEPT / REJECT / REVISE / HOLD`;
- no causation claim;
- no automatic generalization;
- no self-apply;
- no install authority;
- no system-write authority;
- no operator-message authority.

## Runtime refresh

Repository acceptance does not change the live host.

A live R39.6.1 integration requires a separate reversible staged-runtime refresh. The refresh:

1. preserves the stable scheduler task action path;
2. stages the current repository runtime;
3. transforms the wrapper chain so R39.5.1 becomes a core wrapper and R39.6.1 becomes the stable-path wrapper;
4. runs a full isolated staged preflight;
5. requires exact action-hash approval before applying;
6. acquires the existing R39.3.3 live lease;
7. swaps the runtime atomically;
8. rolls back on post-swap verification failure;
9. does not edit or trigger the scheduler.

After a successful refresh, acceptance as live still requires a natural scheduler-owned wake proof.

## Permanent effect boundary

- `proposal_only=true`
- `local_state_write_only=true`
- `provider_calls=false`
- `scheduler_install=false`
- `scheduler_modify=false`
- `human_decision_execution=false`
- `self_apply=false`
- `skill_install=false`
- `system_write=false`
- `operator_message=false`
- `auto_dispatch=false`
- `external_messages=false`
- `can_trade=false`
- `capital_permission=DENY`
