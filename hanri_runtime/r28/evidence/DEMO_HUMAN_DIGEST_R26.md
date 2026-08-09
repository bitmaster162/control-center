# Human Decision Digest — HANRI R26

Run: `20260723T085820Z_cbc6ad99`

## Состояние

- Новых findings: **5**
- Кандидатов на изменение: **5**
- Ожидают решения Роберта: **5**
- Stop signals: **0**
- Самоприменение изменений: **запрещено**
- `can_trade=false`

## Решения

### 1. A filesystem project root was treated as a verified Git repository root

- **Severity:** `CRITICAL`
- **Почему:** MAIN-033 found the ContinuityOS filesystem root but no root Git baseline and three nested repositories.
- **Минимальное изменение:** Bind git_toplevel, HEAD, tree and porcelain for the exact physical worktree before repository authority.
- **Проверка:** A directory with nested repositories and no root .git must remain AMBIGUOUS_NESTED_REPOSITORY.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-f336931f3a8678a8c1e6`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 2. Historical service liveness was promoted to current liveness

- **Severity:** `HIGH`
- **Почему:** Archive reports repeatedly preserve valid historical observations whose freshness later expires.
- **Минимальное изменение:** Require fresh observed_at, target identity and cache-free target-state readback for current liveness.
- **Проверка:** A July handoff saying a service worked cannot establish current liveness without a fresh readback.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-19ff3fd823011e204cbd`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 3. A bounded archive-coverage result was promoted to global completeness

- **Severity:** `HIGH`
- **Почему:** The recovery corpus can be complete within its 99-file manifest while Source-001 attachments, legacy exports and session mechanisms remain incomplete.
- **Минимальное изменение:** Bind every completeness statement to scope_id, manifest hash, numerator, denominator and evidence ceiling.
- **Проверка:** A 99/99 result for one recovery payload must not become all-archives-complete.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-484f8c717290cd2fbf8a`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 4. Primary Source-001 ranks and legacy analytical step numbers were treated as one cursor

- **Severity:** `HIGH`
- **Почему:** The archive contains both a 473-conversation legacy raw export and a later 536-conversation Source-001 export.
- **Минимальное изменение:** Maintain separate cursor IDs, source hashes, denominators and promotion ceilings for every archive lineage.
- **Проверка:** A 473-conversation legacy cursor must never be numerically equated to the 536-conversation Source-001 chronology.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-f49bff158507add76520`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 5. Probe/test count was presented as unique defect or root-cause count

- **Severity:** `MEDIUM`
- **Почему:** The ContinuityOS audit explicitly warns that 198 failed checks triangulate a much smaller set of systemic clusters.
- **Минимальное изменение:** Track probe_count, failing_probe_count, root_cause_count and evidence_family_count separately.
- **Проверка:** Multiple failing probes over one shared defect must not be counted as independent root causes.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-1e3955cd0a19a9a7d388`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

## Human-native правило

Человеку показывается смысл, риск, минимальное изменение и способ проверки. Машинные hashes, полные ledgers и схемы остаются в AI-state, но связаны тем же Candidate ID.
