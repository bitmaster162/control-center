from __future__ import annotations

import json
from pathlib import Path

from build_command_queue import build, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> int:
    expected = build(
        load(DATA / "agent_control_plane.generated.v1.json"),
        load(DATA / "work_order_lifecycle.generated.v1.json"),
        load(DATA / "decision_effect_ledger.generated.v1.json"),
        load(DATA / "effect_readback_plane.generated.v1.json"),
    )
    actual = json.loads((DATA / "command_queue.generated.v1.json").read_text(encoding="utf-8"))
    errors = []
    if actual != expected:
        errors.append("command_queue_semantic_mismatch")
    s = actual.get("summary", {})
    required = {"commands_total":14,"human_now":0,"control_center_queue":8,"project_owner_queue":2,"blocked_queue":3,"historical_queue":1,"effect_candidates":0}
    for key, value in required.items():
        if s.get(key) != value:
            errors.append(f"summary_mismatch:{key}")
    if actual.get("queues", {}).get("HUMAN_NOW") != [] or actual.get("human_now") != []:
        errors.append("human_now_must_be_empty")
    if actual.get("queues", {}).get("HISTORICAL_QUEUE") != ["CMD::CODEX07-R43-RETURN-PLANE-V2"]:
        errors.append("historical_queue_mismatch")
    print(json.dumps({"status":"PASS" if not errors else "FAIL","errors":errors,"summary":s}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
