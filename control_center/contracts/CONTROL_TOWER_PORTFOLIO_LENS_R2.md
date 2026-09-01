# Control Tower / Portfolio Lens Contract R2

Status: LOCAL CANDIDATE / READ_ONLY / NO PROVIDER EFFECTS

R2 preserves all R1 boundaries and adds the cross-system identity invariant:

`RUAP Snapshot SHA == ContinuityOS imported snapshot SHA == Control Tower input snapshot SHA`

RUAP Snapshot IR canonical bytes are UTF-8 sorted/minified JSON plus exactly one trailing LF, matching RUAP Core and ContinuityOS.

Control Tower remains source/currentness-only:
- deployment = UNKNOWN
- runtime = UNKNOWN
- effect = DENY
- semantic_authority = CONTROL_CENTER_ONLY

No provider writes, no gate consumption, no deploy, no trading/capital effects.
