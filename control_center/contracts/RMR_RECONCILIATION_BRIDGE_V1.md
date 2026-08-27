# RMR Reconciliation Bridge V1

Status: `CANDIDATE / REVIEW-ONLY / NON-AUTHORITY`

## Base binding

Prepared read-only against:

- repository: `bitmaster162/control-center`
- default branch: `gpt/github-ready-r1`
- base HEAD: `263a54410f6e53f0796c5c71879f9aa4913e2bcd`
- base tree: `6aae425a133991f76fafa3f3f104da38559c16dd`
- `RMR_EVIDENCE_ENVELOPE_V1.schema.json` blob: `757a8a48a49fc2746d34f3081d66e2407b26ff8c`
- `reconciliation-record.v1.schema.json` blob: `d343292ede1816c1587d08c8f22bac4e8b96ff26`
- `reconciliation_v1.py` blob: `a432f0f72eae4d20f833edea6d06f2cc64188b78`
- `rmr_evidence_consumer.py` blob: `6d0a956ff47f925bcd2502efccaacf3e66412df0`

No repository write, runtime call, service mutation, Current Truth write, apply, external effect, execution, trading, or capital action is authorized by this contract.

## Purpose

Translate one already-produced `RMR_EVIDENCE_ENVELOPE_V1` into one `control_plane.reconciliation_record.v1` transport observation so the existing deterministic reconciliation reducer can route RMR evidence to semantic review without granting RMR semantic, Current Truth, apply, or execution authority.

The bridge does not add `RMR` as a Current Truth source kind and does not alter the authority model.

## Required authority mapping

Every output is fixed to:

- `source_class = TRANSPORT_OBSERVATION`
- `authority_class = TRANSPORT_ONLY`
- `semantic_status = UNREVIEWED`
- `apply_status = NOT_APPLIED`
- `owner = CONTROL_CENTER`
- `current_observation = false`
- `requested_action = null`
- `human_gate_required = false`
- `action_evidence_fresh = false`
- `effect_authorized = false`
- `execution_authorized = false`
- `readback_status = NOT_DUE`

The bridge cannot emit semantic acceptance, canonical active state, apply eligibility, execution authority, requested actions, or human-gate ripeness.

## Pinned RMR ceiling

The envelope must match exact accepted RMR HEAD/tree/identity binding, `EVIDENCE_ONLY`, `CANDIDATE_NOT_LIVE`, `current_truth_promoted=false`, and `execution_authority=NONE`.

## Raw response digest binding

The bridge recomputes `SHA256(canonical_json(envelope.evidence))` with the accepted consumer's stable JSON representation and requires exact equality with `response_digest_sha256`. Mismatch fails closed as `RESPONSE_DIGEST_MISMATCH`.

## Derived metadata replay binding

R87 closes the remaining R86 integrity gap. After digest verification the bridge replays the accepted consumer's pure response validation/classification helpers from `rmr_evidence_consumer.py`:

- `_validate_response_metadata`
- `_returned_count`
- `_provenance_status`
- `_classify`

It also rechecks the raw response operation echo and read-only/currentness ceiling used by the accepted consumer.

The following envelope fields must exactly equal what those deterministic semantics derive from the digested raw `evidence` body:

- `returned_count`
- `has_more`
- `provenance_status`
- `coverage_warning`
- `conflict_indication`
- `consumer_decision`

Any mismatch fails closed as `DERIVED_METADATA_MISMATCH:<field>`. A caller therefore cannot rewrite pagination, provenance, coverage, conflict state, or decision after the raw response has been digested.

For `search_text`, raw RMR operation echo remains `search_messages`, matching the accepted consumer. Other operations require exact operation echo.

This is self-consistency/custody validation, not a new authentication mechanism and not semantic authority.

## Bridgeable decisions

Only:

- `EVIDENCE_ACCEPTED_FOR_REVIEW`
- `EVIDENCE_PARTIAL`
- `EVIDENCE_CONFLICT`
- `EVIDENCE_GAP`

Rejected health/identity evidence does not become a reconciliation record.

Decision mapping:

| RMR decision | `claim_status` | `evidence_debt` |
|---|---|---:|
| `EVIDENCE_ACCEPTED_FOR_REVIEW` | `PASS` | false |
| `EVIDENCE_PARTIAL` | `PARTIAL` | true |
| `EVIDENCE_GAP` | `PARTIAL` | true |
| `EVIDENCE_CONFLICT` | `HOLD` | true |

## Source-cut and subject binding

`source_cut_id` and `subject_id` remain controller-supplied arguments, not RMR-supplied authority. The bridge does not infer semantic subject ownership from RMR text and never marks RMR output as a current factual observation.

## Expected downstream behavior

With only an RMR bridge record, current reconciliation semantics remain:

- `truth_status = UNKNOWN`
- `semantic_status = UNREVIEWED`
- `route = CONTROL_CENTER`
- `authority_granted = false`
- `auto_execute = false`
- all effects false
- `can_trade = false`
- `capital_permission = DENY`

A later controller or human semantic decision must be a distinct artifact produced by its own authority boundary.
