# HANRI R40 — Collaborative Build Network (GitHub Free)

## Status

Engineering/governance candidate only. The collaboration gateway is now provider-verified and bootstrapped; collaborator identity is still pending. This document does not authorize canonical merge, dashboard deployment, runtime changes, self-application, TradingOS changes, trading, or capital effects.

## Verified gateway state

Provider-verified collaboration repository:

- repository: `bitmaster162/control-center-collab`
- repository ID: `1332081436`
- visibility: `private`
- plan dependency: GitHub Free compatible
- main HEAD after bootstrap: `3a22ea5422e61d2ddba6e5469b75f1507302e8a7`
- safe baseline branch: `upstream/r64-safe-baseline`
- safe baseline HEAD: `2811e3aaa80c8f86e175653d45144d6b1d76b8d7`
- collaborator: pending / not yet bound
- state: `BOOTSTRAPPED_WAITING_COLLABORATOR`

The safe baseline is not a full canonical mirror. It contains collaboration policy/provenance and a sanitized Build Network starter. Live projection data, provider IDs, stable roots, runtime state and TradingOS material are intentionally excluded.

## Problem

The canonical repository `bitmaster162/control-center` is private and owned by a personal GitHub account. On the current GitHub Free setup, R40 does not rely on paid private-repository branch protection/rulesets. Instead, collaborator write authority is physically isolated in a second private repository.

## Free isolation architecture

Use two private repositories:

1. **Canonical / sovereign:** `bitmaster162/control-center`
   - accepted/runtime branches remain here;
   - collaborator access is not required;
   - promotion into canonical remains independently reviewed and approval-gated.

2. **Collaboration gateway:** `bitmaster162/control-center-collab`
   - external collaborator receives access only here once identity is supplied;
   - working branches use `collab/<github-user>/<lane>`;
   - collaboration commits/PRs are proposal/evidence artifacts only.

This repository split is the enforcement boundary: collaborator write authority does not extend into canonical.

## Export boundary

Only allowlist-controlled material may cross from canonical into the collaboration gateway. A full history mirror is denied by default.

Allowed classes:
- source code required for the assigned lane;
- non-secret tests and fixtures;
- minimal interface/data contracts;
- sanitized onboarding/build documentation;
- synthetic/example projection data;
- branch/base provenance using commit/tree identities.

Denied classes:
- `.env`, credentials, tokens, keys, cookies, provider secrets;
- live provider IDs unless explicitly required and separately approved;
- private Google Drive corpus or stable Control Center roots;
- host-local runtime state/receipts containing private machine data;
- private operator communications/contact data;
- production deployment credentials;
- TradingOS implementation/runtime state or trading/capital authority.

## Build flow

```text
canonical accepted baseline
        |
        | allowlist + scrub
        v
upstream/r64-safe-baseline  (control-center-collab)
        |
        +--> collab/<github-user>/<lane>
        |       |
        |       +--> commits/tests
        |       +--> collab PR/review
        |
        v
reviewed return patch / commit set
        |
        | independent diff + tests + provenance
        v
new isolated canonical candidate branch
        |
        +--> canonical PR
        +--> CI
        +--> exact human merge gate
        v
accepted canonical state
```

## Non-equivalence rule

A commit or PR merged in `control-center-collab` is **not** accepted canonical state. It is proposal/evidence only. Canonical acceptance requires a new isolated import/review step plus the existing sovereign merge/effect gates.

## Dashboard Build Network projection

The Build Network view may show:
- canonical accepted HEAD/tree;
- verified collaboration repository and safe-baseline HEAD;
- collaborator identity after explicit binding;
- active `collab/*` lanes;
- PR/CI/review state;
- return-import state;
- direct GitHub resource links accessible to the viewer.

The dashboard remains read-only. It must not contain GitHub tokens/provider credentials or perform merges, pushes, approvals, deployments, or provider effects from browser JavaScript.

Current display state must be `BOOTSTRAPPED_WAITING_COLLABORATOR`, not `SETUP_REQUIRED` and not `LIVE_COLLABORATION`, until a real collaborator identity is provider-verified.

## Canonical anchor

- authority generation: `R64`
- accepted branch: `hanri/r37-product-pilot-accepted`
- accepted HEAD: `4dac1a46270ed45bc6c87e2e43448209d3b23f64`
- accepted tree: `78d346ca88b61346380d58e6f4e63c10e4db7ade`
- R39.6.1.1 runtime: `CLOSED / ACCEPTED_LIVE`

## Invariants

- no new authority generation is created by R40;
- recommendation/proposal != approval;
- collab merge != canonical acceptance;
- direct collaborator-to-canonical write = false;
- automatic canonical sync = false;
- `self_application=false`;
- `can_trade=false`;
- `capital_permission=DENY`;
- TradingOS `DO_NOT_TOUCH`.
