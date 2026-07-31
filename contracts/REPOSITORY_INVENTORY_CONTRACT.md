# Repository Inventory Contract v1

Repository inventory is a read-only projection of code roots, runtime/data roots,
remote branches and reconciliation status. It does not create repositories, choose
canonical history or authorize a push.

## Evidence rules

- Full 40-character commit identities are required before merge, tag or push.
- Prefix-only commits remain `SOURCE_BACKED`; they never become `HASH_VERIFIED`.
- Runtime/data roots are explicitly marked `RUNTIME_ONLY` and must never be
  initialized as Git repositories by an automated controller.
- A remote readback proves transport, not code acceptance.
- `PUBLISHED_VERIFIED` requires local/remote exact HEAD equality plus a clean
  source bundle and provider readback receipt.

## Statuses

- `PUBLISHED_VERIFIED` — exact review branch is present remotely.
- `REMOTE_SYNCED` — existing local/remote branch is aligned.
- `EXPORT_READY` — Git bundle exists; remote publication still gated.
- `RECONCILE_REQUIRED` — ancestry, fork or branch drift must be resolved.
- `BOUNDARY_AUDIT_REQUIRED` — source is non-Git or mixed with runtime/data.
- `RUNTIME_ONLY` — never initialize or publish as a whole.
- `HOLD` — no action until a named condition is satisfied.
