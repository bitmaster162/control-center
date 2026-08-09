# Collector Contract Correction R28

## Required collector V2 outputs

Every copied file must carry:

```text
artifact_id
source_path
payload_path
sha256
source_scope_id
collector_run_id
artifact_role
derivation_depth
primary_source_eligible
secret_scan_method
secret_scan_coverage
secret_fingerprint_count
```

## Required independent receipts

1. `NO_SOURCE_EFFECT_PROOF`
2. `PACKAGE_INTEGRITY_RECEIPT`
3. `NO_SECRET_CONTENT_PROOF` or `SECRET_QUARANTINE_RECEIPT`
4. `COVERAGE_AND_DERIVATION_CERTIFICATE`
5. `TARGET_READBACK_RECEIPT` when delivered

No receipt may satisfy another receipt's scope by implication.

## Recursive exclusion

The collector must exclude:

- its current OutputBase;
- every registered prior recovery output root;
- its own manifests, candidate ledgers and package copies unless explicitly collected as `CONTROL_METADATA`;
- any artifact with `derivation_depth > 0` from primary-source coverage.

## Secret scan

Run a second scan over copied bytes, not only source candidates. The scanner contract must publish:

- patterns/version;
- file-size coverage;
- binary/encoding limitations;
- findings by fingerprint only;
- quarantine disposition.

`COPY_SAFE` must never be rendered as `SAFE_TO_DISTRIBUTE`.
