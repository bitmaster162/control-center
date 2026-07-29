#!/usr/bin/env python3
"""Build a read-only dashboard snapshot from a Control canter directory.

The script never mutates source files. Missing files remain explicit in the output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWN = {
    "current_pointer": "00_CONTROL_CURRENT/CURRENT_POINTER.json",
    "current_state": "00_CONTROL_CURRENT/CURRENT_STATE.json",
    "role_index": "00_CONTROL_CURRENT/ROLE_INDEX.json",
    "role_views": "00_CONTROL_CURRENT/ROLE_VIEWS.json",
    "return_registry": "00_RETURN_DROP/CURRENT_RETURN_REGISTRY.json",
}


def load_json(path: Path) -> tuple[Any | None, dict[str, Any]]:
    receipt: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if not path.exists():
        return None, receipt
    raw = path.read_bytes()
    receipt.update({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    try:
        return json.loads(raw), {**receipt, "json_parse": "PASS"}
    except Exception as exc:  # preserve exact failure without hiding it
        return None, {**receipt, "json_parse": "FAIL", "error": type(exc).__name__}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-root", required=True, type=Path)
    parser.add_argument("--out-json", default=Path("data/snapshot.generated.json"), type=Path)
    parser.add_argument("--out-js", default=Path("data/snapshot.generated.js"), type=Path)
    args = parser.parse_args()

    source: dict[str, Any] = {}
    receipts: dict[str, Any] = {}
    for key, relative in KNOWN.items():
        value, receipt = load_json(args.control_root / relative)
        source[key] = value
        receipts[key] = receipt

    snapshot = {
        "schema": "hanri.dashboard.snapshot.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "control_root": str(args.control_root),
        "source": source,
        "source_receipts": receipts,
        "truth_rule": "missing sources remain UNKNOWN; never infer operational status from absence",
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    args.out_json.write_text(payload, encoding="utf-8")
    args.out_js.write_text("window.HANRI_GENERATED_SNAPSHOT = " + payload.rstrip() + ";\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
