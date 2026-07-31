# Agent operating rules

- Authority remains R63 unless Robert explicitly approves another authority generation.
- This repository is code and contracts, not live Control Center state.
- Do not write `CURRENT_POINTER.json`, live decisions, credentials, or runtime databases here.
- Dashboard output is a deterministic projection, never a source of truth.
- Claims must not render healthier than their strongest evidence receipt.
- HANRI candidates remain shadow-only and may not self-apply.
- No trading, capital, credential rotation, external messaging, or production deployment.
