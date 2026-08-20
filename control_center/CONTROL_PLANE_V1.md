# Control Center Control Plane V1

Date: 2026-08-11
Status: IMPLEMENTATION / NON-AUTHORITY PROJECTION

## Purpose

Control Center / Global Command is the operator-facing command plane for the multi-agent/project system. It is not merely a dashboard.

It owns:
- dispatch and accepted work-order intent;
- cross-project owner routing;
- semantic acceptance / hold / rejection of returns;
- human approval and effect-gate projection;
- current operational truth reduction;
- conflict and supersession tracking;
- portfolio/commercial prioritization;
- operator-facing current-control projection.

It does not take implementation ownership away from dedicated project owners.

## One operator surface

Robert should use one primary Control Center / Work Cockpit surface.

HANRI remains a separate technical owner/runtime with a technical subview and reciprocal evidence links:

`Control Center decision -> HANRI evidence`

`HANRI proposal/receipt -> Control Center adjudication`

A dashboard is always read-only projection and never the truth owner.

## Control loop

`ROBERT intent`
`-> Control Center routing / bounded work order`
`-> dedicated owner or executor`
`-> structured return`
`-> Return Broker transport verification / custody / ACK`
`-> Control Center semantic ACCEPT | HOLD | REJECT`
`-> exact human gate when required`
`-> bounded effect`
`-> independent readback`
`-> current-truth reduction`
`-> ContinuityOS durable checkpoint/replay`
`-> operator projection`

## Required state separation

Transport state:
`DISCOVERED -> STAGED -> VERIFIED -> DELIVERED -> ACKNOWLEDGED`
with `QUARANTINED` as a failure branch.

Semantic state:
`UNREVIEWED -> ACCEPTED | HOLD | REJECTED`

Apply state:
`NOT_APPLIED -> APPLIED`

Hard invariants:
- `RETURNED != ACCEPTED`
- `DELIVERED != APPLIED`
- Return Broker owns transport, never semantic acceptance/apply.
- Missing delivery never authorizes rerunning underlying work.
- Retry creates a new attempt, not a new logical return.
- Corrected return supersedes predecessor; it does not rewrite evidence history.

## Agent/work model

Every active work item must expose:
- `work_id`
- `project_id`
- `owner`
- `executor` when distinct
- exact bounded assignment
- work state
- effect class
- required human gate, if any
- current blocker/dependency
- next concrete action
- return expectation

Control Center may route work but must preserve one persistent writer / project-owner isolation.

## Operator projection views

V1 projection must support:
1. NOW — only items that need attention now.
2. AGENTS — active owner/executor assignment and state.
3. PROJECTS — owner, state, blocker, dependency, next gate.
4. WORK — bounded work orders and return expectations.
5. RETURNS — transport status separate from semantic/apply status.
6. DECISIONS — only genuine human decisions, with effect/readback lifecycle.
7. COMMERCIAL — the two active sellable lines and proof state.
8. HANRI — technical upstream status/evidence links, not duplicate authority.

## Current commercial lanes

Exactly two active sellable lines:
- Agent Authority & Evidence Audit — $4,900 primary scope.
- 7-Day Operator Decision Sprint — $199.

The internal self-pilot is dogfood and does not count toward the external MVP rule `3 of 5 named pilots pay $199 or renew`.

## Repository boundary

Files under `control_center/` are implementation contracts, tests and non-authority projections only.
They must not become `CURRENT_POINTER`, live authority roots, credentials, runtime databases or effect receipts.

## Safety ceiling

- `can_trade=false`
- `capital_permission=DENY`
- `deploy_permission=DENY`
- `self_application=false`
- no external message without Robert's exact SEND for that message;
- no self-approval;
- no self-merge;
- no self-deploy;
- no auto-successor work orders.
