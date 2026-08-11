# Control Center owner boundary

Date: 2026-08-11

This branch is the dedicated engineering lane for the Control Center / current operational truth plane.

## Owns

- current operational truth projections;
- accepted intents and human gates;
- conflict and supersession tracking;
- project ownership and routing;
- portfolio/current-work board;
- effect-authority projection;
- return adjudication against exact issued contracts;
- deterministic Control Center dashboard/projection improvements.

## Does not own

- HANRI implementation or `hanri/*` owner branches;
- ContinuityOS development;
- TradingOS;
- BitEvo public-site implementation;
- BitEvo Core implementation;
- NFT bot or VisionAssist implementation.

HANRI output is upstream evidence/proposals/readback for Control Center reconciliation, not a branch to take over.

## Current parallel portfolio lanes

1. 7-Day Operator Decision Sprint — bounded manual paid validation; MVP: 3/5 named pilots pay $199 or renew.
2. Agent Authority & Evidence Audit — sales lane; external outreach remains gated until BitEvo public production proof and explicit Robert SEND per message.
3. BitEvo public — separate site-owner branch; promotion remains separate human gate.
4. BitEvo Core — separate Future Runtime/Core owner flow; source/runtime custody before canonical GitHub implementation.
5. Security/P0 closure — HANRI/host evidence lane; Control Center ingests/adjudicates receipts rather than duplicating execution.

## Repository/effect rules

- Repository projections are not live authority state.
- No self-approval, self-merge or self-deploy.
- No external message without exact Robert SEND.
- No trading or capital effects.
- `can_trade=false`
- `capital_permission=DENY`
- `deploy_permission=DENY`
- `self_application=false`
