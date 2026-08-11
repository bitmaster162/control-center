# Control Center Source Envelope v1

Status: REVIEW-ONLY implementation contract. This file is not authority state.

## Purpose

Normalize read-only upstream observations before they enter the Control Center current-truth reducer. The reducer must never treat "latest JSON" as authority by itself.

## Envelope

Each source envelope contains:

- `schema = control_center.source_envelope.v1`
- `source_id` — stable observation source identifier
- `source_kind` — authority-bounded source type
- `observed_at` — RFC3339 timestamp supplied by the adapter
- `freshness` — `CURRENT` or `STALE`
- `precedence` — deterministic precedence within the same allowed claim class
- `claims[]`

Each claim contains:

- `claim_key` — stable path-like key, e.g. `canonical.generation`, `project.p0-security.state`, `return.foo.transport_status`
- `claim_class` — semantic authority class
- `value` — JSON value
- `evidence_state` — one of `HASH_VERIFIED`, `VERIFIED`, `RECEIPTED`, `SOURCE_BACKED`, `CLAIMED`, `UNKNOWN`
- optional `supersedes[]` containing exact claim refs as `<source_id>::<claim_key>`

## Source authority boundaries

| source_kind | allowed claim classes |
|---|---|
| `CONTROL_ROOTS` | `CANONICAL_AUTHORITY` |
| `PROJECT_OWNER` | `PROJECT_STATE`, `WORK_STATE` |
| `RETURN_BROKER` | `RETURN_TRANSPORT` |
| `HANRI` | `PROJECT_STATE`, `PROPOSAL_EVIDENCE` |
| `CONTROL_CENTER` | `PORTFOLIO_STATE`, `DECISION_STATE`, `SEMANTIC_ACCEPTANCE`, `APPLY_STATE`, `COMMERCIAL_STATE` |
| `HUMAN_GATE` | `HUMAN_DECISION`, `DECISION_STATE`, `SEMANTIC_ACCEPTANCE` |
| `COMMERCIAL` | `COMMERCIAL_STATE` |

A source emitting a claim class outside its authority boundary is invalid. In particular:

- Return Broker cannot emit semantic acceptance or apply authority.
- HANRI cannot emit Control Center canonical authority.
- Project owners cannot grant human/effect authority.
- Dashboard/UI artifacts have no authority source kind and therefore cannot directly enter current truth.

## Current eligibility

A claim is eligible for current resolution only when:

1. envelope freshness is `CURRENT`;
2. evidence state is in `{HASH_VERIFIED, VERIFIED, RECEIPTED, SOURCE_BACKED}`;
3. source kind is authorized for the claim class;
4. it is not explicitly superseded by another eligible claim.

`STALE`, `CLAIMED`, and `UNKNOWN` evidence is retained for audit but cannot win current truth.

## Conflict rule

For a `claim_key`, eligible claims are compared deterministically by precedence and observation timestamp. If the top-ranked claims have the same precedence and same timestamp but different values, the key is `CONFLICT` and the reducer MUST NOT choose either value.

## R64 canonical anchor

This Control Center generation is hard-bound to the accepted current authority:

- generation: `R64`
- status: `ACTIVE`
- pointer SHA-256: `3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef`
- accepted manifest SHA-256: `41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d`
- `CURRENT_STATE.json`: `0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd`
- `ROLE_INDEX.json`: `e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567`
- `ROLE_VIEWS.json`: `9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148`
- provider readback: `all_exact`
- `R63.is_current = false`

A reducer result that does not resolve exactly to this anchor is invalid for the current Control Center projection.

## Non-authority rule

Adapters and reducer outputs are projections/evidence-processing artifacts. They do not mutate `CURRENT_POINTER.json`, `CURRENT_STATE.json`, Return Broker custody, project repositories, human decisions, or external systems.