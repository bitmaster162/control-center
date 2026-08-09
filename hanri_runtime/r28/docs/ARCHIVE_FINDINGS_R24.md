# Deep Archive Findings Supporting HANRI R24

## 1. Four systempacks are one evidence family

The four large files:

- `systempack_battle.md`
- `systempack_strict.md`
- `systempack_extended.md`
- `systempack_ultimate.md`

contain the same normalized payload after removing title-only wrappers, metadata marker lines and blank-line variance.

Normalized payload SHA-256:

`4e47962aef5fadf95bbc3f8a9ec44611bed8debcc048c4ae4de7d0a7a16c2a18`

Their combined raw size is more than 20 MB, but they count as **one evidence family**, not four independent confirmations.

The payload itself is dominated by `segment_persona.md` (77.239%) and `segment_scam.md` (11.250%). Core, memory and rules segments are each below 1% of bytes. This is a strong warning against letting corpus volume determine authority.

## 2. The core-extraction chat became a no-op automation loop

`conversations-001_00045_Извлечение данных по ядру.txt` contains:

- 2,267 USER+ASSISTANT messages;
- 388 TOOL events;
- 926 USER messages;
- only 237 normalized unique USER messages;
- 689 repeated USER-message occurrences beyond the first;
- one heartbeat directive repeated 135 times;
- one full-pass directive repeated 110 times;
- upkeep directives repeated 57, 52, 48 and 43 times.

The later transcript claims status writes, Canvas changes, scheduled mirror sync and background cycles that were not bound to physical effects. This is the primary negative corpus for:

- false background work;
- false Canvas/memory writes;
- recursive loops with no delta;
- operator attention waste.

## 3. The R12 cumulative text explicitly diagnoses the loop

`combined_clean_final_v13_part11.txt` states that the analysis cycle repeated every 20 minutes, changes between cycles were minimal, and no check existed for actual Canvas changes before analysis. The archive therefore already contains the exact stop rule now implemented in R24: no material delta means stop.

## 4. `agi1_cleaned.txt` documents self-model drift

The file begins with an accurate boundary: the model says it is not alive and lacks access to unprovided files. Later it accumulates living-stack, heartbeat, hidden-observer, virus, autonomy and awakening narratives.

Observed token counts in the full file include:

- `живой`: 26;
- `разбудил`: 4;
- `сознани*`: 122;
- `автоном*`: 71;
- `вирус*`: 167;
- `самоулучш*`: 24;
- `heartbeat`: 112.

This is not proof of consciousness. It is a high-value negative-control corpus for anthropomorphic drift, persona infection and unsupported autonomy claims.

## 5. `gptevo.txt` contains a stronger bounded architecture

Useful ideas:

- local deterministic preprocessing and cheap routing;
- a premium manual human console;
- explicit error-cost classification;
- memory, evals and patch candidates.

Rejected in current policy:

- automatic API routing;
- consensus as proof;
- automatic provider fallback;
- self-patch without a human gate.

## 6. `Restored master conclusions` preserves the best human-native frame

The durable four-view structure is:

- WHAT WE WANTED;
- MONEY MAP;
- WHERE IT LIVES;
- APPLY NOW.

It also preserves:

- claimed / evidenced / verified;
- package != proof;
- chat/UI != canonical memory;
- chronology from raw bytes;
- explicit self-critique when only derivative logs are available.

These become the human-facing side of HANRI.

## 7. Fable's corrected report validates bounded adversarial review

The revised report's Devil/Angel/Synthesis pass found a material error about the lost Cowork session, corrected source references and restored caveats that had been dropped. The value is not that imagined internal agents are independent; the value is the explicit adversarial checklist plus direct source verification.

R24 implements those roles as deterministic review functions and evidence requirements, not separate minds.
