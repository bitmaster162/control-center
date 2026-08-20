# Control Center Control Plane V1

Date: 2026-08-11
Status: engineering contract / projection design, not live authority state

## Mission

Control Center is the operator-facing command and semantic-control plane for Robert's agent/project fleet.

It is not merely a dashboard. It owns the reduction from operator intent and agent evidence into current operational truth, bounded work, human gates, semantic acceptance and routed next actions.

## Core control loop

```text
ROBERT / OPERATOR INTENT
  -> CONTROL CENTER intake / normalize
  -> exact project owner + executor routing
  -> bounded work order / task contract
  -> isolated agent execution
  -> structured return
  -> RETURN BROKER transport / custody / dedup / ACK
  -> controller validation
  -> semantic adjudication: ACCEPT | REVISE | HOLD | REJECT
  -> exact human/effect gate when required
  -> current-truth reduction
  -> ContinuityOS event/checkpoint/replay record
  -> operator projection
```

## Control Center owns

1. Operator-intent intake and normalization.
2. Active-agent / owner / executor routing.
3. Bounded work-order and task-contract issuance when a real portfolio step requires one.
4. Cross-project concurrency and one-writer constraints.
5. Current operational truth and supersession/conflict resolution.
6. Human approval/gate state.
7. Semantic adjudication of exact returns against issued contracts.
8. Effect-authority projection and pre-dispatch deny/allow routing.
9. Portfolio/current-work prioritization.
10. Commercial proof/gate tracking for active sellable lanes.
11. Agent health / missing-return / stale-owner / blocked-lane detection.
12. Evolution of the Control Center itself: broker integration, controller contracts, operator cockpit, evidence links, stale-source detection and effect-boundary enforcement.

## Return Broker boundary

Return Broker is a transport/custody component, not the semantic authority.

Broker may own:
- discovery;
- staging;
- byte/hash/envelope verification;
- delivery;
- ACK;
- dedup/retry;
- quarantine;
- transport receipts.

Control Center alone performs semantic acceptance/rejection and routes apply/effect authority.

## HANRI boundary

HANRI is an upstream shadow governor / observer / evaluator.

HANRI may:
- observe current evidence;
- detect drift/conflicts;
- propose decisions;
- score/prioritize;
- isolate-test candidate logic;
- track effect/readback/closure evidence in its own product lane.

HANRI may not become Control Center authority, self-accept, self-dispatch or self-apply.

Control Center consumes HANRI output as evidence/proposals and reconciles it with other current sources.

## Operator surface: one primary cockpit

Robert should not need two equal dashboards.

Primary surface: **Control Center / Work Cockpit**.

Recommended top-level views:

1. `NOW` — current truth, top decisions, blockers, next actions.
2. `AGENTS` — agent/owner/executor slots, active work orders, returns, waiting/blocked state.
3. `PROJECTS` — portfolio lanes, owner, current phase, exact next gate.
4. `DECISIONS` — pending/accepted/rejected decisions and effect/readback lifecycle.
5. `RETURNS` — Return Broker transport state plus Control Center semantic state.
6. `COMMERCIAL` — Sprint/Audit proof, outreach gates, payments/pilots.
7. `HANRI` — embedded intelligence view / deep link into HANRI technical dashboard.
8. `EVIDENCE` — exact receipts, contradictions, supersession and provenance.

HANRI may keep a technical dashboard for its owner/debugging workflow, but the Robert-facing daily control surface is Control Center.

## Cross-link contract

Every Control Center decision derived from HANRI carries a `hanri_evidence_ref` / deep link.
Every HANRI proposal requiring action carries a `control_center_decision_ref` once reconciled.

Do not duplicate authority state between the two projections.

## Repository boundary

GitHub stores code, schemas, contracts, tests and deterministic projections.
It is not the live authority database.
Do not commit CURRENT_POINTER, mutable live decisions, credentials, private messages or production secrets.

## Hard invariants

- no self-approval;
- no self-merge;
- no self-deploy;
- no project-owner takeover;
- no external message without exact Robert SEND;
- no trading/capital effects;
- can_trade=false;
- capital_permission=DENY;
- deploy_permission=DENY;
- self_application=false.
