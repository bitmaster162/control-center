from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import archive as legacy
from . import archive_scandir
from . import cli as core
from . import delta_cli as r30

PROBE_VERSION = "35.0.0-probe-v1"
PROBE_MODE = "ISOLATED_JSON_VS_SQLITE_INVENTORY_AB"
EXPECTED_PROGRAM_VERSION = "33.0.0"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_config(raw: Mapping[str, Any]) -> None:
    if str(raw.get("program_version")) != EXPECTED_PROGRAM_VERSION:
        raise core.HanriError("R35 requires accepted R33 config")
    if raw.get("shadow_only") is not True:
        raise core.HanriError("shadow_only must be true")
    if raw.get("external_model_api") != "DENY":
        raise core.HanriError("external_model_api must be DENY")
    if raw.get("can_trade") is not False:
        raise core.HanriError("can_trade must be false")


def _state_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return result
    for path in root.iterdir():
        if path.is_file():
            stat = path.stat()
            result[path.name] = (int(stat.st_size), int(stat.st_mtime_ns))
    return result


def _metadata_snapshot(values: Sequence[str | Path]) -> list[tuple[Path, int, int]]:
    rows: list[tuple[Path, int, int]] = []
    for path, stat in archive_scandir.iter_file_metadata_scandir(values):
        rows.append((path, int(stat.st_size), int(stat.st_mtime_ns)))
    return rows


def _path_key(path: Path) -> str:
    return str(path).casefold()


def _record_lean(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": str(record["path"]),
        "name": str(record["name"]),
        "suffix": str(record["suffix"]),
        "size_bytes": int(record["size_bytes"]),
        "mtime_utc": str(record["mtime_utc"]),
        "sha256": str(record["sha256"]),
        "content_class": str(record.get("content_class", "UNKNOWN")),
        "content_signature_verified": bool(record.get("content_signature_verified", False)),
        "full_text_read": bool(record.get("full_text_read", False)),
        "text_characters_read": int(record.get("text_characters_read", 0)),
        "line_count_read": int(record.get("line_count_read", 0)),
    }


def _fresh_records_for_misses(
    sections: Mapping[str, Sequence[tuple[Path, int, int]]],
    cache: Mapping[str, Any],
    max_bytes: int,
) -> tuple[dict[str, dict[str, Any]], int]:
    miss_paths: dict[str, Path] = {}
    for metadata in sections.values():
        for path, size_bytes, mtime_ns in metadata:
            cached = cache.get(_path_key(path))
            if not (
                isinstance(cached, dict)
                and cached.get("size_bytes") == size_bytes
                and cached.get("mtime_ns") == mtime_ns
                and isinstance(cached.get("record"), dict)
            ):
                miss_paths[_path_key(path)] = path
    started = time.perf_counter()
    records = {key: legacy.inspect_file(path, max_bytes=max_bytes) for key, path in miss_paths.items()}
    elapsed_ms = int(round((time.perf_counter() - started) * 1000.0))
    return records, elapsed_ms


def _classify_json(
    metadata: Sequence[tuple[Path, int, int]],
    cache: Mapping[str, Any],
    fresh: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], int, int]:
    rows: list[dict[str, Any]] = []
    next_cache: dict[str, Any] = {}
    hits = 0
    misses = 0
    for path, size_bytes, mtime_ns in metadata:
        key = _path_key(path)
        cached = cache.get(key)
        if (
            isinstance(cached, dict)
            and cached.get("size_bytes") == size_bytes
            and cached.get("mtime_ns") == mtime_ns
            and isinstance(cached.get("record"), dict)
        ):
            record = dict(cached["record"])
            hits += 1
        else:
            record = dict(fresh[key])
            misses += 1
        rows.append(record)
        next_cache[key] = {"size_bytes": size_bytes, "mtime_ns": mtime_ns, "record": record}
    return rows, next_cache, hits, misses


