# CODEX07-R64 — Common Memory and Agent Event Bus shadow

Implement the contracts in `COMMON_MEMORY_CONTRACT.md` and `INTER_AGENT_COMMUNICATION_CONTRACT.md` in shadow mode.

Requirements:

- append-only message/event journal;
- deterministic IDs and payload hashes;
- ACK/supersession states;
- no input-as-return confusion;
- no direct current-state mutation;
- projection into dashboard snapshot;
- replay/idempotence tests;
- five concurrent publishers;
- crash/restart recovery;
- 20 idle cycles with zero recursive growth;
- permanent slots for Claude and Fable.

Do not enable live mutation. Return strict broker result.
