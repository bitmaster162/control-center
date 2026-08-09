# Dual-Frontier Archive Protocol R25

## Objective

Advance the oldest unresolved origin and the newest current evidence in the same bounded cycle.

## Cycle

```text
ORIGIN FRONTIER
oldest unresolved primary or source-adjacent item
        +
CURRENT FRONTIER
newest current report, receipt, source snapshot or operator correction
        ↓
exact hashes + byte signatures + version lineage
        ↓
origin intent / current physical truth / drift
        ↓
ADOPT | REVISE | HOLD | REJECT | UNKNOWN
        ↓
next cursors
```

## Mandatory checks

1. The origin and current items have exact file hashes.
2. Classification comes from bytes, not directory name.
3. Same-name/different-hash files receive a version lineage.
4. Derivative reports do not promote current state.
5. Metrics include scope, source layer, event time, unit and sample size.
6. Entity aliases map to stable IDs.
7. Security deferrals include owner, expiry and review trigger.
8. The cycle stops when neither frontier changes a decision, evidence gap, regression or product lineage.

## Human-native output

- what the origin intended;
- what is true now;
- what persisted;
- what drifted;
- the smallest next gate.

## AI-native output

- source IDs and hashes;
- content signatures;
- frontier cursors;
- version collisions;
- promotion/supersession records;
- regression candidates.
