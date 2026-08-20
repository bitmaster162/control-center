# P0 HANRI Evidence Sync R1

Status: DRAFT CANDIDATE / SHADOW ONLY / NO EFFECT

## Baseline

This branch starts from the accepted HANRI integration trunk:

`hanri/r37-product-pilot-accepted@ef5c504179de8ae8c16bd70c168b14b79bd2f466`

HANRI remains subordinate to the R64 Control Center authority root.

## Authority stack

```text
HUMAN_SOVEREIGN
→ R64 CONTROL CENTER / GLOBAL COMMAND
→ HANRI bounded runtime-attention-governor/evidence plane
→ accepted Git / receipts / ledgers
→ dashboard projection only
```

HANRI is not a second authority root and cannot promote its own output.

## ArchiveOS boundary

The currently accepted ArchiveOS qualification is intentionally fail-closed:

```text
status=BLOCKED_REVERIFY
freshness=STALE
current_claim_allowed=false
promotion_eligible=false
```

The exact remaining proof debt is a fresh authoritative-root readback, non-empty full SHA-256 integrity receipt, manifest/file-count binding and independent second readback.

Canonical role split:

```text
ArchiveOS Core = non-authoritative evidence vault
C:\PROJECTS\archiveos_api = authoritative ArchiveOS root
Drive = mirror evidence only
Archive Tooling = artifact compiler, not ArchiveOS engine
```

Historical Archive Tooling handoff SHA-256 is retained only as bounded evidence:

`af9f06b74fa380a1b3e9c6bf69b871d17228abd70ae6c13f77ca8984836e0856`

It cannot satisfy ArchiveOS Core integrity proof.

## P0 sync result

The adapter consumes one hash-valid `bitevo.unified_shadow_transaction.v2` and the current `hanri.archiveos-freshness.qualification/v1`.

The HANRI gate is:

```text
HOLD if upstream Control Center gate is HOLD
OR
HOLD if ArchiveOS is not PASS/CURRENT
ELSE
PASS_SHADOW
```

`PASS_SHADOW` is still non-authoritative and non-promotable.

## Knowledge / Memory boundary

P0 records the relationship without performing admission or memory writes:

```text
Archive custody != claim admission
Reasoning derivative != evidence by itself
Durable memory != current truth
Memory != permission
Project canon != private memory
```

Therefore:

```text
claim_admission=NOT_PERFORMED
durable_memory_write=false
project_canon_write=false
current_truth_write=false
```

## Effect ceiling

All effects are fixed false:

```text
github_write=false
drive_write=false
archiveos_write=false
knowledge_write=false
memory_write=false
current_truth_apply=false
runtime_write=false
scheduler_write=false
external_message=false
signal=false
order=false
capital_effect=false
```

And the global safety vector remains:

```text
execution_authority=NONE
can_trade=false
capital_permission=DENY
orders_allowed=false
signals_allowed=false
```
