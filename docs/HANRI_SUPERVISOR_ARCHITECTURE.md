# HANRI Supervisory Architecture R64

## Decision

HANRI becomes the **bounded self-improvement governor above the Control Center**, not a free-running super-agent and not the source of truth.

```text
Robert / Operator Authority
        ↓
HANRI Governor
  observe → detect drift → propose → isolate-test → recommend
        ↓
Control Center Truth Plane
  source vault · claims/evidence/conflicts · timeline · work orders
        ↓
ContinuityOS Governance + Memory
  canonical state · checkpoints · proof ledger · recovery · policies
        ↓
Executor Network
  GPT · Codex · Fable · Claude · Work · Antigravity
        ↓
Operator Systems / Fleets
  TradingOS · Arena · MAWorld · VisionAssist · Parasite-Killer · ArchiveOS · others
```

## What “self-improving” means now

HANRI may autonomously:

1. observe registered sources;
2. detect drift, contradictions, stale decisions and missing evidence;
3. generate bounded improvement candidates;
4. run deterministic checks and isolated/disposable experiments;
5. compare candidate versus baseline;
6. create a decision card with evidence, rollback class and expected value;
7. learn from ACCEPT/REJECT outcomes in its proposal history.

HANRI may **not** silently:

- apply its own runtime patch;
- change authority, credentials or production state;
- create a new control generation merely to record activity;
- call external model APIs without a scoped work order;
- trade or affect capital.

Application path:

```text
candidate
→ policy check
→ human/control approval
→ verified Git worktree
→ tests + adversarial checks
→ bounded execution
→ independent readback
→ checkpoint + rollback receipt
```

## Invariants

- Control Center owns current truth.
- ContinuityOS owns durable state, replay and authority gates.
- HANRI owns detection, proposals and improvement evidence.
- Executors own isolated implementation.
- Robert owns irreversible and high-impact decisions.
- Missing data yields `UNKNOWN`, never `HEALTHY`.
- No result is complete without evidence return and controller acceptance.
