# Deep Archive Provenance R28

## Physical scope

R28 re-audits the exact `handoff_recovery_local.zip` bytes rather than another narrative summary.

- ZIP size: `13310626` bytes
- ZIP SHA-256: `9a3b454b6686c5273a7b703e5e251a728bd3082bc6ca20d6116664e88bdc30fd`
- copied payload files: `99`
- candidates: `206`
- unique hashes: `121`
- duplicate occurrences: `85`
- unsafe/excluded rows: `23`
- collector errors: `0`

## New material findings

### 1. CopySafe is not SecretSafe

The source-effect receipt is valid within its narrow scope: the collector copied files and did not modify, move or delete source files. However, the copied payload includes credential-shaped literals that the collector did not detect.

- confirmed SSH password literal occurrences: `2`
- additional local/default credential-shaped occurrences requiring context review: `10`
- unique secret/literal fingerprints: `3`
- raw values reproduced in R28: `0`

Therefore:

```text
NO_SOURCE_EFFECT_PROOF: PASS within source-effect scope
NO_SECRET_CONTENT_PROOF: FAIL
SAFE_TO_DISTRIBUTE: DENY for raw package
```

### 2. The recovery corpus ingested prior recovery outputs

Three candidates came from earlier `HANDOFF_RECOVERY_*` runs. Two prior `HANDOFF_CANDIDATES.csv` files were copied into the new 99-file payload. This is recursive collector self-ingestion.

They remain useful as control/provenance evidence, but must not increase primary archive coverage or independent corroboration.

### 3. The 99-file count is a transport scope, not a primary-evidence denominator

R28 classifies the copied payload as:

```json
{
  "AGENT_RETURN": 24,
  "CONTROL_METADATA": 10,
  "DERIVATIVE_REPORT": 55,
  "PRIMARY_SOURCE": 4,
  "RECOVERY_SELF_DERIVATIVE": 2,
  "RESTRICTED_SECRET_BEARING": 2,
  "UNKNOWN": 2
}
```

The count `99` remains physically correct. It does not mean 99 independent primary sources, 99 current facts, or global archive completeness.

### 4. The status label is narrower than the population

`STATUS.json` labels all 23 unsafe rows as `excluded_pointer_only`, but `12` of those rows do not contain the reason `POINTER_ONLY_TYPE`. The field should be renamed to `excluded_or_unsafe_count`, with a reason-class breakdown.

### 5. Secret scanner coverage was incomplete

The collector scans only enumerated regexes and only fully scans text files up to 5 MiB. It detects assignments at the start of a line but missed password literals embedded in function arguments. A second scan of the copied payload is mandatory before any package is called safe for distribution.

## Corrected truth chain

```text
source-effect safe
≠ package-integrity safe
≠ secret-content safe
≠ safe to distribute
≠ accepted as current truth
```

## Archive consequence

The next archive depth comes from provenance/derivation and claim-specific evidence eligibility, not from raising the copied-file count. Source-001 chronology remains separate, and Wave 013 remains user-confirmed complete but physically unaccepted; no rerun is authorized.
