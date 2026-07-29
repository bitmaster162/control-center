# Common Memory Contract R64

The system currently has several memory stores, but no single operator projection. R64 defines one contract.

## Layers

1. **Current / Hot** — `CURRENT_POINTER`, `CURRENT_STATE`, `ROLE_INDEX`, `ROLE_VIEWS`, active work orders.
2. **Episodic / Warm** — events, checkpoints, proof ledger, return bundles, decisions and run journals.
3. **Semantic** — entities, claims, evidence pointers, conflicts, supersession and confidence.
4. **Procedural** — work-order templates, verification recipes, policies, rollback and security playbooks.
5. **Cold / Source** — content-addressed source vault, archives and manifests.

## Required agent read set

Every agent must read, in order:

1. current pointer;
2. current state;
3. role index/view;
4. current return registry;
5. exact work order;
6. only cited predecessor evidence.

## Shared run state

```json
{
  "Plan": {},
  "Tasks": [],
  "Findings": [],
  "EvidencePointers": [],
  "Contradictions": [],
  "Budget": {},
  "RunStatus": "planned|running|blocked|complete"
}
```

## Write rules

- Events, decisions, proofs, returns and checkpoints are append-only.
- Current state is a projection from accepted events, not a second history.
- A claim records source, freshness, verification, scope and confidence.
- Duplicate content may have multiple provenance roles; hash equality alone does not authorize deletion.
- Missing discovery never authorizes rerun.
