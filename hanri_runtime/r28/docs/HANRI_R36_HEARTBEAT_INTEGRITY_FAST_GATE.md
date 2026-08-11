# HANRI R36 — Heartbeat Integrity Fast Gate

## Status

Engineering candidate only. This document does not authorize install, cutover, promotion, self-application, external messaging, trading, or capital effects.

Accepted parent runtime:

- branch: `hanri/r35-accepted-runtime`
- HEAD: `4e8c5bd68f5159c55ff604e8b4a9dbcbf4031b50`
- tree: `75f2508265ec00248747c59e3e06bd222ef9a483`
- runtime: HANRI R35 / `35.0.0`

## Observed bottleneck

The accepted R35 no-delta heartbeat receipt reports:

- `fast_path_total_observed_ms = 151.739`
- `heavy_snapshot_integrity_elapsed_ms = 120.945`
- `heavy_snapshot_bytes_hashed = 33558254`
- integrity mode `STREAMING_SHA256_NO_JSON_PARSE`

The heavy SHA pass therefore accounts for about 79.7% of the observed no-delta heartbeat wall time.

## Candidate delta

R36 keeps the existing cryptographic SHA checkpoint as the source of truth but avoids re-reading every heavy snapshot on every unchanged heartbeat.

After a full verified SHA pass, the projection receipt also stores a bounded metadata checkpoint for each heavy file:

- exact filename set;
- byte size;
- `mtime_ns`;
- timestamp of the last full SHA verification.

On an otherwise eligible no-delta heartbeat:

1. validate the existing SHA checkpoint and heavy-file set;
2. compare current stat metadata to the last full-verified stat checkpoint;
3. require the last full SHA verification to be younger than the bounded rehash interval;
4. if all checks match, reuse the prior SHA checkpoint without hashing the heavy bytes;
5. otherwise perform the full streaming SHA pass immediately;
6. any SHA mismatch fails closed to the inherited full-processing path.

The full rehash interval defaults to 900 seconds and is capped by the enabled archive scan cadence. It may not be lower than 60 seconds.

## Security model

`CACHED_STAT_GUARD` is not presented as equivalent to a fresh full hash. It is a bounded freshness optimization backed by a prior cryptographic checkpoint and mandatory periodic full verification.

A same-size content modification that can also restore the exact observed metadata could evade the cache gate only until the next forced full SHA pass. The maximum intended exposure window is therefore the bounded rehash interval, normally at most the archive scan cadence.

Ambiguous or incomplete checkpoint state never silently becomes trusted:

- missing stat checkpoint -> full SHA refresh;
- changed stat checkpoint -> full SHA refresh;
- missing/invalid verification timestamp -> full SHA refresh;
- rehash interval due -> full SHA refresh;
- clock rollback -> full SHA refresh;
- SHA mismatch -> fail closed.

## Receipt fields

The candidate adds or maintains:

- `heavy_snapshot_raw_sha256`
- `heavy_snapshot_stat_checkpoint`
- `heavy_snapshot_full_verified_at`
- `heavy_snapshot_full_sha_performed`
- `heavy_snapshot_integrity_mode`
- `heavy_snapshot_bytes_hashed`
- `heavy_snapshot_integrity_elapsed_ms`
- `heavy_snapshot_integrity_cache_age_seconds`
- `heavy_snapshot_integrity_refresh_reason`
- `heavy_snapshot_full_rehash_interval_seconds`

A valid cached heartbeat reports:

- `heavy_snapshot_integrity_mode = CACHED_STAT_GUARD`
- `heavy_snapshot_full_sha_performed = false`
- `heavy_snapshot_bytes_hashed = 0`

A refresh heartbeat reports:

- `heavy_snapshot_integrity_mode = STREAMING_SHA256_NO_JSON_PARSE`
- `heavy_snapshot_full_sha_performed = true`
- a non-null refresh reason.

## Acceptance gates

Engineering acceptance requires:

1. all existing repository tests remain green;
2. unchanged stat checkpoint within TTL performs zero heavy SHA calls;
3. stat drift forces full SHA;
4. tampered bytes fail closed;
5. missing cache rebuilds with full SHA;
6. TTL expiry forces full SHA;
7. clock rollback forces full SHA;
8. rehash interval cannot exceed active archive scan cadence;
9. no network/model calls, subprocess execution, self-application, trading, capital or production-deploy authority is added.

## Effect boundary

- candidate branch / tests / draft PR: allowed;
- accepted R35 branch mutation: forbidden;
- runtime install/cutover: not authorized here;
- merge/promotion: separate human gate;
- `self_application=false`;
- `can_trade=false`;
- `capital_permission=DENY`;
- TradingOS: `DO_NOT_TOUCH`.
