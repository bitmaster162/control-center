# Canonical Working Folder Layout R64

No existing canonical object is deleted or moved merely to make the tree prettier. Create stable roots first; move only with hash/readback and pointer updates.

```text
Control canter/
├── 00_CONTROL_CURRENT/
│   ├── CURRENT_POINTER.json
│   ├── CURRENT_STATE.json
│   ├── ROLE_INDEX.json
│   ├── ROLE_VIEWS.json
│   ├── START_PROMPTS.md
│   ├── TOKEN_CONTEXT_POLICY.json
│   ├── AUTO_PICKUP_PROTOCOL.md
│   ├── LINEAGE_SUPERSESSION.json
│   └── MANIFEST.json
├── 00_DASHBOARD_CURRENT/
│   ├── CURRENT_UNIVERSE_SNAPSHOT.json
│   ├── CURRENT_DASHBOARD_BUILD.json
│   └── README.md
├── 00_RETURN_DROP/
│   ├── CURRENT_RETURN_REGISTRY.json
│   └── Rxx/<SLOT>/<DELIVERY_ID>/
├── 00_DECISIONS/
│   ├── DECISION_LEDGER.jsonl
│   ├── CURRENT_DECISION_QUEUE.json
│   └── receipts/
├── 00_SECURITY/
│   ├── P0_SECURITY_REGISTER.json
│   └── receipts/
├── 00_MEMORY/
│   ├── CURRENT_MEMORY_INDEX.json
│   ├── events/
│   ├── claims/
│   └── checkpoints/
├── 00_EVENT_BUS/
│   ├── inbox/
│   ├── acknowledged/
│   └── dead_letter/
├── 00_WORK_ORDERS/
│   ├── active/
│   ├── complete/
│   └── cancelled/
├── 00_PRODUCT_CURRENT/
├── 00_INBOX_RAW/
├── 90_ARCHIVE_IMMUTABLE/
└── _to_delete/          # quarantine candidates only; no automatic deletion
```

## Migration controls

- Inventory and hash first.
- Preserve stable Drive IDs where agents already depend on them.
- Copy → readback → update pointer → deprecate old path; never blind move.
- `_to_delete` requires canonical selection, restore proof and retention window.
- No recursive receipt copying.
