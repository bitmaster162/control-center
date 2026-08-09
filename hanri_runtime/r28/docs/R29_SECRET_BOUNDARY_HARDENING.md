# HANRI R29 Candidate — Secret Boundary Hardening

Status: `CANDIDATE_ONLY / NOT_INSTALLED / NOT_MERGED`

Baseline:

- commit: `e8a1d944dec01a21bf43a3075b8b11fe1920fcd3`
- tree: `2c1f27b2c4e234d7e2afcb4d190fda54aa027563`
- runtime baseline: HANRI R28.0.0

## Problem

R28 already classifies `SECRET_SCANNER_COVERAGE_GAP` as CRITICAL, but the runtime sanitizer primarily recognizes vendor/token formats. Credential values embedded in contextual forms can survive unless they happen to match those formats.

Examples covered by R29 candidate:

- structured fields such as `password`, `client_secret`, `api_key`, `access_token`;
- function or text assignments such as `password="..."`;
- JSON-like assignment text;
- `Authorization: Bearer ...`;
- DSN credentials such as `scheme://user:password@host`.

## Change shape

R29 does not rewrite the verified R28 core. `guarded_cli.py` wraps the existing command entrypoint and replaces only the runtime `sanitize` binding before R28 command execution.

This keeps rollback bounded: restoring `__main__.py` to import `main` from `.cli` removes the candidate guard without touching the R28 core implementation.

Only secret fingerprints are retained:

- classification kind;
- SHA-256 of the raw secret value;
- guard source marker.

Raw credential values are not written to findings.

## Regression gate

`tests/test_secret_boundary_r29.py` covers:

1. sensitive dictionary keys;
2. password function arguments;
3. JSON-like `client_secret` assignments;
4. Bearer authorization values;
5. DSN passwords;
6. preservation of R28 vendor-token redaction;
7. explicit redaction markers;
8. non-secret text stability.

## Authority / effect boundary

- no runtime installation;
- no merge to the repository default branch;
- no external model/API calls;
- no credential rotation;
- no production state mutation;
- `self_application=false`;
- `can_trade=false`.

Promotion requires provider-side CI/test evidence, diff review, explicit human/control approval, bounded install, independent runtime readback, and rollback receipt.
