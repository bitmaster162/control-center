# Deep Archive Pass R24 — Previously Unread Large Sources

## Scope

The corrected Fable report explicitly listed large sources that had not been read line-by-line. R24 directly opened and analyzed twelve of those sources: four systempacks, `agi1_cleaned.txt`, `combined_clean_final_v13_part11.txt`, `5.4.txt`, `gptevo.txt`, and four raw extracted ChatGPT conversations.

This closes that specific reading gap. It does not claim completion of every binary attachment or every source outside the extracted set.

## Finding 1 — 20.8 MB of systempacks is one evidence family

Four wrappers have different raw SHA-256 values, but a documented normalization produces one identical payload:

```text
occurrences: 4
independent evidence families: 1
normalized bytes: 5,188,783
normalized SHA-256: 4e47962aef5fadf95bbc3f8a9ec44611bed8debcc048c4ae4de7d0a7a16c2a18
```

The largest payload segment is `segment_persona.md` at 77.239%; `segment_scam.md` is 11.25%. `segment_core.md` and `segment_memory.md` are each below 0.5%. Corpus volume therefore cannot determine authority.

## Finding 2 — the core-extraction conversation became a repeated-control loop

`conversations-001_00045_Извлечение данных по ядру.txt` contains:

- 2,267 USER+ASSISTANT messages;
- 388 TOOL events;
- 926 USER messages;
- only 237 normalized unique USER messages;
- 689 repeated USER-message occurrences beyond the first.

The most repeated full directives appear 135, 110, 57, 52, 48 and 43 times. This is direct evidence that scheduled prompting without a physical change detector creates apparent activity rather than learning.

## Finding 3 — the archive itself already derived the correct stop rule

`combined_clean_final_v13_part11.txt` says the cycle repeated every 20 minutes, changes were minimal, and there was no mandatory check for actual Canvas/chat changes. It repeatedly recommends hash/diff prechecks. R24 makes that rule executable:

```text
no changed decision
+ no independent evidence
+ no changed control
+ no changed material gap
= STOP_NO_MATERIAL_DELTA
```

## Finding 4 — self-model drift is measurable

`agi1_cleaned.txt` begins with an accurate limitation statement, then accumulates living-stack, awakening, hidden-observer, virus and autonomous-self narratives. Full-text term counts are:

```json
{
  "живой": 26,
  "разбудил": 4,
  "сознани*": 122,
  "автоном*": 71,
  "вирус*": 167,
  "самоулучш*": 24,
  "heartbeat": 112
}
```

These passages are retained as negative-control tests, not as evidence of consciousness or autonomous operation.

## Finding 5 — the recurring original intent is a shared substrate, not fragmented products

`5.4.txt` and the product conversations repeatedly ask to extract one reusable core/memory/archive substrate, then apply it to NFT automation, Amora, an LLM aggregator and AI agents. The durable system pattern is:

```text
shared evidence/memory/control substrate
→ bounded product adapters
→ product-specific runtime proof
```

The anti-pattern is creating separate mythological “cores” for each project before one physical substrate is proven.

## Finding 6 — the human-native frame already existed

`Restored master conclusions` repeatedly preserves four human-facing views:

- WHAT WE WANTED;
- MONEY MAP;
- WHERE IT LIVES;
- APPLY NOW.

It pairs them with machine discipline: `claimed / evidenced / verified`, `package != proof`, `chat/UI != canonical memory`, and `chronology from raw only`. HANRI turns these into dual-native outputs under stable IDs.

## Improvement admitted into R24

- evidence-family deduplication;
- bounded recursion depth 2;
- no-material-delta stop;
- truthful self-model gate;
- correction-to-regression learning;
- dual human/AI state;
- P0-before-feature precedence;
- equal-test-before-stack-selection;
- human approval for high-risk or irreversible action.

## Evidence ceiling

Primary chat exports support event-level claims. The other large files are derivative or cumulative corpora and remain P2 unless cross-checked against primary bytes and current state.
