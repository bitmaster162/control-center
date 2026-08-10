from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import cli as core
from . import sqlite_inventory_probe as v1

PROBE_VERSION = "35.1.0-probe-v1"
PROBE_MODE = "ISOLATED_JSON_VS_SQLITE_BULK_INVENTORY_AB"
SQLITE_STRATEGY = "BULK_INDEX_SNAPSHOT_SINGLE_SELECT_PLUS_CHANGED_ROW_UPSERT"


def _classify_sqlite_bulk(
    conn: sqlite3.Connection,
    metadata: Sequence[tuple[Path, int, int]],
    fresh: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int, int]:
    rows: list[dict[str, Any]] = []
    hits = 0
    misses = 0
    changed = 0
    query = (
        "SELECT path_key,size_bytes,mtime_ns,path,name,suffix,mtime_utc,sha256,content_class,"
        "content_signature_verified,full_text_read,text_characters_read,line_count_read FROM inventory"
    )
    indexed = {str(row[0]): row[1:] for row in conn.execute(query)}

    for path, size_bytes, mtime_ns in metadata:
        key = v1._path_key(path)
        row = indexed.get(key)
        if row is not None and int(row[0]) == size_bytes and int(row[1]) == mtime_ns:
            rows.append({
                "path": row[2], "name": row[3], "suffix": row[4], "mtime_utc": row[5], "sha256": row[6],
                "content_class": row[7], "content_signature_verified": bool(row[8]), "full_text_read": bool(row[9]),
                "text_characters_read": int(row[10]), "line_count_read": int(row[11]), "size_bytes": size_bytes,
            })
            hits += 1
        else:
            record = dict(fresh[key])
            rows.append(v1._record_lean(record))
            v1._insert_row(conn, key, size_bytes, mtime_ns, record)
            misses += 1
            changed += 1
    return rows, hits, misses, changed


def run_probe(config_path: Path) -> dict[str, Any]:
    original_classifier = v1._classify_sqlite
    try:
        v1._classify_sqlite = _classify_sqlite_bulk
        result = v1.run_probe(config_path)
    finally:
        v1._classify_sqlite = original_classifier
    result["probe_version"] = PROBE_VERSION
    result["probe_mode"] = PROBE_MODE
    result["sqlite_strategy"] = SQLITE_STRATEGY
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R35.1 isolated JSON vs SQLite bulk inventory-cache A/B probe")
    parser.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_probe(args.config)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error, core.HanriError) as exc:
        print(json.dumps({"status": "ERROR", "probe_version": PROBE_VERSION, "error": type(exc).__name__, "message": str(exc), "can_trade": False}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
