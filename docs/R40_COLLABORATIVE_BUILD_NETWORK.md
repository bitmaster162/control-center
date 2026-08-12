# HANRI R40 — Collaborative Build Network (GitHub Free)

## Status

Engineering/governance candidate only. This document does not authorize merge, deployment, provider writes, runtime changes, self-application, TradingOS changes, trading, or capital effects.

## Problem

The canonical repository `bitmaster162/control-center` is private and owned by a personal GitHub account. On GitHub Free, private-repository collaborators have write access to that repository, while protected branches/rulesets for private repositories require a paid plan. R40 therefore MUST NOT depend on branch protection that is unavailable on the current plan.

## Free isolation architecture

Use two private repositories:

1. **Canonical / sovereign:** `bitmaster162/control-center`
   - Robert remains the only collaborator required for canonical writes.
   - Accepted/runtime branches remain here.
   - No friend/collaborator access is required.
   - All promotion into canonical remains explicitly reviewed and approval-gated.

2. **Collaboration gateway:** `bitmaster162/control-center-collab`
   - Separate private repository on GitHub Free.
   - Friend receives collaborator access only to this repository.
   - Working branches use `collab/<github-user>/<lane>`.
   - No secrets, provider credentials, host-local receipts, stable Control Center roots, private operator communications, or trading/capital authority are copied into this repository.

This repository split is the enforcement boundary when paid branch protection is unavailable: collaborator write authority exists only in the collaboration repository, not in canonical.

## Export boundary

Only an explicitly prepared collaboration bundle may cross from canonical to the collaboration gateway. The bundle MUST be allowlist-based and MUST NOT be a full mirror of canonical.

Allowed by default:
- source code required for the assigned lane;
- public/non-secret tests and fixtures;
- minimal interface contracts required to build the lane;
- sanitized README/onboarding material;
- synthetic/example snapshot data;
- branch/base provenance using commit/tree identities.

Denied by default:
- `.env`, credentials, tokens, keys, cookies, provider secrets;
- private Google Drive content or stable Control Center roots;
- host-local receipts/logs that contain machine/user/private paths unless sanitized;
- private operator messages or contact data;
- production deployment credentials;
- TradingOS runtime state or trading/capital permission material;
- any artifact whose sharing authority is not explicit.

## Build flow

```text
canonical accepted baseline
        |
        | sanitized/export-approved bundle
        v
control-center-collab
        |
        +--> collab/<friend>/<lane>
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

A commit/PR merged in `control-center-collab` is **not** accepted canonical state. It is a proposal/evidence source only. Canonical acceptance requires an independent import/review step and the existing sovereign merge/effect gates.

## Dashboard projection

The dashboard Build Network view may show:
- canonical accepted baseline HEAD/tree;
- collaboration repository setup state;
- collaborator identity once explicitly supplied;
- active `collab/*` lanes;
- PR/CI/review state;
- return-import state;
- direct links to GitHub resources accessible to the viewer.

The dashboard MUST remain read-only. It MUST NOT contain GitHub tokens or provider credentials and MUST NOT perform merges, pushes, approvals, deployments, or external effects from browser JavaScript.

Until `control-center-collab` exists and a collaborator identity is explicitly bound, the dashboard MUST render `SETUP_REQUIRED` rather than pretending collaboration is live.

## Current plan constraints

- GitHub plan dependency: **GitHub Free compatible**.
- Private canonical branch protection: unavailable without paid plan; not relied upon.
- Collaboration repo: private.
- Canonical collaborator access for friend: not required and not recommended under the current plan.

## Invariants

- canonical authority remains R64;
- no new authority generation is created by R40;
- recommendation/proposal != approval;
- collab merge != canonical acceptance;
- `self_application=false`;
- `can_trade=false`;
- `capital_permission=DENY`;
- TradingOS `DO_NOT_TOUCH`.
