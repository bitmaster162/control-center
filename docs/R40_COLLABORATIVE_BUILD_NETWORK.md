# HANRI R40 — Collaborative Build Network (GitHub Free)

## Status

Engineering/governance candidate only. The separate collaboration gateway is provider-verified, sanitized baseline is merged there, and gateway state is `READY_WAITING_COLLABORATOR`. Collaborator identity is still pending. This document does not authorize canonical merge, dashboard deployment, runtime changes, self-application, TradingOS changes, trading, or capital effects.

## Verified gateway state

- repository: `bitmaster162/control-center-collab`
- repository ID: `1332081436`
- visibility: `private`
- final main HEAD: `25c59fb1a564d313c93028d9795592bcabdbc976`
- final main tree: `5cd156dbb5a6233f6855319f2286b895227e142d`
- final main signature: `UNSIGNED` (provider-verified identity; not authority)
- safe baseline branch: `upstream/r64-safe-baseline`
- safe baseline HEAD: `2811e3aaa80c8f86e175653d45144d6b1d76b8d7`
- baseline review PR: `control-center-collab#1`
- baseline review merge: `ad3d33994f5608c5d77505e77a8136abafbd5436`
- additive ready receipt: `GATEWAY_READY_RECEIPT.json`
- collaborator: pending / not yet bound
- collaboration_live: false
- state: `READY_WAITING_COLLABORATOR`

The collab repository is intentionally not a full mirror. Live snapshot/provider data, stable Control Center roots, runtime state, private operator material and TradingOS content are excluded.

## Free isolation architecture

Two private repositories are used because the current GitHub Free setup does not rely on paid private-repository branch protection/rulesets.

1. **Canonical / sovereign:** `bitmaster162/control-center`
   - accepted/runtime branches remain here;
   - collaborator write access is not required;
   - all import/promotion remains separately reviewed and exact-gated.

2. **Collaboration gateway:** `bitmaster162/control-center-collab`
   - external collaborator will receive access only here;
   - work branches use `collab/<github-user>/<lane>`;
   - collab commits/PRs are proposal/evidence artifacts only.

The repository split is the enforcement boundary: collaborator write authority does not extend into canonical.

## Export boundary

Only allowlist-controlled material may cross from canonical into collab. Full history mirroring is denied by default.

Allowed classes:
- source required for the assigned lane;
- non-secret tests/fixtures;
- minimal interface/data contracts;
- sanitized onboarding/build documentation;
- synthetic/example projection data;
- branch/base provenance using commit/tree identities.

Denied classes:
- `.env`, credentials, tokens, keys, cookies, provider secrets;
- live provider IDs unless explicitly required and separately approved;
- private Drive corpus or stable Control Center roots;
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

A commit or PR merged in `control-center-collab` is **not** accepted canonical state. The merged baseline is `COLLAB_REVIEW_ACCEPTED` only. Canonical acceptance still requires an isolated import/review step plus sovereign merge/effect gates.

## Dashboard Build Network projection

The Build Network view may show:
- canonical accepted HEAD/tree;
- collab repository HEAD/tree and ready receipt;
- safe-baseline branch/HEAD;
- collaborator identity after explicit binding;
- active `collab/*` lanes and PR/CI/review state;
- return-import state;
- direct GitHub links accessible to the viewer.

The dashboard remains read-only. It must not contain GitHub tokens/provider credentials or perform merges, pushes, approvals, deployments, or provider effects from browser JavaScript.

Until a real collaborator identity is provider-verified, the correct state is `READY_WAITING_COLLABORATOR`, not `LIVE_COLLABORATION`.

## Canonical anchor

- authority generation: `R64`
- accepted branch: `hanri/r37-product-pilot-accepted`
- accepted HEAD: `4dac1a46270ed45bc6c87e2e43448209d3b23f64`
- accepted tree: `78d346ca88b61346380d58e6f4e63c10e4db7ade`
- R39.6.1.1 runtime: `CLOSED / ACCEPTED_LIVE`

## Invariants

- no new authority generation created by R40;
- recommendation/proposal != approval;
- collab merge != canonical acceptance;
- direct collaborator-to-canonical write = false;
- automatic canonical sync = false;
- `self_application=false`;
- `can_trade=false`;
- `capital_permission=DENY`;
- TradingOS `DO_NOT_TOUCH`.
