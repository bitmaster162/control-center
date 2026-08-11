# HANRI R39 — Attention-over-Attention / Improvement Governor

## Mission restored

R39 restores HANRI to the full governor/intelligence role rather than treating effect governance as the product itself.

HANRI continuously reasons over four first-order attention domains:

1. **SELF** — audit HANRI's own misses, blind spots, stale assumptions, recommendation failures and attention imbalance.
2. **AGENT** — audit agent outputs, repeated failures, quality drift, tool misuse and skill gaps; generate evidence-bound skill candidates and behavior improvements.
3. **SYSTEM** — audit system reliability, truth drift, process friction and performance defects; generate isolated/shadow-first improvement proposals with readback and rollback requirements.
4. **OPERATOR** — audit operator friction, repeated manual work, context overload and decision bottlenecks; produce concise advisory recommendations, never hidden actions.

Above those four loops is **attention-over-attention**: HANRI audits its own observation coverage and the measured outcomes of earlier recommendations. A cycle is not healthy merely because HANRI produced findings; it must also show where it did not look and whether its prior advice helped, did nothing, or regressed the target.

## Canonical loop

```text
observe
→ detect drift / friction / failure / skill gap / operator burden
→ produce evidence-bound finding
→ propose improvement
→ isolate-test candidate where applicable
→ recommend to operator
→ after accepted execution, verify outcome
→ audit recommendation quality
→ audit attention coverage / blind spots
→ next observation cycle
```

Effect Governance remains downstream safety infrastructure:

```text
HANRI intelligence proposal
→ Control Center accepted intent / work order / human authority
→ R37 Effect Gateway
→ bounded execution
→ independent readback / receipt
→ outcome evidence back into HANRI R39
```

## Outputs

- `SKILL_CANDIDATE`: reusable agent skill draft plus isolated-eval acceptance gate; never auto-installed.
- `AGENT_IMPROVEMENT`: bounded behavior/process proposal for an agent.
- `SYSTEM_IMPROVEMENT`: hypothesis + shadow/isolate test + independent readback + rollback requirement.
- `OPERATOR_ADVICE`: advisory-only recommendation to the human sovereign.
- `HANRI_SELF_IMPROVEMENT`: correction to HANRI's attention/recommendation logic; never self-applied.

## Non-negotiable authority boundary

R39 is proposal/evidence logic. It cannot:

- accept its own proposal;
- install a skill;
- modify a system;
- message the operator automatically;
- auto-dispatch a successor;
- self-apply a self-improvement;
- touch TradingOS or capital permissions.

`can_trade=false` and `capital_permission=DENY` remain hard ceilings.

## Phase-1 Control Center pilot

The fixture intentionally audits the current Control Center episode:

- SELF: stale R35/R28 dashboard truth was not proactively caught before operator challenge;
- AGENT: CODEX-01 gets a candidate current-truth verification skill;
- SYSTEM: static-snapshot drift becomes a system-improvement proposal;
- OPERATOR: repeated manual challenge/coordination becomes operator advice;
- OUTCOME AUDIT: a prior ineffective assumption creates an additional HANRI self-review.

The pilot performs zero provider effects. Its purpose is to prove that HANRI can look at all four layers and then look at the quality and coverage of that attention itself.
