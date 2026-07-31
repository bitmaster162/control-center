# HANRI Control Center R64-P2

> **Classification:** implementation/dashboard patch only. Authority remains **R63 ACCEPTED**. This repository does not create or supersede a Control Center authority generation.

A contract-bound, read-only operator dashboard with repository-control projection for the HANRI / Control Center / ContinuityOS stack.

## Controller decisions applied

- R63 controller replay: `ACCEPTED`.
- R64 UI: canonical dashboard frame.
- R63 operator dashboard: merged into the `Audit` tab.
- FABLE-5: runtime/auditor, allowed to regenerate projections from verified sources.
- CODEX-01: read-only live adapters against snapshot contract v1.0.0.
- D4: remains `P0_CLAIMED_NOT_RECEIPTED` until three negative-test receipts validate.
- HANRI R64 governor: shadow/install-gated, no self-application and no automatic replacement of live R28.
- CONTROL_FREEZE: active; no new authority generation in this implementation patch.

## Truth surfaces

- **ArchiveOS** — long-term source memory: immutable sources, vault, archive closure.
- **ContinuityOS** — long-term operational state: checkpoints, replay, recovery, policy state.
- **HANRI R28** — live bounded supervisor runtime.
- **R64-P1** — dashboard and governor implementation candidate above those systems.

## Snapshot contract

Canonical payload:

```text
data/snapshot.json
```

Static-browser wrapper:

```text
data/snapshot.js
```

Schema and semantics:

```text
contracts/hanri-dashboard-snapshot.schema.json
contracts/SNAPSHOT_DATA_CONTRACT.md
```

Render invariant:

```text
RECEIPTED/HASH_VERIFIED + CURRENT + evidence refs → green
CLAIMED                                           → yellow / CLAIMED
UNKNOWN                                           → gray
CONFLICTED/REJECTED/open P0                       → red
STALE                                              → yellow override
```

No HTTP status, file existence or agent statement alone may render a system healthy.

## Repository control

Snapshot contract `1.1.0` adds an optional, evidence-bound `repositories` projection.
It distinguishes published Git branches, synced remotes, exported candidates,
non-Git source roots and runtime/data roots that must never be initialized blindly.

```bash
python scripts/normalize_repository_inventory.py EXPORT_SUMMARY.json data/repositories.generated.json
python scripts/validate_repository_inventory.py --inventory data/repositories.generated.json
```

Transport/readback does not equal content acceptance. Prefix-only commit IDs remain
`SOURCE_BACKED` and cannot authorize merge or push.

## Dashboard

Server mode:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Open:

```text
http://127.0.0.1:8764
```

Self-contained fallback:

```text
HANRI_R64_DASHBOARD_STANDALONE_CONTRACT_V1.html
```

The UI contains nine tabs:

1. Overview
2. Systems
3. Agents
4. Decisions
5. Common Memory
6. Agent Communication
7. P0 Security
8. Audit
9. Arbiter Content

## Deterministic generation

After editing `data/snapshot.json`:

```bash
python scripts/generate_snapshot_assets.py
```

This creates:

- `data/snapshot.js`
- `data/snapshot.sha256`
- the self-contained HTML

Identical JSON input produces byte-identical generated assets.

## Validation

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate_snapshot.py
python scripts/validate.py
python scripts/validate_repository_inventory.py
python -m pytest -q
node --check assets/app.js
```

## P0 closure

Schema and redacted templates:

```text
contracts/p0-closure-receipt.schema.json
templates/P0-1_CLOSURE.template.json
templates/P0-2_CLOSURE.template.json
templates/P0-3_CLOSURE.template.json
```

D4 cannot be closed from a batch-generated claim. Each P0 requires exact timestamps, negative tests, continuity proof and evidence hashes, without secret values.

## Current implementation tasks

Use the P1 tasks, not the earlier drafts:

- `tasks/CODEX01_R64_P1_CONTRACT_BOUND_LIVE_DASHBOARD.md`
- `tasks/ANTIGRAVITY_R64_P1_P0_RECEIPT_CLOSURE.md`
- `tasks/HANRI_R64_P1_SELF_IMPROVEMENT_GOVERNOR.md`

`CODEX07_R64_COMMON_MEMORY_EVENT_BUS.md` remains valid for shadow event-bus work.

## Effect ceiling

```text
can_trade=false
capital_permission=DENY
deploy_permission=DENY
self_application=false
```
