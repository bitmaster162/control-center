# HANRI R39.3.1 — Semantic Delta Repair

## Host finding

The first accepted R39.3 host cycle initialized correctly. A second immediate host wake with unchanged coverage, findings, proposals and source counts incorrectly returned `SEMANTIC_DELTA` and incremented `semantic_cycle_count` from 1 to 2.

Root cause: R39.1 `envelope_sha256` included `observed_at`. Producer artifacts without a source-native timestamp use the wake time as fallback, so identical source bytes acquired a different envelope SHA on every wake. R39.3 used those hashes as semantic evidence identity.

## Repair

R39.3.1 introduces `SEMANTIC_ENVELOPE_V2`.

Semantic identity includes:
- envelope_id
- source_type
- producer
- subject_id
- evidence_refs
- payload

It excludes volatile `observed_at`. The timestamp remains available as metadata but cannot by itself create semantic change.

A real payload/source identity change still changes the semantic envelope SHA and therefore produces `SEMANTIC_DELTA`.

## State lineage

R39.3.0 state is not silently reinterpreted. V2 uses separate `continuous_state_v2`, `continuous_work_v2`, and `continuous_receipts_v2` roots. The legacy state remains forensic evidence of the detected defect.

## Acceptance

Two consecutive real-host V2 wakes over unchanged source bytes must produce:
1. `INITIALIZED`, wake 1, semantic cycle 1;
2. `NO_DELTA`, wake 2, semantic cycle still 1;
3. identical `EVIDENCE_SET_SHA256` across both wakes.

Regression tests also require proposal identity to remain stable when only `observed_at` changes, while payload changes still produce a semantic delta.

## Effect boundary

No scheduler install, provider call, human-decision execution, self-apply, skill install, system write, operator message, auto-dispatch, external message, TradingOS or capital effect is authorized. `can_trade=false`; `capital_permission=DENY`.
