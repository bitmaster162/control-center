# HANRI Control Center Snapshot Data Contract v1.0.0

**Classification:** R64 implementation contract. It does not create or supersede an authority generation. Authority remains R63.

## Purpose

`data/snapshot.json` is the canonical machine-readable dashboard projection. `data/snapshot.js` is a deterministic wrapper generated from the same JSON for static-browser compatibility. Neither file is an authority source; both are read-only projections of verified sources.

## Required pipeline

```text
verified sources
→ deterministic adapters
→ snapshot.json
→ JSON Schema validation
→ snapshot.js wrapper
→ dashboard / standalone HTML
```

A live adapter may update the projection, but it must never mutate Control Center, ContinuityOS, HANRI, Return Broker or product state.

## Versioning

- `contract.version` follows semantic versioning.
- Patch: clarifications or optional fields only.
- Minor: backward-compatible fields or enum values.
- Major: removals, renamed required fields or changed semantics.
- The UI must declare compatible contract versions.
- A contract mismatch renders the dashboard `DEGRADED`, never green.

## Source binding

Every material value must reference at least one `sources[].source_id` through `evidence_refs`.

Each source records:

- locator and optional Drive file ID;
- optional SHA-256 when known;
- evidence state;
- freshness state and timestamp;
- whether the source is mandatory.

Missing mandatory sources remain explicit. Their absence never authorizes a rerun or a healthy status.

## Evidence states

| State | Meaning |
|---|---|
| `RECEIPTED` | Required receipt exists and its scope supports the claim |
| `HASH_VERIFIED` | Exact bytes and hash were verified |
| `SOURCE_BACKED` | Source text/data supports the claim, but the complete terminal receipt may not exist |
| `CLAIMED` | An actor states the result; required receipt or negative test is missing |
| `INFERRED` | Explicitly marked controller inference from cited sources |
| `UNKNOWN` | Evidence is missing or inaccessible |
| `CONFLICTED` | Sources materially disagree |
| `REJECTED` | Claim or artifact failed acceptance |

## Rendering policy

Green is allowed only when all three conditions hold:

1. evidence state is `RECEIPTED` or `HASH_VERIFIED`;
2. freshness is `CURRENT`;
3. at least one valid evidence reference is present.

Additional rules:

- `CLAIMED` is yellow and visibly labelled `CLAIMED`.
- `UNKNOWN` is neutral/gray.
- `CONFLICTED`, `REJECTED`, open P0 and failed gates are red.
- `STALE` overrides an otherwise green claim to yellow.
- No adapter may infer `OPERATIONAL` from an HTTP 200 or file existence alone.
- No source-independent universal freshness threshold is encoded. Each adapter must declare a source-specific freshness rule and its basis.

## Authority and effect ceilings

The contract requires:

```text
authority_generation = R63
authority_status = ACCEPTED
control_generation_created = false
can_trade = false
capital_permission = DENY
deploy_permission = DENY
self_application = false
```

Any violating payload fails validation.

## Determinism

Given identical normalized source inputs and an explicit `generated_at`, the snapshot builder must produce byte-identical canonical JSON using UTF-8, sorted keys for hashing and LF line endings. Runtime timestamps, random IDs and unordered filesystem traversal must not enter the canonical payload implicitly.

## Audit tab

The `audit` object is required and contains:

- R63 authority acceptance;
- HANRI decision-loop state;
- P0 closure receipts and missing tests;
- defect ledger;
- artifact acceptance ledger;
- global invariants.

The R63 operator dashboard is merged here; it is not maintained as an independent competing truth surface.

## Standalone and live modes

- `SNAPSHOT`: self-contained fallback with a frozen payload.
- `LIVE`: read-only adapters regenerate the same contract.
- `FALLBACK`: live adapters failed and the last accepted snapshot is displayed with a visible degradation label.

The standalone HTML and server-hosted UI must render the same snapshot ID and payload hash.
