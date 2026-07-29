# ANTIGRAVITY-R64 — R63 acceptance, workspace order and P0 closure

## Authority

Robert approved D1–D4. This work order does not grant trading or capital effects.

## Start gate

1. Read R63 `CURRENT_POINTER`, `CURRENT_STATE`, `ROLE_INDEX`, `ROLE_VIEWS`, generation ledger, P0 register and Drive readback receipt.
2. Verify exact device/provider hashes and write ordering.
3. Verify the canonical ContinuityOS repository HEAD and clean/defined baseline before modifying persistent scripts.
4. If R63 bytes or Git baseline are ambiguous, stop `R63_OR_BASELINE_CONFLICT`.

## Phase A — accept R63

- verify all 21/21 files claimed in the provider readback;
- confirm pointer written last and targets existing R63 files;
- confirm R56 is VOID and lineage planes are explicit;
- produce controller acceptance receipt.

## Phase B — D1 and folder order

- register permanent slots: `CLAUDE-BITUNIX`, `FABLE-5`, `CODEX-08`;
- create missing stable roots described in `CANONICAL_FOLDER_LAYOUT.md`;
- do not move existing canonical files unless copy/readback/pointer update succeeds;
- inventory root clutter, receipt recursion, temp and untitled objects;
- quarantine proposals only; no deletion.

## Phase C — D2 HANRI decision-loop repair

- bind the accepted human decision `HD-HANRI-R28-20260727T175628Z`;
- reproduce the bug: accepted/rejected cards still appear as pending;
- apply the existing decision-intake repair in a verified Git worktree;
- tests must prove raw_cards=2, unique_decisions=1, exactly one executable change, zero pending recurrence;
- no self-application outside the approved scope.

## Phase D — D3 CONTROL_FREEZE

Install the policy file and executable validation gate. Reject control churn. Record all emergency exceptions.

## Phase E — D4 P0 security window

For each risk, reverify current exposure before changing anything.

1. **Arena PostgreSQL** — if still externally exposed: preserve current config, restrict firewall/bind to localhost, rotate password, update the legitimate consumer, verify new connection, then revoke old credential. Never log the value.
2. **Panel bearer token** — issue replacement, update consumer, verify, revoke old, redact/quarantine exposed artifact. Never print token.
3. **win185 Administrator access** — preserve break-glass, establish and verify new key/credential path before invalidating old password; avoid lockout; capture only redacted receipts.

Classify credential rotations as `COMPENSATABLE`, not rollback. If operator presence is required, stop at `OPERATOR_PRESENCE_REQUIRED` rather than risking lockout.

## Deliverables

- R63 independent acceptance
- folder inventory and migration ledger
- decision-loop repair Git receipts and tests
- CONTROL_FREEZE gate receipt
- one security receipt per P0 item
- new current-state delta
- dashboard source-adapter inventory
- strict ZIP/SHA/READY-last through broker

No new successor work order. `can_trade=false`; `capital_permission=DENY`.
