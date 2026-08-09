# Scope-Bound Completeness R26

## Required certificate

```json
{
  "scope_id": "...",
  "scope_manifest_sha256": "...",
  "numerator": 0,
  "denominator": 0,
  "coverage_ratio": "0/0",
  "evidence_ceiling": "...",
  "files": []
}
```

## Forbidden compression

Do not collapse:

- complete recovery candidate set → complete global archive;
- test/probe count → root-cause count;
- historical service observation → current liveness;
- filesystem folder → Git repository;
- legacy step number → Source-001 chronological rank.

## Status vocabulary

- `COMPLETE_WITHIN_SCOPE`
- `PARTIAL_WITHIN_SCOPE`
- `SCOPE_UNBOUND`
- `GLOBAL_COMPLETENESS_UNKNOWN`