def _create_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute(
        """
        CREATE TABLE inventory (
            path_key TEXT PRIMARY KEY,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            path TEXT NOT NULL,
            name TEXT NOT NULL,
            suffix TEXT NOT NULL,
            mtime_utc TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            content_class TEXT NOT NULL,
            content_signature_verified INTEGER NOT NULL,
            full_text_read INTEGER NOT NULL,
            text_characters_read INTEGER NOT NULL,
            line_count_read INTEGER NOT NULL,
            record_json TEXT NOT NULL
        ) WITHOUT ROWID
        """
    )
    return conn


def _insert_row(conn: sqlite3.Connection, key: str, size_bytes: int, mtime_ns: int, record: Mapping[str, Any]) -> None:
    lean = _record_lean(record)
    conn.execute(
        """
        INSERT OR REPLACE INTO inventory (
            path_key,size_bytes,mtime_ns,path,name,suffix,mtime_utc,sha256,content_class,
            content_signature_verified,full_text_read,text_characters_read,line_count_read,record_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            key, size_bytes, mtime_ns, lean["path"], lean["name"], lean["suffix"], lean["mtime_utc"],
            lean["sha256"], lean["content_class"], int(lean["content_signature_verified"]),
            int(lean["full_text_read"]), lean["text_characters_read"], lean["line_count_read"], _canonical(dict(record)),
        ),
    )


def _import_cache(conn: sqlite3.Connection, cache: Mapping[str, Any]) -> None:
    for key, value in cache.items():
        if not isinstance(value, dict) or not isinstance(value.get("record"), dict):
            raise core.HanriError(f"invalid cache row: {key}")
        _insert_row(conn, str(key), int(value["size_bytes"]), int(value["mtime_ns"]), value["record"])
    conn.commit()


def _classify_sqlite(
    conn: sqlite3.Connection,
    metadata: Sequence[tuple[Path, int, int]],
    fresh: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int, int]:
    rows: list[dict[str, Any]] = []
    hits = 0
    misses = 0
    changed = 0
    query = (
        "SELECT size_bytes,mtime_ns,path,name,suffix,mtime_utc,sha256,content_class,"
        "content_signature_verified,full_text_read,text_characters_read,line_count_read "
        "FROM inventory WHERE path_key=?"
    )
    for path, size_bytes, mtime_ns in metadata:
        key = _path_key(path)
        row = conn.execute(query, (key,)).fetchone()
        if row is not None and int(row[0]) == size_bytes and int(row[1]) == mtime_ns:
            rows.append({
                "path": row[2], "name": row[3], "suffix": row[4], "mtime_utc": row[5], "sha256": row[6],
                "content_class": row[7], "content_signature_verified": bool(row[8]), "full_text_read": bool(row[9]),
                "text_characters_read": int(row[10]), "line_count_read": int(row[11]), "size_bytes": size_bytes,
            })
            hits += 1
        else:
            record = dict(fresh[key])
            rows.append(_record_lean(record))
            _insert_row(conn, key, size_bytes, mtime_ns, record)
            misses += 1
            changed += 1
    return rows, hits, misses, changed


def _scope_summary(scope_id: str, sections: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    origin = list(sections["origin"])
    pivot = list(sections["pivot"])
    current = list(sections["current"])
    all_rows = origin + pivot + current
    scope = legacy.build_scope_coverage_certificate(
        scope_id, all_rows, evidence_ceiling="REGISTERED_CAUSAL_FRONTIER_FILES_ONLY", required_full_text=False
    )
    return {
        "scope_manifest_sha256": scope["scope_manifest_sha256"],
        "denominator": scope["denominator"],
        "coverage_ratio": scope["coverage_ratio"],
        "collision_sha256": _sha_text(_canonical(legacy.discover_same_name_collisions(all_rows))),
    }


def _selection_summary(sections: Mapping[str, Sequence[Mapping[str, Any]]], processed: set[str]) -> dict[str, Any]:
    def choose(name: str, newest: bool) -> dict[str, Any] | None:
        candidates = [row for row in sections[name] if str(row["sha256"]) not in processed]
        if not candidates:
            return None
        key = lambda row: (str(row["mtime_utc"]), str(row["path"]))
        row = max(candidates, key=key) if newest else min(candidates, key=key)
        return {"path": str(row["path"]), "sha256": str(row["sha256"])}
    return {"origin": choose("origin", False), "pivot": choose("pivot", False), "current": choose("current", True)}


def _db_logical_sha(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for row in conn.execute("SELECT path_key,size_bytes,mtime_ns,record_json FROM inventory ORDER BY path_key"):
        digest.update(_canonical([row[0], int(row[1]), int(row[2]), row[3]]).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _cache_logical_sha(cache: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(cache):
        value = cache[key]
        record_json = _canonical(value["record"])
        digest.update(_canonical([key, int(value["size_bytes"]), int(value["mtime_ns"]), record_json]).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def run_probe(config_path: Path) -> dict[str, Any]:
    raw = core.load_json(config_path)
    _validate_config(raw)
    state_root = core.expand_path(str(raw["state_root"])).resolve()
    projection_root = core.expand_path(str(raw["human_output_root"])).resolve()
    cache_path = state_root / "archive_inventory_cache.json"
    if not cache_path.exists():
        raise core.HanriError("accepted R33 inventory cache missing")
    live_before = _state_snapshot(state_root)
    r30.configure_excluded_roots([str(projection_root)])
    frontier = raw.get("archive_frontier", {})
    if frontier.get("enabled") is not True or not frontier.get("pivot_paths"):
        raise core.HanriError("R35 requires accepted R33 causal-spine config")
    max_bytes = int(frontier.get("max_read_bytes", 16 * 1024 * 1024))
    scope_id = str(frontier.get("scope_id", "CONTROL_CENTER_REGISTERED_CAUSAL_FRONTIERS_R33"))

    load_started = time.perf_counter()
    cache = core.load_json(cache_path)
    json_load_ms = round((time.perf_counter() - load_started) * 1000.0, 3)

    enum_started = time.perf_counter()
    metadata_sections = {
        "origin": _metadata_snapshot([core.expand_path(str(v)) for v in frontier.get("origin_paths", [])]),
        "pivot": _metadata_snapshot([core.expand_path(str(v)) for v in frontier.get("pivot_paths", [])]),
        "current": _metadata_snapshot([core.expand_path(str(v)) for v in frontier.get("current_paths", [])]),
    }
    enumeration_ms = round((time.perf_counter() - enum_started) * 1000.0, 3)
    fresh, inspection_ms = _fresh_records_for_misses(metadata_sections, cache, max_bytes)

    json_class_started = time.perf_counter()
    json_sections: dict[str, list[dict[str, Any]]] = {}
    json_next: dict[str, Any] = {}
    json_hits = 0
    json_misses = 0
    for name, metadata in metadata_sections.items():
        rows, next_rows, hits, misses = _classify_json(metadata, cache, fresh)
        json_sections[name] = rows
        json_next.update(next_rows)
        json_hits += hits
        json_misses += misses
    json_class_ms = round((time.perf_counter() - json_class_started) * 1000.0, 3)

    processed_path = state_root / "processed_event_hashes.json"
    processed_values = core.load_json(processed_path) if processed_path.exists() else []
    processed = {str(v).split(":", 1)[1] for v in processed_values if str(v).startswith("ARCHIVE:")}
    json_scope = _scope_summary(scope_id, json_sections)
    json_selection = _selection_summary(json_sections, processed)

    with tempfile.TemporaryDirectory(prefix="hanri-r35-sqlite-") as temp_dir:
        temp_root = Path(temp_dir)
        json_out = temp_root / "archive_inventory_cache.next.json"
        json_write_started = time.perf_counter()
        core.atomic_write_json(json_out, json_next)
        json_write_ms = round((time.perf_counter() - json_write_started) * 1000.0, 3)

        db_path = temp_root / "archive_inventory_cache.sqlite3"
        conn = _create_db(db_path)
        try:
            import_started = time.perf_counter()
            _import_cache(conn, cache)
            sqlite_import_ms = round((time.perf_counter() - import_started) * 1000.0, 3)

            sqlite_started = time.perf_counter()
            sqlite_sections: dict[str, list[dict[str, Any]]] = {}
            sqlite_hits = 0
            sqlite_misses = 0
            changed_rows = 0
            for name, metadata in metadata_sections.items():
                rows, hits, misses, changed = _classify_sqlite(conn, metadata, fresh)
                sqlite_sections[name] = rows
                sqlite_hits += hits
                sqlite_misses += misses
                changed_rows += changed
            lookup_upsert_ms = round((time.perf_counter() - sqlite_started) * 1000.0, 3)
            commit_started = time.perf_counter()
            conn.commit()
            sqlite_commit_ms = round((time.perf_counter() - commit_started) * 1000.0, 3)

            sqlite_scope = _scope_summary(scope_id, sqlite_sections)
            sqlite_selection = _selection_summary(sqlite_sections, processed)
            parity_started = time.perf_counter()
            json_logical_sha = _cache_logical_sha(json_next)
            sqlite_logical_sha = _db_logical_sha(conn)
            parity_materialization_ms = round((time.perf_counter() - parity_started) * 1000.0, 3)
        finally:
            conn.close()

    live_after = _state_snapshot(state_root)
    json_operational = round(json_load_ms + enumeration_ms + inspection_ms + json_class_ms + json_write_ms, 3)
    sqlite_operational = round(enumeration_ms + inspection_ms + lookup_upsert_ms + sqlite_commit_ms, 3)
    parity = {
        "path_count_equal": sum(len(v) for v in json_sections.values()) == sum(len(v) for v in sqlite_sections.values()),
        "cache_hits_equal": json_hits == sqlite_hits,
        "cache_misses_equal": json_misses == sqlite_misses,
        "scope_equal": json_scope == sqlite_scope,
        "selection_equal": json_selection == sqlite_selection,
        "next_cache_logical_equal": json_logical_sha == sqlite_logical_sha,
    }
    failures = [name for name, passed in parity.items() if not passed]
    live_unchanged = live_before == live_after
    if not live_unchanged:
        failures.append("live_r33_state_unchanged")

    return {
        "schema_version": 1,
        "probe_version": PROBE_VERSION,
        "probe_mode": PROBE_MODE,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "accepted_runtime_version": EXPECTED_PROGRAM_VERSION,
        "counts": {
            "files_seen": sum(len(v) for v in metadata_sections.values()),
            "json_cache_hits": json_hits,
            "json_cache_misses": json_misses,
            "sqlite_cache_hits": sqlite_hits,
            "sqlite_cache_misses": sqlite_misses,
            "sqlite_changed_rows_committed": changed_rows,
        },
        "parity": parity,
        "json_reference": {"scope": json_scope, "selection": json_selection, "next_cache_logical_sha256": json_logical_sha},
        "sqlite": {"scope": sqlite_scope, "selection": sqlite_selection, "next_cache_logical_sha256": sqlite_logical_sha},
        "timings_ms": {
            "common_metadata_enumeration": enumeration_ms,
            "common_content_inspection": inspection_ms,
            "json_cache_load": json_load_ms,
            "json_classification": json_class_ms,
            "json_cache_atomic_write": json_write_ms,
            "json_operational_total": json_operational,
            "sqlite_one_time_import": sqlite_import_ms,
            "sqlite_lookup_and_changed_row_upsert": lookup_upsert_ms,
            "sqlite_commit": sqlite_commit_ms,
            "sqlite_operational_total": sqlite_operational,
            "parity_materialization_excluded_from_operational": parity_materialization_ms,
        },
        "operational_speedup_x": round(json_operational / sqlite_operational, 3) if sqlite_operational > 0 else None,
        "safety": {
            "live_r33_state_unchanged_during_probe": live_unchanged,
            "drive_hanri_r33_writes": 0,
            "scheduler_changes": 0,
            "runtime_install_or_promotion": False,
            "source_repository_writes": False,
            "external_model_api_calls": 0,
            "self_application": False,
            "can_trade": False,
            "capital_permission": "DENY",
            "sqlite_location": "TEMP_ONLY",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R35 isolated JSON vs SQLite inventory-cache A/B probe")
    parser.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_probe(args.config)
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error, core.HanriError) as exc:
        print(_canonical({"status": "ERROR", "probe_version": PROBE_VERSION, "error": type(exc).__name__, "message": str(exc), "can_trade": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
