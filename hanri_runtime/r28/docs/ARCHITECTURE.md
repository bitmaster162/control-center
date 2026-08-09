# HANRI R24 Architecture

HANRI is a bounded, shadow-only recursive improvement supervisor.

It does not improve model weights and it does not rewrite CORE/BRAIN by itself. It records structured task events, applies deterministic anti-regression checks, proposes the smallest candidate delta, falsifies that candidate once, and stops for Robert's decision.

## State machine

```text
OBSERVE EVENT
    ↓
DETERMINISTIC DIAGNOSIS
    ↓
CANDIDATE DELTA
    ↓
ONE ADVERSARIAL FALSIFICATION PASS
    ↓
HUMAN REVIEW REQUIRED
    ↓
ACCEPT | REVISE | HOLD | REJECT
```

No automatic transition exists from candidate to applied policy.

## Bounded recursion

Depth 0: task/step event.

Depth 1: critique and minimal candidate delta.

Depth 2: falsification of the candidate.

A third recursive level is prohibited. No material change to decision, evidence, control or unresolved-gap state produces `STOP_NO_MATERIAL_DELTA`.

## Inputs

- structured step/task events;
- Robert's explicit corrections and verdicts;
- R23 return-sync state;
- current-state artifacts by exact path/hash.

## Outputs

AI-native:
- append-only event, finding, candidate, falsification and decision ledgers;
- exact IDs, hashes, evidence refs and machine state;
- regression-case ledger.

Human-native:
- one decision digest;
- each card states why it matters, the smallest change, the test and the available verdicts;
- machine details remain linked by Candidate ID rather than being forced on the operator.

## Authority

HANRI may write only to its own state/output roots. It has no source, repository, runtime, provider, deployment or capital authority.

## Additional fail-closed gates

- human/AI view mismatch;
- material operator correction without a regression case;
- high-risk or irreversible action without explicit human approval;
- stack selection before equal falsification tests;
- feature expansion while a known P0 defect remains open.


## R26 causal archive plane

R26 adds a tri-frontier archive selector and a scope-bound coverage certificate. The selector chooses one unseen origin, pivot and current item. The scanner has no semantic authority: it creates evidence for Human review.

Outputs:

- `latest_archive_causal_spine.json`
- `latest_archive_scope_certificate.json`
- event `ARCHIVE_CAUSAL_SPINE`
