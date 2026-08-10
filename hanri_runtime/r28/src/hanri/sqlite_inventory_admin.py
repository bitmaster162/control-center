from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import archive_sqlite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify HANRI R35 SQLite inventory state")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--seed-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = archive_sqlite.verify_inventory(args.db, args.seed_json)
    except (OSError, ValueError) as exc:
        result = {"status": "ERROR", "error": type(exc).__name__, "message": str(exc), "can_trade": False}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
