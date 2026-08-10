from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import archive as legacy
from . import delta_cli as r30

SCAN_POLICY_VERSION = "33.0.0-scandir-metadata-cache-v1"
SCAN_ENGINE = "OS_SCANDIR_SINGLE_STAT_CACHE_REUSE"


def _path_key(path: Path) -> str:
    return str(path).casefold()


def _normalized(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _within(path: Path, root: Path) -> bool:
    path_text = _normalized(path)
    root_text = _normalized(root)
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False


def _excluded_roots() -> tuple[Path, ...]:
    return tuple(Path(value) for value in r30._EXCLUDED_ROOTS)


def _is_excluded(path: Path, excluded: Sequence[Path]) -> bool:
    return any(_within(path, root) for root in excluded)


def iter_file_metadata_scandir(
    values: Sequence[str | Path],
    allowed_suffixes: set[str] | None = None,
) -> Iterable[tuple[Path, os.stat_result]]:
    suffixes = allowed_suffixes or (legacy.TEXT_SUFFIXES | {".docx"})
    seen: set[str] = set()
    excluded = _excluded_roots()

    for raw in values:
        source = Path(raw).expanduser()
        if not source.exists():
            continue
        root = source.resolve()
        if _is_excluded(root, excluded):
            continue

        if root.is_file():
            if root.suffix.lower() not in suffixes:
                continue
            key = _path_key(root)
            if key in seen:
                continue
            seen.add(key)
            yield root, root.stat()
            continue

        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                entries = os.scandir(directory)
            except OSError:
                raise
            with entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        child = Path(entry.path)
                        if not _is_excluded(child, excluded):
                            stack.append(child)
                        continue

                    if Path(entry.name).suffix.lower() not in suffixes:
                        continue
                    if not entry.is_file(follow_symlinks=True):
                        continue

                    if entry.is_symlink():
                        path = Path(entry.path).resolve()
                    else:
                        path = Path(os.path.abspath(entry.path))
                    if _is_excluded(path, excluded):
                        continue
                    key = _path_key(path)
                    if key in seen:
                        continue
                    seen.add(key)
                    yield path, entry.stat(follow_symlinks=True)


def _scan_records(
    paths: Sequence[str | Path],
    cache: Mapping[str, Any],
    max_bytes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    next_cache: dict[str, Any] = {}
    hits = 0
    misses = 0
    started = time.perf_counter()

    for path, stat in iter_file_metadata_scandir(paths):
        key = _path_key(path)
        cached = cache.get(key)
        if (
            isinstance(cached, dict)
            and cached.get("size_bytes") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and isinstance(cached.get("record"), dict)
        ):
            record = dict(cached["record"])
            hits += 1
        else:
            record = legacy.inspect_file(path, max_bytes=max_bytes)
            misses += 1
        rows.append(record)
        next_cache[key] = {
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "record": record,
        }

    metrics = {
        "files_seen": len(rows),
        "cache_hits": hits,
        "cache_misses": misses,
        "elapsed_ms": int(round((time.perf_counter() - started) * 1000.0)),
    }
    return rows, next_cache, metrics


def scan_frontier_pair_scandir(
    origin_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
    inventory_cache: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    processed = processed_hashes or set()
    cache = inventory_cache or {}
    origin_items, origin_cache, _ = _scan_records(origin_paths, cache, max_bytes)
    current_items, current_cache, _ = _scan_records(current_paths, cache, max_bytes)
    next_cache = {**origin_cache, **current_cache}

    origin_unseen = [row for row in origin_items if row["sha256"] not in processed]
    current_unseen = [row for row in current_items if row["sha256"] not in processed]
    origin = min(origin_unseen, key=lambda row: (row["mtime_utc"], row["path"])) if origin_unseen else None
    current = max(current_unseen, key=lambda row: (row["mtime_utc"], row["path"])) if current_unseen else None
    all_items = origin_items + current_items
    pair = {
        "schema_version": 1,
        "generated_at": legacy.iso_utc(),
        "origin": origin,
        "current": current,
        "origin_files_seen": len(origin_items),
        "current_files_seen": len(current_items),
        "same_name_collisions": legacy.discover_same_name_collisions(all_items),
        "status": "PAIR_READY" if origin and current else "FRONTIER_INCOMPLETE",
        "inventory_cache_entries": len(next_cache),
        "can_trade": False,
    }
    return pair, next_cache


def scan_causal_spine_scandir(
    origin_paths: Sequence[str | Path],
    pivot_paths: Sequence[str | Path],
    current_paths: Sequence[str | Path],
    processed_hashes: set[str] | None = None,
    max_bytes: int = 16 * 1024 * 1024,
    inventory_cache: Mapping[str, Any] | None = None,
    scope_id: str = "ARCHIVE_CAUSAL_SPINE",
) -> tuple[dict[str, Any], dict[str, Any]]:
    processed = processed_hashes or set()
    cache = inventory_cache or {}

    origin_items, origin_cache, _ = _scan_records(origin_paths, cache, max_bytes)
    pivot_items, pivot_cache, _ = _scan_records(pivot_paths, cache, max_bytes)
    current_items, current_cache, _ = _scan_records(current_paths, cache, max_bytes)
    next_cache = {**origin_cache, **pivot_cache, **current_cache}

    def unseen(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if row["sha256"] not in processed]

    origin_candidates = unseen(origin_items)
    pivot_candidates = unseen(pivot_items)
    current_candidates = unseen(current_items)
    origin = min(origin_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if origin_candidates else None
    pivot = min(pivot_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if pivot_candidates else None
    current = max(current_candidates, key=lambda row: (row["mtime_utc"], row["path"])) if current_candidates else None

    all_items = origin_items + pivot_items + current_items
    scope = legacy.build_scope_coverage_certificate(
        scope_id,
        all_items,
        evidence_ceiling="REGISTERED_CAUSAL_FRONTIER_FILES_ONLY",
        required_full_text=False,
    )
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
        "inventory_cache_entries": len(next_cache),
        "causal_claim_authority": "NONE_UNTIL_HUMAN_OR_PRIMARY_EVIDENCE_ADJUDICATION",
        "can_trade": False,
    }
    return spine, next_cache
