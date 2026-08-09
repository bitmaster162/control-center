# HANRI R28 Architecture Delta

R28 adds a recovery-provenance audit to the existing causal truth kernel.

```text
collector candidate
→ physical copy
→ artifact role
→ derivation depth
→ copied-byte secret scan
→ proof-scope separation
→ claim-specific evidence admission
→ human decision
```

New deterministic failure classes:

- `RECOVERY_SELF_INGESTION`
- `CONTENT_SECRET_SAFETY_FALSE_CLAIM`
- `CONTROL_ARTIFACT_COVERAGE_INFLATION`
- `PROOF_SCOPE_CONFLATION`
- `UNSAFE_ROW_LABEL_MISMATCH`
- `SECRET_SCANNER_COVERAGE_GAP`

R28 does not repair the collector automatically and never self-applies candidate deltas.
