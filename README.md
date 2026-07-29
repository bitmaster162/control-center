# HANRI Control Center R64

A runnable local **snapshot dashboard** plus integration contracts for the HANRI / Control Center / ContinuityOS stack.

## What this package is

- a truthful read-only dashboard that opens now;
- a bounded HANRI supervisor architecture;
- common-memory and inter-agent communication contracts;
- D1–D5 decision receipts;
- a canonical working-folder layout;
- exact implementation work orders for Antigravity, CODEX-01, CODEX-07, Work and HANRI.

## What it is not

- not proof that R63 is independently accepted;
- not a live-connected dashboard yet;
- not direct model-to-model chat;
- not production mutation or trading authority.

## Run the dashboard

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Then open `http://127.0.0.1:8764`.

It can also be opened directly through `index.html`; the included snapshot is embedded as JavaScript.

## Validate

```bash
python scripts/validate.py
python -m pytest -q
```

## Build a local source snapshot

```powershell
py scripts\build_snapshot.py `
  --control-root "C:\Users\coins\My Drive\Control canter" `
  --out-json data\snapshot.generated.json `
  --out-js data\snapshot.generated.js
```

The builder is read-only and records missing sources as missing.
