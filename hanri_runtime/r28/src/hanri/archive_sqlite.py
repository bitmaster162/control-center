from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import archive as legacy
from . import archive_scandir

CACHE_JSON_NAME = "archive_inventory_cache.json"
DB_NAME = "archive_inventory_cache.sqlite3"
DB_SCHEMA_VERSION = "1"
STORAGE_POLICY_VERSION = "35.0.0-sqlite-bulk-index-v1"
STORAGE_ENGINE = "SQLITE_BULK_INDEX_SNAPSHOT_CHANGED_ROW_UPSERT"
_LAST_SCAN_METRICS: dict[str, Any] = {}


@dataclass(frozen=True)
class SQLiteInventoryHandle:
    seed_json_path: Path
    db_path: Path
    migration_performed: bool
    migration_seed_file_sha256: str
    migration_seed_logical_sha256: str
    migration_parity_verified: bool


@dataclass(frozen=True)
class SQLiteCacheWriteReceipt:
    db_path: Path
    entries: int
    changed_rows: int
    removed_rows: int


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _path_key(path: Path | str) -> str:
    return str(path).casefold()


def _cache_logical_sha(cache: Mapping[str, Any]) -> str:
    digest = hashlib.sha256()
    for key in sorted(cache):
        value = cache[key]
        if not isinstance(value, Mapping) or not isinstance(value.get("record"), Mapping):
            raise ValueError(f"invalid inventory seed row: {key}")
        record_json = _canonical(dict(value["record"]))
        digest.update(
            _canonical([str(key), int(value["size_bytes"]), int(value["mtime_ns"]), record_json]).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _db_logical_sha(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for row in conn.execute("SELECT path_key,size_bytes,mtime_ns,record_json FROM inventory ORDER BY path_key"):
        digest.update(_canonical([row[0], int(row[1]), int(row[2]), row[3]]).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory (
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) WITHOUT ROWID
        """
    )


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


def _upsert_record(
    conn: sqlite3.Connection,
    key: str,
    size_bytes: int,
    mtime_ns: int,
    record: Mapping[str, Any],
) -> None:
    lean = _record_lean(record)
    conn.execute(
        """
        INSERT OR REPLACE INTO inventory (
            path_key,size_bytes,mtime_ns,path,name,suffix,mtime_utc,sha256,content_class,
            content_signature_verified,full_text_read,text_characters_read,line_count_read,record_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            key,
            int(size_bytes),
            int(mtime_ns),
            lean["path"],
            lean["name"],
            lean["suffix"],
            lean["mtime_utc"],
            lean["sha256"],
            lean["content_class"],
            int(lean["content_signature_verified"]),
            int(lean["full_text_read"]),
            lean["text_characters_read"],
            lean["line_count_read"],
            _canonical(dict(record)),
        ),
    )


def _meta(conn: sqlite3.Connection) -> dict[str, str]:
    return {str(key): str(value) for key, value in conn.execute("SELECT key,value FROM meta")}


def _quick_check(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA quick_check").fetchone()
    return str(row[0]) if row else ""


def _migrate_seed(
    seed_json_path: Path,
    db_path: Path,
    raw_loader: Callable[[Path], Any],
) -> SQLiteInventoryHandle:
    seed = raw_loader(seed_json_path)
    if not isinstance(seed, dict) or not seed:
        raise ValueError("R35 requires non-empty accepted R33 inventory seed JSON")
    seed_file_sha = _sha256_file(seed_json_path)
    seed_logical_sha = _cache_logical_sha(seed)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_name(db_path.name + f".tmp-{uuid.uuid4().hex}")
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
            _create_schema(conn)
            for key in sorted(seed):
                value = seed[key]
                if not isinstance(value, Mapping) or not isinstance(value.get("record"), Mapping):
                    raise ValueError(f"invalid inventory seed row: {key}")
                _upsert_record(conn, str(key), int(value["size_bytes"]), int(value["mtime_ns"]), value["record"])
            meta_values = {
                "schema_version": DB_SCHEMA_VERSION,
                "storage_policy_version": STORAGE_POLICY_VERSION,
                "storage_engine": STORAGE_ENGINE,
                "migration_seed_file_sha256": seed_file_sha,
                "migration_seed_logical_sha256": seed_logical_sha,
                "migration_entry_count": str(len(seed)),
                "migration_parity_verified": "false",
                "seed_json_preserved": "true",
            }
            conn.executemany("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)", list(meta_values.items()))
            conn.commit()
            if _quick_check(conn) != "ok":
                raise ValueError("SQLite quick_check failed during migration")
            if _db_logical_sha(conn) != seed_logical_sha:
                raise ValueError("SQLite migration logical SHA parity failed")
            conn.execute(
                "INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)",
                ("migration_parity_verified", "true"),
            )
            conn.commit()
        finally:
            conn.close()
        os.replace(temporary, db_path)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass

    return SQLiteInventoryHandle(
        seed_json_path=seed_json_path,
        db_path=db_path,
        migration_performed=True,
        migration_seed_file_sha256=seed_file_sha,
        migration_seed_logical_sha256=seed_logical_sha,
        migration_parity_verified=True,
    )


def prepare_inventory_handle(
    seed_json_path: Path,
    raw_loader: Callable[[Path], Any],
) -> SQLiteInventoryHandle:
    seed_json_path = Path(seed_json_path)
    if seed_json_path.name != CACHE_JSON_NAME:
        raise ValueError("unexpected R35 inventory seed path")
    if not seed_json_path.exists():
        raise ValueError("R35 inventory seed JSON is missing")
    db_path = seed_json_path.with_name(DB_NAME)
    if not db_path.exists():
        return _migrate_seed(seed_json_path, db_path, raw_loader)

    seed_file_sha = _sha256_file(seed_json_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        _create_schema(conn)
        if _quick_check(conn) != "ok":
            raise ValueError("SQLite quick_check failed")
        meta = _meta(conn)
        if meta.get("schema_version") != DB_SCHEMA_VERSION:
            raise ValueError("SQLite inventory schema version mismatch")
        if meta.get("storage_policy_version") != STORAGE_POLICY_VERSION:
            raise ValueError("SQLite inventory policy version mismatch")
        if meta.get("storage_engine") != STORAGE_ENGINE:
            raise ValueError("SQLite inventory engine mismatch")
        if meta.get("migration_parity_verified") != "true":
            raise ValueError("SQLite migration parity evidence missing")
        if meta.get("migration_seed_file_sha256") != seed_file_sha:
            raise ValueError("R35 inventory seed JSON changed after migration")
    finally:
        conn.close()

    return SQLiteInventoryHandle(
        seed_json_path=seed_json_path,
        db_path=db_path,
        migration_performed=False,
        migration_seed_file_sha256=seed_file_sha,
        migration_seed_logical_sha256=meta["migration_seed_logical_sha256"],
        migration_parity_verified=True,
    )


def verify_inventory(db_path: Path, seed_json_path: Path) -> dict[str, Any]:
    db_path = Path(db_path)
    seed_json_path = Path(seed_json_path)
    result: dict[str, Any] = {
        "db_exists": db_path.exists(),
        "seed_exists": seed_json_path.exists(),
        "storage_policy_version": STORAGE_POLICY_VERSION,
        "storage_engine": STORAGE_ENGINE,
    }
    if not result["db_exists"] or not result["seed_exists"]:
        result["status"] = "FAIL"
        return result
    seed_file_sha = _sha256_file(seed_json_path)
    conn = sqlite3.connect(db_path)
    try:
        quick = _quick_check(conn)
        meta = _meta(conn)
        entries = int(conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0])
    finally:
        conn.close()
    result.update(
        {
            "quick_check": quick,
            "schema_version": meta.get("schema_version"),
            "meta_storage_policy_version": meta.get("storage_policy_version"),
            "meta_storage_engine": meta.get("storage_engine"),
            "migration_parity_verified": meta.get("migration_parity_verified") == "true",
            "seed_json_preserved": meta.get("seed_json_preserved") == "true",
            "seed_file_sha256": seed_file_sha,
            "migration_seed_file_sha256": meta.get("migration_seed_file_sha256"),
            "migration_seed_logical_sha256": meta.get("migration_seed_logical_sha256"),
            "entry_count": entries,
        }
    )
    result["status"] = (
        "PASS"
        if quick == "ok"
        and meta.get("schema_version") == DB_SCHEMA_VERSION
        and meta.get("storage_policy_version") == STORAGE_POLICY_VERSION
        and meta.get("storage_engine") == STORAGE_ENGINE
        and meta.get("migration_parity_verified") == "true"
        and meta.get("seed_json_preserved") == "true"
        and meta.get("migration_seed_file_sha256") == seed_file_sha
        else "FAIL"
    )
    return result


def _bulk_index(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT path_key,size_bytes,mtime_ns,path,name,suffix,mtime_utc,sha256,content_class,
               content_signature_verified,full_text_read,text_characters_read,line_count_read
        FROM inventory
        """
    )
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        index[str(row[0])] = {
            "size_bytes": int(row[1]),
            "mtime_ns": int(row[2]),
            "record": {
                "path": row[3],
                "name": row[4],
                "suffix": row[5],
                "mtime_utc": row[6],
                "sha256": row[7],
                "content_class": row[8],
                "content_signature_verified": bool(row[9]),
                "full_text_read": bool(row[10]),
                "text_characters_read": int(row[11]),
                "line_count_read": int(row[12]),
                "size_bytes": int(row[1]),
            },
        }
    return index


def _fetch_full_record(conn: sqlite3.Connection, item: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    key = _path_key(str(item["path"]))
    row = conn.execute("SELECT record_json FROM inventory WHERE path_key=?", (key,)).fetchone()
    if row is None:
        raise ValueError(f"selected inventory record missing: {item['path']}")
    record = json.loads(str(row[0]))
    if str(record.get("sha256")) != str(item.get("sha256")):
        raise ValueError(f"selected inventory record SHA mismatch: {item['path']}")
    return record


def _scan_section(
    conn: sqlite3.Connection,
    paths: Sequence[str | Path],
    index: dict[str, dict[str, Any]],
    max_bytes: int,
) -> tuple[list[dict[str, Any]], set[str], dict[str, int]]:
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    hits = 0
    misses = 0
    for path, stat in archive_scandir.iter_file_metadata_scandir(paths):
        key = _path_key(path)
        seen.add(key)
        cached = index.get(key)
        if (
            cached is not None
            and int(cached["size_bytes"]) == int(stat.st_size)
            and int(cached["mtime_ns"]) == int(stat.st_mtime_ns)
        ):
            rows.append(dict(cached["record"]))
            hits += 1
            continue
        record = legacy.inspect_file(path, max_bytes=max_bytes)
        _upsert_record(conn, key, int(stat.st_size), int(stat.st_mtime_ns), record)
        lean = _record_lean(record)
        index[key] = {
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "record": lean,
        }
        rows.append(lean)
        misses += 1
    return rows, seen, {
        "files_seen": len(rows),
        "cache_hits": hits,
        "cache_misses": misses,
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000.0)),
    }


def _publish_metrics(
    kind: str,
    sections: Mapping[str, Mapping[str, int]],
    started: float,
    handle: SQLiteInventoryHandle,
    *,
    bulk_index_ms: int,
    commit_ms: int,
    changed_rows: int,
    removed_rows: int,
    entries: int,
) -> None:
    global _LAST_SCAN_METRICS
    _LAST_SCAN_METRICS = {
        "scan_engine": archive_scandir.SCAN_ENGINE,
        "scan_policy_version": archive_scandir.SCAN_POLICY_VERSION,
        "scan_kind": kind,
        "sections": {str(key): dict(value) for key, value in sections.items()},
        "files_seen": sum(int(value.get("files_seen", 0)) for value in sections.values()),
        "cache_hits": sum(int(value.get("cache_hits", 0)) for value in sections.values()),
        "cache_misses": sum(int(value.get("cache_misses", 0)) for value in sections.values()),
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000.0)),
        "content_inspection_required_only_on_cache_miss": True,
        "inventory_backend": "SQLITE",
        "inventory_storage_policy_version": STORAGE_POLICY_VERSION,
        "inventory_storage_engine": STORAGE_ENGINE,
        "sqlite_bulk_index_snapshot": True,
        "sqlite_bulk_index_elapsed_ms": bulk_index_ms,
        "sqlite_changed_rows_committed": changed_rows,
        "sqlite_removed_rows_committed": removed_rows,
        "sqlite_commit_elapsed_ms": commit_ms,
        "sqlite_entry_count": entries,
        "sqlite_quick_check": "ok",
        "sqlite_migration_performed": handle.migration_performed,
        "sqlite_migration_parity_verified": handle.migration_parity_verified,
        "sqlite_seed_json_preserved": True,
        "sqlite_monolithic_json_rewrite": False,
        "sqlite_direct_json_fallback": False,
    }


def get_last_scan_metrics() -> dict[str, Any]:
    return dict(_LAST_SCAN_METRICS)


def _scan_all(
    handle: SQLiteInventoryHandle,
    sections_paths: Mapping[str, Sequence[str | Path]],
    max_bytes: int,
) -> tuple[sqlite3.Connection, dict[str, list[dict[str, Any]]], dict[str, dict[str, int]], int, int, int, int, int]:
    conn = sqlite3.connect(handle.db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    if _quick_check(conn) != "ok":
        conn.close()
        raise ValueError("SQLite quick_check failed before archive scan")

    bulk_started = time.perf_counter()
    index = _bulk_index(conn)
    bulk_index_ms = int(round((time.perf_counter() - bulk_started) * 1000.0))
    original_keys = set(index)
    all_seen: set[str] = set()
    section_rows: dict[str, list[dict[str, Any]]] = {}
    section_metrics: dict[str, dict[str, int]] = {}
    for name, paths in sections_paths.items():
        rows, seen, metrics = _scan_section(conn, paths, index, max_bytes)
        section_rows[name] = rows
        section_metrics[name] = metrics
        all_seen.update(seen)

    removed = sorted(original_keys - all_seen)
    if removed:
        conn.executemany("DELETE FROM inventory WHERE path_key=?", [(key,) for key in removed])
    changed_rows = sum(int(value.get("cache_misses", 0)) for value in section_metrics.values())
    commit_started = time.perf_counter()
    conn.commit()
    commit_ms = int(round((time.perf_counter() - commit_started) * 1000.0))
    entries = int(conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0])
    return conn, section_rows, section_metrics, bulk_index_ms, commit_ms, changed_rows, len(removed), entries


def scan_causal_spine_sqlite(
    origin_paths: Sequence[str | Path],
    pivot_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
    inventory_cache: Any = None,
    scope_id: str = "ARCHIVE_CAUSAL_SPINE",
) -> tuple[dict[str, Any], SQLiteCacheWriteReceipt]:
    if not isinstance(inventory_cache, SQLiteInventoryHandle):
        raise ValueError("R35 requires SQLite inventory handle; JSON fallback is denied")
    started = time.perf_counter()
    processed = processed_hashes or set()
    conn, sections, metrics, bulk_ms, commit_ms, changed, removed, entries = _scan_all(
        inventory_cache,
        {"origin": origin_paths, "pivot": pivot_paths, "current": current_paths},
        max_bytes,
    )
    try:
        origin_items = sections["origin"]
        pivot_items = sections["pivot"]
        current_items = sections["current"]

        def unseen(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
            return [row for row in rows if str(row["sha256"]) not in processed]

        origin_candidates = unseen(origin_items)
        pivot_candidates = unseen(pivot_items)
        current_candidates = unseen(current_items)
        origin_lean = min(origin_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if origin_candidates else None
        pivot_lean = min(pivot_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if pivot_candidates else None
        current_lean = max(current_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if current_candidates else None

        all_items = origin_items + pivot_items + current_items
        scope = legacy.build_scope_coverage_certificate(
            scope_id,
            all_items,
            evidence_ceiling="REGISTERED_CAUSAL_FRONTIER_FILES_ONLY",
            required_full_text=False,
        )
        origin = _fetch_full_record(conn, origin_lean)
        pivot = _fetch_full_record(conn, pivot_lean)
        current = _fetch_full_record(conn, current_lean)
        spine = {
            "schema_version": 1,
            "generated_at": legacy.iso_utc(),
            "scope_id": scope_id,
            "origin": origin,
            "pivot": pivot,
            "current": current,
            "origin_files_seen": len(origin_items),
            "pivot_files_seen": len(pivot_items),
            "current_files_seen": len(current_items),
            "same_name_collisions": legacy.discover_same_name_collisions(all_items),
            "coverage_certificate": scope,
            "status": "SPINE_READY" if origin and pivot and current else "CAUSAL_SPINE_INCOMPLETE",
            "inventory_cache_entries": entries,
            "causal_claim_authority": "NONE_UNTIL_HUMAN_OR_PRIMARY_EVIDENCE_ADJUDICATION",
            "can_trade": False,
        }
        _publish_metrics(
            "CAUSAL_SPINE",
            metrics,
            started,
            inventory_cache,
            bulk_index_ms=bulk_ms,
            commit_ms=commit_ms,
            changed_rows=changed,
            removed_rows=removed,
            entries=entries,
        )
        return spine, SQLiteCacheWriteReceipt(inventory_cache.db_path, entries, changed, removed)
    finally:
        conn.close()


def scan_frontier_pair_sqlite(
    origin_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
    inventory_cache: Any = None,
) -> tuple[dict[str, Any], SQLiteCacheWriteReceipt]:
    if not isinstance(inventory_cache, SQLiteInventoryHandle):
        raise ValueError("R35 requires SQLite inventory handle; JSON fallback is denied")
    started = time.perf_counter()
    processed = processed_hashes or set()
    conn, sections, metrics, bulk_ms, commit_ms, changed, removed, entries = _scan_all(
        inventory_cache,
        {"origin": origin_paths, "current": current_paths},
        max_bytes,
    )
    try:
        origin_items = sections["origin"]
        current_items = sections["current"]
        origin_candidates = [row for row in origin_items if str(row["sha256"]) not in processed]
        current_candidates = [row for row in current_items if str(row["sha256"]) not in processed]
        origin_lean = min(origin_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if origin_candidates else None
        current_lean = max(current_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if current_candidates else None
        all_items = origin_items + current_items
        origin = _fetch_full_record(conn, origin_lean)
        current = _fetch_full_record(conn, current_lean)
        pair = {
            "schema_version": 1,
            "generated_at": legacy.iso_utc(),
            "origin": origin,
            "current": current,
            "origin_files_seen": len(origin_items),
            "current_files_seen": len(current_items),
            "same_name_collisions": legacy.discover_same_name_collisions(all_items),
            "status": "PAIR_READY" if origin and current else "FRONTIER_INCOMPLETE",
            "inventory_cache_entries": entries,
            "can_trade": False,
        }
        _publish_metrics(
            "FRONTIER_PAIR",
            metrics,
            started,
            inventory_cache,
            bulk_index_ms=bulk_ms,
            commit_ms=commit_ms,
            changed_rows=changed,
            removed_rows=removed,
            entries=entries,
        )
        return pair, SQLiteCacheWriteReceipt(inventory_cache.db_path, entries, changed, removed)
    finally:
        conn.close()


def finalize_inventory_write(path: Path, value: Any) -> None:
    if not isinstance(value, SQLiteCacheWriteReceipt):
        raise ValueError("R35 inventory JSON rewrite denied: expected SQLite write receipt")
    expected_db = Path(path).with_name(DB_NAME)
    if expected_db.resolve() != value.db_path.resolve():
        raise ValueError("R35 inventory write receipt DB path mismatch")
    conn = sqlite3.connect(expected_db)
    try:
        if _quick_check(conn) != "ok":
            raise ValueError("SQLite quick_check failed during cache finalization")
        entries = int(conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0])
    finally:
        conn.close()
    if entries != int(value.entries):
        raise ValueError("R35 inventory entry count changed before finalization")
