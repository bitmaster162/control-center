# Control Center Sync Contract V2

Status: `REVIEW_BRANCH_ENGINEERING / NO CANONICAL APPLY`

## Purpose

Prevent current-truth projection drift by separating claim dimensions and forcing every visible current-state projection through one normalized snapshot.

## Logical planes

- `ROBERT / HUMAN_SOVEREIGN`
- `R64 CONTROL CENTER / GLOBAL COMMAND`: authority, approvals, effect authority, routing, adjudication.
- `HANRI`: subordinate runtime / attention / governor / recommendations / evidence.
- `ContinuityOS`: durable continuity / checkpoint / replay; no independent current-truth authority.
- `Return Broker`: deterministic transport/index/dedup; no semantic authority.
- project owners: bounded implementation lanes.

Physical repository sharing does not collapse these logical planes.

## Claim dimensions

Every mutable/current evidence record declares exactly one:

- `authority`
- `control_truth`
- `repository`
- `runtime`
- `slot_freshness`
- `strict_return`
- `projection`

A source authoritative for one dimension is not silently promoted to another.

Examples:
- GitHub provider can prove repository identity; not live host.
- operational closure/host readback can prove bounded runtime; not R64 authority.
- dashboard is a projection; never its own authority.
- historical strict return is evidence; not current slot freshness.

## Required evidence metadata

Every observation carries:

- `semantic_surface`
- `claim_dimension`
- `source_class`
- `source_id`
- `source_scope`
- `observed_at`
- `identity`
- `freshness`
- `claim_ceiling`
- `effect_authority`
- payload
- optional `supersedes[]`

`source_id` is immutable within one evidence set.

## Selection

Selection is dimension-specific.

Higher-authority source class wins before timestamp.
Within the same rank, later evidence wins.
Equal-priority/equal-time conflicting identities fail closed.
A newer lower-authority narrative does not replace a stronger provider source; it becomes a warning.

## Required current surfaces

- `r64.authority`
- `hanri.runtime`
- `hanri.repository`
- `hanri.projection`
- `collaboration.raw4ik`
- `continuityos.repository`
- `visionassist.custody`

Missing required surfaces fail closed.

## Projection contract

Exactly one normalized `CONTROL_CENTER_SNAPSHOT` feeds the renderer.

Separate axes:

- authority state/freshness
- repository state/freshness
- runtime state/freshness
- projection state/freshness
- agent slot freshness
- effect authority

Forbidden:
- footer/header says R36 while snapshot says R39.6.1.1;
- repo merge displayed as live host;
- multiple current collaboration objects;
- freshness lifting `DO_NOT_TOUCH`;
- dashboard citing itself as proof;
- provider HEAD advancing without projection becoming `STALE`.

A `STALE` projection may be rendered only with a visible stale label.
An invalid projection cannot be rendered.

## Current bounded semantics represented in the review fixture

- R64 remains active/resealed.
- HANRI live host proof: R39.6.1.1 bounded accepted-live lineage.
- HANRI accepted Git/evidence branch: repository identity separate from live host.
- CODEX-05: `DO_NOT_TOUCH`; freshness never lifts it.
- ContinuityOS:
  - R52 = historical local canonical code-adoption PASS.
  - R57 = later runtime-adoption preflight `REVISE`, `live_activation=false`.
  - modern public GitHub source is a separate freshness dimension.
- VisionAssist:
  - sanitized publication baseline independently verified;
  - owner transfer sent;
  - private GitHub custody still pending until remote receipt returns.
- Raw4ik issue remediation is owned by HANRI and is not duplicated by this slice.

## Write/effect guard

- read-only: allowed.
- GitHub review-branch code write: bounded engineering authority + fresh PR #30 readback.
- GitHub comment / external send: exact `SEND`.
- merge / Drive write / runtime mutation: separate exact effect gate.
- trading/capital: denied by current ceiling.

## CI

The review branch must run:

```text
python control_center/scripts/control_center_sync_v2.py --validate control_center/data/current_sync_evidence.review.v2.json
python control_center/scripts/test_control_center_sync_v2.py
```

No merge, deploy, Drive/root mutation, Return Registry mutation, runtime activation, trading/capital effect, or self-application is authorized by this contract.
