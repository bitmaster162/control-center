#!/usr/bin/env python3
"""Capture immutable metadata for known Control canter sources.

This tool is read-only. It does not infer system health and does not produce a
dashboard snapshot. A controller/runtime transformer must adjudicate the capture
before projecting it through the snapshot contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

KNOWN = {
    "current_pointer": "00_CONTROL_CURRENT/CURRENT_POINTER.json",
    "current_state": "00_CONTROL_CURRENT/CURRENT_STATE.json",
    "role_index": "00_CONTROL_CURRENT/ROLE_INDEX.json",
    "role_views": "00_CONTROL_CURRENT/ROLE_VIEWS.json",
    "return_registry": "00_RETURN_DROP/CURRENT_RETURN_REGISTRY.json",
}


def capture(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"locator": str(path), "exists": path.exists()}
    if not path.exists():
        return result
    raw = path.read_bytes()
    result.update({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    try:
        json.loads(raw)
        result["json_parse"] = "PASS"
    except Exception as exc:
        result.update({"json_parse": "FAIL", "error": type(exc).__name__})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-root", required=True, type=Path)
    parser.add_argument("--captured-at", required=True, help="Explicit RFC3339 timestamp supplied by the runtime")
    parser.add_argument("--out", type=Path, default=Path("data/source_capture.generated.json"))
    args = parser.parse_args()

    payload = {
        "schema": "hanri.dashboard.source_capture.v1",
        "captured_at": args.captured_at,
        "control_root": str(args.control_root),
        "sources": {key: capture(args.control_root / relative) for key, relative in sorted(KNOWN.items())},
        "adjudication_required": True,
        "truth_rule": "Existence/hash/parse do not establish operational health or current authority.",
        "effects": {"writes_to_control_root": 0, "can_trade": False, "capital_permission": "DENY"},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
