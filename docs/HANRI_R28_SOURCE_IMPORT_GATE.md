# HANRI R28 Source Import Gate

Status: `BLOCKED_SOURCE_BYTES_NOT_YET_IMPORTED`

This branch exists to establish a forensic Git baseline for the live HANRI R28 runtime before any runtime improvement work.

## Existing verified repository baseline

- Repository: `bitmaster162/control-center`
- Import branch: `hanri/r28-source-import`
- Branch base: `gpt/github-ready-r1`
- Verified repository review head observed before branch creation: `2d1bddf5506f758f9cd8d89be1c21187f3c10256`
- Existing source provenance:
  - source head: `6f2745a7ae027648776ee69b516578282cb740c5`
  - source tree: `8f552ced0843f2fa843afd8b0351a00d65f94c8f`
  - source git bundle SHA-256: `79a265d0692018049f7dc5a4668769f4bc2312779f05b2afba319014634cc0a4`
  - source ZIP SHA-256: `2f910ff85355f68067c7881d7c629a89f3fd5396fad5f2a331bcf5eb1f0c7325`

## Live runtime evidence to bind

Observed live runtime:

- source/runtime application path: `C:\Users\coins\AppData\Local\ControlCenterHANRIR28\app\`
- runtime program version: `28.0.0`
- runtime config path: `C:\Users\coins\AppData\Local\ControlCenterHANRIR28\app\config\r28.windows.json`
- runtime config SHA-256: `0e0652621528597770d57a848e46f9ad7ae32123db70fbd496bf38a6b70cdabb`
- `can_trade=false`
- `self_application=false`

The installed application directory itself has not yet been byte-read through the available connectors. Therefore this branch MUST NOT be described as the R28 source baseline yet.

## Required forensic import procedure

1. Read/copy the installed `app\` tree without modifying the live runtime.
2. Generate an inventory for every source file: relative path, byte size, SHA-256.
3. Run a secret scan before any Git staging.
4. Exclude runtime/mutable/sensitive material, including at minimum:
   - `.env`, credentials, keys, tokens, wallet/account material;
   - `state\`, runtime databases, mutable journals and generated runtime evidence;
   - `decision_inbox\` and operator/private messages;
   - temporary/cache files and generated provider receipts.
5. Verify the copied source tree against the inventory after the copy.
6. Make the first R28 source commit with **no source edits mixed into the import**.
7. Record the resulting Git commit SHA and tree SHA as the R28 baseline evidence.
8. Only after that commit may improvement branches modify HANRI runtime source.

Recommended first source commit message:

`baseline: import verified HANRI R28.0.0 source snapshot`

## Runtime / Drive / Git boundaries

- Git/GitHub: source code, tests, schemas, deterministic build/install tooling, bounded-governor contracts.
- `%LOCALAPPDATA%\ControlCenterHANRIR28\`: installed/live runtime.
- Google Drive `Control canter`: control-plane projection, runtime evidence, receipts, manifests, snapshots and dashboards.

Do not commit mutable Drive state or make Git the source of current Control Center authority.

## Change gate after baseline

Every runtime change must follow:

`baseline -> feature branch -> tests/adversarial checks -> human/control approval -> bounded installer -> independent runtime readback -> rollback/checkpoint receipt`

No direct self-application. No trading/capital authority is granted by this branch or repository.
