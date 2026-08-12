# HANRI R39.6 — Bounded Improvement Recommendations

## Status and scope

R39.6.0 compiles verified R39.5 improvement-learning evidence into deterministic human-review recommendation packets. It is a repository/shadow layer only. It does not install, schedule, deploy, send messages, mutate production systems, or change HANRI authority.

Source contract:

- exact `39.5.0-improvement-learning-v1` state;
- valid source `state_sha256`;
- proposal-only/local-state-only effect boundary;
- `execution_effects_performed=0`.

Output policy:

- `39.6.0-bounded-improvement-recommendations-v1`;
- every emitted packet is `PENDING_HUMAN_REVIEW`;
- every packet requires one of `ACCEPT / REJECT / REVISE / HOLD`;
- `execution_authority=NONE`;
- `self_apply_authorized=false`;
- `install_authorized=false`;
- `system_write_authorized=false`;
- `operator_message_authorized=false`;
- causation is not claimed;
- generalization is not authorized.

## Recommendation compiler

R39.6 consumes R39.5 ranked patterns in rank order and emits packets only for:

1. `CRITICAL_CORRECTIVE_REVIEW`
2. `HIGH_CORRECTIVE_REVIEW`
3. `EVIDENCE_COLLECTION`
4. `BOUNDED_REINFORCEMENT_REVIEW`

`MONITOR_MORE_EVIDENCE` does not produce change advice.

Allowed review actions:

- `ATTENTION_RULE_REVIEW`
- `SKILL_CANDIDATE_REVIEW`
- `SYSTEM_IMPROVEMENT_REVIEW`
- `OPERATOR_ADVICE_REVIEW`
- `HANRI_RECOMMENDATION_RULE_REVIEW`
- `REINFORCEMENT_REVIEW`
- `OUTCOME_EVIDENCE_COLLECTION`

Recommendation IDs are stable over `{domain, kind, review_action}`. Repeated execution over the same R39.5 `learning_digest` is `NO_DELTA` and does not inflate history.

## Zero-evidence rule

When R39.5 has zero ranked improvement items, R39.6 emits zero recommendation packets and returns `NO_RECOMMENDATIONS_YET`.

HANRI must not invent advice, change proposals, confidence, or success from absence of explicit outcome evidence.

## Domain mapping

- SELF findings may produce attention-rule or HANRI recommendation-rule review.
- AGENT findings may produce skill-candidate review plus HANRI recommendation-rule review.
- SYSTEM findings may produce bounded system-improvement review.
- OPERATOR findings may produce optional operator-advice review.
- Outcome debt produces evidence-collection packets only.
- Repeated verified improvement may produce bounded reinforcement review only; automatic generalization remains forbidden.

## Verification and adoption

A recommendation packet describes a proposed review and an isolated verification plan. The packet is not an effect candidate and is not executable authority.

Any future adoption must be separately reviewed, isolated-tested, and explicitly approved under the relevant effect-governance path.

R39.6.1, if implemented, may integrate this compiler into the live R39.5.1 heartbeat sidecar. Because that changes the staged live runtime, it requires a fresh runtime-refresh PLAN and a new exact host-effect approval. R39.6.0 itself authorizes no host effect.

## Safety boundary

Always:

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
