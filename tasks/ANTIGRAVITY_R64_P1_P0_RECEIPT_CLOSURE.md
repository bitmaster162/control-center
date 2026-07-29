# ANTIGRAVITY-R64-P1 — P0 negative-test receipt closure

## Goal

Close D4 only with reproducible receipts. Do not repeat R63/R64 acceptance, workspace organization or HANRI D2 work.

## Start gate

- Read `contracts/p0-closure-receipt.schema.json` and all three templates.
- Reverify current exposure before changing anything.
- Preserve a compensating/break-glass path.
- Never print or store credential/token values.
- If lockout risk cannot be compensated, stop `OPERATOR_PRESENCE_REQUIRED`.

## P0-1 — Arena PostgreSQL

Required receipt observations:

1. listener is loopback-only;
2. connection from an external/separate context is `REFUSED` or times out;
3. old credential authentication is `DENIED`;
4. legitimate application continuity with new access is `PASS`;
5. new-access activation and old-access revocation timestamps are distinct and exact.

## P0-2 — leaked bearer token

Required:

1. old token request is `DENIED`;
2. authorized consumer succeeds with new token;
3. a declared-scope grep/artifact scan records zero old-token literals without exposing search values;
4. exact activation/revocation timestamps;
5. no unredacted token in receipts or logs.

## P0-3 — remote Administrator credential

Required:

1. new authorized access `PASS`;
2. old credential `DENIED`;
3. break-glass path `VERIFIED` before revocation;
4. legitimate remote administration continuity `PASS`;
5. exact activation/revocation timestamps.

## Acceptance

Validate each filled receipt against the JSON Schema. `RECEIPTED_CLOSED` is forbidden if any required negative test is `NOT_RUN` or `FAIL`, if timestamps are missing, or if evidence hashes are absent.

Deliver:

- `P0-1_CLOSURE.json`
- `P0-2_CLOSURE.json`
- `P0-3_CLOSURE.json`
- redacted evidence files and hashes
- validator receipt
- no-effect/continuity receipt
- strict broker triplet

No unrelated work, no new control generation, no secret values, no trading/capital effect.
