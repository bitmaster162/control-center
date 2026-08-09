# CORE / BRAIN Candidate Delta R28

Status: `CANDIDATE / PROMPT-LEVEL ONLY`

## CORE additions

### 1. Proof-scope isolation

```text
NO_SOURCE_EFFECT_PROOF
≠ NO_SECRET_CONTENT_PROOF
≠ PACKAGE_INTEGRITY
≠ TARGET_EFFECT_RECEIPT
```

A valid narrow receipt cannot be promoted into a broader guarantee.

### 2. Recovery derivation

Every recovered artifact binds `artifact_role + derivation_depth + collector_run_id`.
Collector outputs may be retained as control evidence but cannot count as new primary evidence.

### 3. CopySafe boundary

`COPY_SAFE` means source bytes were copied without source mutation under the recorded operation. It does not mean secret-free, authoritative, current, or safe to distribute.

### 4. Archive coverage

Report at least four independent counts:

- physical occurrences;
- unique hashes;
- independent evidence families;
- primary-source eligible items.

### 5. Negative-claim and rerun control

Wave 013 remains `COMPLETED_USER_CONFIRMED / PHYSICAL_INGESTION_PENDING`; the system searches all registered surfaces and never reruns first.

## BRAIN additions

New reflex:

```text
RECOVERED
→ classify role and derivation
→ scan copied bytes
→ isolate proof scopes
→ quarantine secrets
→ admit claim-specific evidence
```

The controller must prefer a smaller truthful denominator over a larger mixed corpus count.
