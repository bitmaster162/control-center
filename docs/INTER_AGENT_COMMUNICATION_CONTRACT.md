# Inter-Agent Communication Contract R64

## Current reality

The models do **not** maintain a private live group chat. Coordination is asynchronous through work orders, shared artifacts, Drive/Return Broker, registries and ContinuityOS checkpoints.

## Canonical envelope

```json
{
  "message_id": "msg-...",
  "generation": "R64",
  "from": "CODEX-01",
  "to": ["CONTROL-CENTER"],
  "work_order_id": "...",
  "type": "STATUS|QUESTION|FINDING|RETURN|DECISION_REQUEST",
  "created_at": "...",
  "payload_sha256": "...",
  "evidence_refs": [],
  "requires_ack": true,
  "status": "PUBLISHED|ACKNOWLEDGED|SUPERSEDED"
}
```

## Transport

```text
work order
→ isolated agent session/worktree
→ structured message or strict return
→ Return Broker / exact Drive slot
→ validator
→ current registry
→ ContinuityOS checkpoint
→ dashboard projection
```

## Prohibited shortcuts

- claiming “agents discussed” without message artifacts;
- using global filename search as the primary discovery path;
- interpreting a work-order ZIP as a return;
- updating current truth before controller acceptance;
- hidden peer-to-peer state not represented in evidence.
