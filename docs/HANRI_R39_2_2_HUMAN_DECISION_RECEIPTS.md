# HANRI R39.2.2 — Human Decision Receipts as OPERATOR Attention Evidence

## Host finding

The R39.2.1 real-host pilot proved that the remaining OPERATOR blind spot was not caused by scan exclusions:

- `PROCESSED_SOURCES=21`
- `EMITTED_ENVELOPES=21`
- `SCAN_SKIPS=54`
- `SOURCE_TOO_OLD=50`
- `SOURCE_TOO_LARGE=3`
- `SOURCE_JSON_ROOT_UNSUPPORTED=1`
- skip sources were only R23/R36 agent/system surfaces
- `OPERATOR=0`

Therefore no qualifying file existed in the R36 operator event inbox.

## Existing authoritative evidence

Control Center already stores a real current-generation human decision receipt:

`receipts/D1_D5_DECISION_RECEIPT.json`

It is bound to:

- schema `control_canter.human_decision_receipt.v1`
- generation `R64`
- decider `Robert`
- explicit human authorization utterance
- bounded D1-D5 decisions
- `can_trade=false`
- `capital_permission=DENY`

R39.2.2 observes that existing receipt rather than creating a synthetic OPERATOR_FEEDBACK event.

## Receipt-to-attention contract

A human decision receipt closes OPERATOR attention coverage only when all of the following hold:

1. exact schema matches `control_canter.human_decision_receipt.v1`;
2. generation is current `R64`;
3. decider is human-bound (`Robert` / `HUMAN` / `OPERATOR`);
4. at least one decision has an ID and verdict;
5. receipt boundaries preserve `can_trade=false` and `capital_permission=DENY`.

A valid receipt emits `AUDIT_COVERAGE(domain=OPERATOR)` only. It does not create a material operator finding by itself.

## Data minimization

The attention envelope does not persist:

- `authorization_utterance`;
- individual decision scopes;
- arbitrary receipt fields.

It persists only the source identity/SHA plus bounded evidence refs for schema, generation and decision count.

## Authority boundary

Observation is not execution.

- human decision execution: false
- synthetic operator events: false
- provider calls: false
- scheduler install: false
- stable-root writes: false
- R36 modification: false
- self-apply: false
- skill install: false
- system write: false
- operator message: false
- auto-dispatch: false
- external messages: false
- `can_trade=false`
- `capital_permission=DENY`

The receipt remains evidence of a prior bounded human decision. R39.2.2 cannot replay, broaden or execute it.
