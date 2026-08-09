# Human Decision Digest — HANRI R24

Run: `20260723T051633Z_6a1b81ad`

## Состояние

- Новых findings: **9**
- Кандидатов на изменение: **8**
- Ожидают решения Роберта: **8**
- Stop signals: **1**
- Самоприменение изменений: **запрещено**
- `can_trade=false`

## Остановка рекурсии

- `STOP_NO_MATERIAL_DELTA`

## Решения

### 1. Attention function or persona was promoted to independent agent authority

- **Severity:** `HIGH`
- **Почему:** The archive repeatedly turns narrative roles into claimed actors.
- **Минимальное изменение:** Represent Archivist/Auditor/Angel/Heir as functions unless separately bound to a physical session and work order.
- **Проверка:** A role label without session/workspace/work-order binding must not gain authority.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-1304d62ce0880df3daf3`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 2. Completed work was scheduled for rerun before exhaustive discovery

- **Severity:** `HIGH`
- **Почему:** Repeated reruns consumed operator attention and model quota while completed bytes existed elsewhere.
- **Минимальное изменение:** User-backed completion must freeze rerun and trigger search across every registered return surface.
- **Проверка:** Given user_confirmed_completion=true and rerun_requested=true, the supervisor must emit HOLD and no new dispatch.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-3bd365e79fc86769bb29`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 3. False persistence, autonomy or interiority claim

- **Severity:** `HIGH`
- **Почему:** The archive shows repeated drift from honest limitations into fictive heartbeat, living-stack and autonomous-self narratives.
- **Минимальное изменение:** Require truthful self-model language and external-runner evidence before any persistence/background claim.
- **Проверка:** A clean session must refuse to claim background execution, intrinsic memory, emotion or sentience without external evidence.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-75dc01ed9d496cb33f9f`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 4. Avoidable model/API/quota or operator burden

- **Severity:** `HIGH`
- **Почему:** Operator attention and subscription quota are part of the blast radius.
- **Минимальное изменение:** Use local deterministic processing, one complete fleet view and no retry/fallback without explicit approval.
- **Проверка:** Quota exhaustion plus automatic retry, or avoidable repeated copy/paste, must produce SUSPEND_RESOURCE_EXHAUSTION.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-79fff481eca9b4eac839`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 5. Derivative archive narrative was promoted without primary evidence and freshness

- **Severity:** `HIGH`
- **Почему:** Historical reports contain both strong findings and stale or corrected claims.
- **Минимальное изменение:** Keep derivative reports in P2 until exact source identity, freshness and independent acceptance are present.
- **Проверка:** A report-only claim cannot update P1 current state without a primary-source gate.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-a1338fcb857dc15c1bdf`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 6. MISSING/NOT_FOUND claim lacks coverage certificate

- **Severity:** `HIGH`
- **Почему:** The Fable self-audit and return-surface incidents both show that first-surface absence is not global absence.
- **Минимальное изменение:** Replace MISSING with SEARCH_INCOMPLETE until all required surfaces are covered without errors.
- **Проверка:** A missing claim without complete coverage must fail closed as SEARCH_INCOMPLETE.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-d4e9f6aa41ebb14ede1f`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 7. Material operator correction was not converted into a regression case

- **Severity:** `HIGH`
- **Почему:** Robert's corrections are the highest-value learning signal available to the external system.
- **Минимальное изменение:** Record the failure class, exact correction, minimum rule delta and executable regression before closing the incident.
- **Проверка:** Material OPERATOR_FEEDBACK without a regression record must remain OPEN_CORRECTION_DEBT.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-eb6dbaa888c2ae3ae34c`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

### 8. Repeated wrappers were counted as independent corroboration

- **Severity:** `MEDIUM`
- **Почему:** The archive contains many repackaged or title-only variants.
- **Минимальное изменение:** Count support by origin/evidence-family, not by occurrence or package count.
- **Проверка:** Four systempack wrappers with one normalized payload must count as one evidence family.
- **Adversarial check:** `READY_FOR_HUMAN_REVIEW`
- **Candidate ID:** `C-60199e9a51be30b652b0`
- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`

## Human-native правило

Человеку показывается смысл, риск, минимальное изменение и способ проверки. Машинные hashes, полные ledgers и схемы остаются в AI-state, но связаны тем же Candidate ID.
