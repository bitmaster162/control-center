from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import archive
from . import cli as core

PROBE_VERSION = "33.0.0-probe-v1"
PROBE_MODE = "READ_ONLY_METADATA_ONLY"
_ALLOWED_SUFFIXES = archive.TEXT_SUFFIXES | {".docx"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _assert_r32_probe_config(config: Mapping[str, Any]) -> None:
    if str(config.get("program_version")) != "32.0.0":
        raise ValueError("R33 probe requires accepted R32 config program_version=32.0.0")
    if config.get("shadow_only") is not True:
        raise ValueError("R33 probe requires shadow_only=true")
    if config.get("can_trade") is not False:
        raise ValueError("R33 probe requires can_trade=false")
    if str(config.get("external_model_api")) != "DENY":
        raise ValueError("R33 probe requires external_model_api=DENY")
    state_root = str(config.get("state_root", ""))
    if "ControlCenterHANRIR32" not in state_root:
        raise ValueError("R33 probe may read only the isolated R32 state root")


def _profile_root(
    raw_root: str,
    cache: Mapping[str, Any],
    seen: set[str],
) -> dict[str, Any]:
    root = core.expand_path(raw_root)
    started = time.perf_counter()
    type_check_seconds = 0.0
    resolve_seconds = 0.0
    metadata_stat_seconds = 0.0
    files_seen = 0
    cache_hits = 0
    cache_missing = 0
    cache_stale = 0
    duplicate_paths_skipped = 0
    unsupported_suffix_skipped = 0
    root_exists = root.exists()

    if not root_exists:
        return {
            "root": str(root),
            "root_exists": False,
            "files_seen": 0,
            "cache_hits": 0,
            "cache_missing": 0,
            "cache_stale": 0,
            "cache_misses": 0,
            "would_require_content_inspection": 0,
            "duplicate_paths_skipped": 0,
            "unsupported_suffix_skipped": 0,
            "root_total_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "type_check_ms": 0.0,
            "resolve_ms": 0.0,
            "metadata_stat_ms": 0.0,
            "enumeration_residual_ms": 0.0,
        }

    candidates = [root] if root.is_file() else root.rglob("*")
    for candidate in candidates:
        check_started = time.perf_counter()
        is_file = candidate.is_file()
        type_check_seconds += time.perf_counter() - check_started
        if not is_file:
            continue
        if candidate.suffix.lower() not in _ALLOWED_SUFFIXES:
            unsupported_suffix_skipped += 1
            continue

        resolve_started = time.perf_counter()
        resolved = candidate.resolve()
        resolve_seconds += time.perf_counter() - resolve_started
        key = str(resolved).casefold()
        if key in seen:
            duplicate_paths_skipped += 1
            continue
        seen.add(key)

        stat_started = time.perf_counter()
        stat = resolved.stat()
        metadata_stat_seconds += time.perf_counter() - stat_started
        files_seen += 1

        cached = cache.get(key)
        if not isinstance(cached, dict):
            cache_missing += 1
            continue
        if (
            cached.get("size_bytes") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and isinstance(cached.get("record"), dict)
        ):
            cache_hits += 1
        else:
            cache_stale += 1

    total_seconds = time.perf_counter() - started
    measured_seconds = type_check_seconds + resolve_seconds + metadata_stat_seconds
    cache_misses = cache_missing + cache_stale
    return {
        "root": str(root),
        "root_exists": True,
        "files_seen": files_seen,
        "cache_hits": cache_hits,
        "cache_missing": cache_missing,
        "cache_stale": cache_stale,
        "cache_misses": cache_misses,
        "would_require_content_inspection": cache_misses,
        "duplicate_paths_skipped": duplicate_paths_skipped,
        "unsupported_suffix_skipped": unsupported_suffix_skipped,
        "root_total_ms": round(total_seconds * 1000.0, 3),
        "type_check_ms": round(type_check_seconds * 1000.0, 3),
        "resolve_ms": round(resolve_seconds * 1000.0, 3),
        "metadata_stat_ms": round(metadata_stat_seconds * 1000.0, 3),
        "enumeration_residual_ms": round(max(total_seconds - measured_seconds, 0.0) * 1000.0, 3),
    }


def profile_archive_scan(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = _load_json(config_path)
    _assert_r32_probe_config(config)

    frontier = config.get("archive_frontier")
    if not isinstance(frontier, dict) or frontier.get("enabled") is not True:
        raise ValueError("R33 probe requires archive_frontier.enabled=true")

    state_root = core.expand_path(str(config["state_root"]))
    cache_path = state_root / "archive_inventory_cache.json"
    scope_path = state_root / "latest_archive_scope_certificate.json"
    cache = _load_json(cache_path)
    scope = _load_json(scope_path)

    started = time.perf_counter()
    sections: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    for section, config_key in (
        ("origin", "origin_paths"),
        ("pivot", "pivot_paths"),
        ("current", "current_paths"),
    ):
        rows: list[dict[str, Any]] = []
        for raw_root in frontier.get(config_key, []):
            rows.append(_profile_root(str(raw_root), cache, seen))
        sections[section] = rows

    all_rows = [row for rows in sections.values() for row in rows]
    files_seen = sum(int(row["files_seen"]) for row in all_rows)
    cache_hits = sum(int(row["cache_hits"]) for row in all_rows)
    cache_missing = sum(int(row["cache_missing"]) for row in all_rows)
    cache_stale = sum(int(row["cache_stale"]) for row in all_rows)
    cache_misses = cache_missing + cache_stale
    observed_keys = set(seen)
    cache_keys = {str(key).casefold() for key in cache}
    cache_orphans = len(cache_keys - observed_keys)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)

    coverage_percent = scope.get("coverage_percent")
    denominator = scope.get("denominator")
    result = {
        "schema_version": 1,
        "probe_version": PROBE_VERSION,
        "probe_mode": PROBE_MODE,
        "accepted_runtime_version": "32.0.0",
        "config_path": str(config_path),
        "state_root": str(state_root),
        "inventory_cache_path": str(cache_path),
        "scope_certificate_path": str(scope_path),
        "archive_scope_id": frontier.get("scope_id"),
        "scan_interval_seconds": int(frontier.get("scan_interval_seconds", 900)),
        "sections": sections,
        "totals": {
            "files_seen": files_seen,
            "cache_entries": len(cache),
            "cache_hits": cache_hits,
            "cache_missing": cache_missing,
            "cache_stale": cache_stale,
            "cache_misses": cache_misses,
            "cache_orphans": cache_orphans,
            "would_require_content_inspection": cache_misses,
            "metadata_only_probe_elapsed_ms": elapsed_ms,
            "cache_hit_percent": round((cache_hits / files_seen * 100.0), 6) if files_seen else 0.0,
        },
        "previous_scope_certificate": {
            "scope_id": scope.get("scope_id"),
            "coverage_percent": coverage_percent,
            "denominator": denominator,
            "coverage_ratio": scope.get("coverage_ratio"),
            "status": scope.get("status"),
        },
        "safety": {
            "read_only": True,
            "writes_performed": 0,
            "file_content_reads_performed": 0,
            "network_calls": 0,
            "external_model_api_calls": 0,
            "source_repository_writes": False,
            "self_application": False,
            "can_trade": False,
        },
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R33 read-only archive scan profiler")
    parser.add_argument("--config", required=True, help="Path to accepted R32 config JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = profile_archive_scan(Path(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
