# Repository boundary

This repository contains the HANRI / Control Center dashboard, schemas, deterministic
projection tooling, validation code, and bounded-governor contracts.

It intentionally excludes:

- live Control Center authority state and pointers;
- ContinuityOS runtime databases and checkpoints;
- ArchiveOS source archives;
- Return Broker delivery trees;
- credentials, private operator messages, and production secrets;
- generated provider receipts and mutable runtime evidence.

Runtime data must be consumed through read-only adapters and represented with explicit
freshness and evidence state. Missing or stale sources must degrade the projection.
