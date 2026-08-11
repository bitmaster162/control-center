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
    if actual != expected:
        print(json.dumps({"status": "FAIL", "error": "command_queue_semantic_mismatch"}, indent=2))
        return 2
    print(json.dumps({
        "status": "PASS",
        "commands_total": actual["summary"]["commands_total"],
        "human_now": actual["summary"]["human_now"],
        "control_center_queue": actual["summary"]["control_center_queue"],
        "project_owner_queue": actual["summary"]["project_owner_queue"],
        "blocked_queue": actual["summary"]["blocked_queue"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
