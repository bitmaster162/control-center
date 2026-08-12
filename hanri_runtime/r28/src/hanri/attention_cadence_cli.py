from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from hanri.attention_cadence import POLICY_VERSION, decide_wake

UTC = dt.timezone.utc


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="HANRI R39.3.2 attention cadence controller")
    parser.add_argument("--loop-receipt", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-receipt", required=True)
    parser.add_argument("--now")
    parser.add_argument("--lease-active", action="store_true")
    args = parser.parse_args()

    now = args.now or dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")
    state_path = Path(args.state)
    prior = _read(state_path) if state_path.exists() else None
    result = decide_wake(
        loop_receipt=_read(Path(args.loop_receipt)),
        prior_cadence_state=prior,
        policy=_read(Path(args.policy)),
        now=now,
        lease_active=bool(args.lease_active),
    )
    _write(state_path, result["state"])
    _write(Path(args.output_receipt), result["receipt"])
    receipt = result["receipt"]
    print(json.dumps({
        "status": "PASS",
        "policy_version": POLICY_VERSION,
        "action": receipt["action"],
        "mode": receipt["mode"],
        "interval_minutes": receipt["interval_minutes"],
        "heartbeat_minutes": receipt["heartbeat_minutes"],
        "next_full_attention_at": receipt["next_full_attention_at"],
        "scheduler_installed": False,
        "provider_calls": 0,
        "execution_effects_performed": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
