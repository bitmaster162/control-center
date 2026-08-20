# P0 R4 Domain History Projection

Status: DRAFT / REVIEW-ONLY / NO EFFECT

Control Center R4 consumes only `bitevo.shadow_domain_history_closure.v1` after TradingOS has bound the generic R3 history to exact domain artifacts.

Required upstream guarantees:

- exact R3 history verification hash;
- exact R4 subject manifest hash;
- exact R4 domain subject verification hash;
- exact ContinuityOS admission candidate hash;
- admission replay input equals the CASE_QUALIFIED subject;
- all six lifecycle subjects are bound;
- no history write or semantic acceptance;
- no execution authority.

Control Center emits only:

`control_center.shadow_domain_history_projection.v1`

with:

```text
projection_kind=NON_AUTHORITY_DOMAIN_HISTORY_PROJECTION
domain_subject_integrity=VERIFIED_SHADOW_ONLY
admission_integrity=VERIFIED_SHADOW_ONLY
current_truth_promotion_allowed=false
apply=false
```

All mutations remain false:

```text
current_truth
command_queue
decision_ledger
return_registry
human_gate
runtime
trading
capital
```

R4 therefore allows the operator UI/control layer to display that domain-history binding was verified while preserving the distinction:

```text
verified history
!= semantic acceptance
!= human identity signature
!= current truth
!= permission
!= effect
```

The first-class human reveal receipt is still only a deterministic content-bound reveal artifact. Without separate trusted capture/signature/custody evidence, it does not prove physical human identity or intent authenticity.

Fixed P0 ceiling remains `execution_authority=NONE`, `can_trade=false`, `capital_permission=DENY`, no merge/deploy/runtime/trading/capital effect.
