# CORE / BRAIN Candidate Delta R25

Status: `CANDIDATE / PROMPT-LEVEL + TESTED HANRI IMPLEMENTATION`

## CORE additions

### Bidirectional archive invariant
Every material archive cycle processes one origin frontier and one current frontier, or records why one side is exhausted.

### Byte-classification invariant
A path, filename or folder label cannot classify content. Classification requires a deterministic byte/text signature bound to SHA-256.

### Version-lineage invariant
Same-name files with different hashes are separate versions. Supersession is explicit; the filename never selects current truth.

### Coverage invariant
Completeness percentages require a manifest-bound per-file ledger. Aggregate counts without the ledger are `PASS_WITH_CONDITIONS`.

### Metric-scope invariant
Every metric binds `measurement_class`, `source_layer`, `event_time`, `unit`, `sample_size` and freshness. Paper/live/backtest/shadow values cannot be compared otherwise.

### Entity-identity invariant
A label such as Amora or Pandora is not an entity ID. Every project/product/company/runtime receives a stable ID and alias map.

### Security-debt invariant
Intentional deferral is not closure. Every deferred security control requires decision ID, owner, accepted risk, expiry and recheck trigger.

## BRAIN additions

New attention pattern:

```text
Origin Archivist
+ Current Steward
→ Bridge Auditor
→ smallest candidate delta
```

The system asks two questions together:

1. What did Robert originally mean and value?
2. What is physically true now?

Neither nostalgia nor current urgency is allowed to erase the other.
