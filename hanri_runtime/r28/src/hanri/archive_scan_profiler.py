from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import archive
from . import cli as core

PROBE_VERSION = "33.0.0-probe-v2"
PROBE_MODE = "READ_ONLY_METADATA_AB_PARITY"
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


def _path_key(path: Path) -> str:
    return str(path).casefold()


def _within(path: Path, root: Path) -> bool:
    path_text = os.path.normcase(os.path.abspath(str(path)))
    root_text = os.path.normcase(os.path.abspath(str(root)))
    try:
        return os.path.commonpath([path_text, root_text]) == root_text
    except ValueError:
        return False


def _cache_class(cache: Mapping[str, Any], key: str, stat: os.stat_result) -> str:
    cached = cache.get(key)
    if not isinstance(cached, dict):
        return "missing"
    if (
        cached.get("size_bytes") == stat.st_size
        and cached.get("mtime_ns") == stat.st_mtime_ns
        and isinstance(cached.get("record"), dict)
    ):
        return "hit"
    return "stale"


def _empty_root_result(root: Path, mode: str, elapsed_ms: float) -> dict[str, Any]:
    return {
        "mode": mode,
        "root": str(root),
        "root_exists": False,
        "files_seen": 0,
        "cache_hits": 0,
        "cache_missing": 0,
        "cache_stale": 0,
        "cache_misses": 0,
        "would_require_content_inspection": 0,
        "duplicate_paths_skipped": 0,
        "excluded_projection_files": 0,
        "unsupported_suffix_skipped": 0,
        "root_total_ms": round(elapsed_ms, 3),
        "type_check_ms": 0.0,
        "resolve_ms": 0.0,
        "metadata_stat_ms": 0.0,
        "enumeration_residual_ms": 0.0,
        "path_keys": [],
        "cache_classes": {},
    }


def _finalize_root(
    *,
    mode: str,
    root: Path,
    started: float,
    type_check_seconds: float,
    resolve_seconds: float,
    metadata_stat_seconds: float,
    files_seen: int,
    cache_hits: int,
    cache_missing: int,
    cache_stale: int,
    duplicate_paths_skipped: int,
    excluded_projection_files: int,
    unsupported_suffix_skipped: int,
    path_keys: list[str],
    cache_classes: dict[str, str],
) -> dict[str, Any]:
    total_seconds = time.perf_counter() - started
    measured_seconds = type_check_seconds + resolve_seconds + metadata_stat_seconds
    cache_misses = cache_missing + cache_stale
    return {
        "mode": mode,
        "root": str(root),
        "root_exists": True,
        "files_seen": files_seen,
        "cache_hits": cache_hits,
        "cache_missing": cache_missing,
        "cache_stale": cache_stale,
        "cache_misses": cache_misses,
        "would_require_content_inspection": cache_misses,
        "duplicate_paths_skipped": duplicate_paths_skipped,
        "excluded_projection_files": excluded_projection_files,
        "unsupported_suffix_skipped": unsupported_suffix_skipped,
        "root_total_ms": round(total_seconds * 1000.0, 3),
        "type_check_ms": round(type_check_seconds * 1000.0, 3),
        "resolve_ms": round(resolve_seconds * 1000.0, 3),
        "metadata_stat_ms": round(metadata_stat_seconds * 1000.0, 3),
        "enumeration_residual_ms": round(max(total_seconds - measured_seconds, 0.0) * 1000.0, 3),
        "path_keys": sorted(path_keys),
        "cache_classes": dict(sorted(cache_classes.items())),
    }


def _profile_root_legacy(
    raw_root: str,
    cache: Mapping[str, Any],
    seen: set[str],
    excluded_roots: Sequence[Path],
) -> dict[str, Any]:
    root = core.expand_path(raw_root)
    started = time.perf_counter()
    type_check_seconds = 0.0
    resolve_seconds = 0.0
    metadata_stat_seconds = 0.0
    files_seen = cache_hits = cache_missing = cache_stale = 0
    duplicate_paths_skipped = excluded_projection_files = unsupported_suffix_skipped = 0
    path_keys: list[str] = []
    cache_classes: dict[str, str] = {}

    if not root.exists():
        return _empty_root_result(root, "legacy", (time.perf_counter() - started) * 1000.0)

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
        if any(_within(resolved, excluded) for excluded in excluded_roots):
            excluded_projection_files += 1
            continue
        key = _path_key(resolved)
        if key in seen:
            duplicate_paths_skipped += 1
            continue
        seen.add(key)

        stat_started = time.perf_counter()
        stat = resolved.stat()
        metadata_stat_seconds += time.perf_counter() - stat_started
        files_seen += 1
        path_keys.append(key)
        classification = _cache_class(cache, key, stat)
        cache_classes[key] = classification
        cache_hits += classification == "hit"
        cache_missing += classification == "missing"
        cache_stale += classification == "stale"

    return _finalize_root(
        mode="legacy",
        root=root,
        started=started,
        type_check_seconds=type_check_seconds,
        resolve_seconds=resolve_seconds,
        metadata_stat_seconds=metadata_stat_seconds,
        files_seen=files_seen,
        cache_hits=cache_hits,
        cache_missing=cache_missing,
        cache_stale=cache_stale,
        duplicate_paths_skipped=duplicate_paths_skipped,
        excluded_projection_files=excluded_projection_files,
        unsupported_suffix_skipped=unsupported_suffix_skipped,
        path_keys=path_keys,
        cache_classes=cache_classes,
    )


def _profile_root_scandir(
    raw_root: str,
    cache: Mapping[str, Any],
    seen: set[str],
    excluded_roots: Sequence[Path],
) -> dict[str, Any]:
    root = core.expand_path(raw_root)
    started = time.perf_counter()
    type_check_seconds = 0.0
    resolve_seconds = 0.0
    metadata_stat_seconds = 0.0
    files_seen = cache_hits = cache_missing = cache_stale = 0
    duplicate_paths_skipped = excluded_projection_files = unsupported_suffix_skipped = 0
    path_keys: list[str] = []
    cache_classes: dict[str, str] = {}

    if not root.exists():
        return _empty_root_result(root, "scandir", (time.perf_counter() - started) * 1000.0)

    root_resolve_started = time.perf_counter()
    root = root.resolve()
    resolve_seconds += time.perf_counter() - root_resolve_started
    stack = [root]
    while stack:
        directory = stack.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                check_started = time.perf_counter()
                is_dir = entry.is_dir(follow_symlinks=False)
                type_check_seconds += time.perf_counter() - check_started
                if is_dir:
                    stack.append(Path(entry.path))
                    continue

                suffix = Path(entry.name).suffix.lower()
                if suffix not in _ALLOWED_SUFFIXES:
                    unsupported_suffix_skipped += 1
                    continue

                check_started = time.perf_counter()
                is_file = entry.is_file(follow_symlinks=True)
                type_check_seconds += time.perf_counter() - check_started
                if not is_file:
                    continue

                path = Path(entry.path)
                if entry.is_symlink():
                    resolve_started = time.perf_counter()
                    path = path.resolve()
                    resolve_seconds += time.perf_counter() - resolve_started
                else:
                    path = Path(os.path.abspath(str(path)))

                if any(_within(path, excluded) for excluded in excluded_roots):
                    excluded_projection_files += 1
                    continue
                key = _path_key(path)
                if key in seen:
                    duplicate_paths_skipped += 1
                    continue
                seen.add(key)

                stat_started = time.perf_counter()
                stat = entry.stat(follow_symlinks=True)
                metadata_stat_seconds += time.perf_counter() - stat_started
                files_seen += 1
                path_keys.append(key)
                classification = _cache_class(cache, key, stat)
                cache_classes[key] = classification
                cache_hits += classification == "hit"
                cache_missing += classification == "missing"
                cache_stale += classification == "stale"

    return _finalize_root(
        mode="scandir",
        root=root,
        started=started,
        type_check_seconds=type_check_seconds,
        resolve_seconds=resolve_seconds,
        metadata_stat_seconds=metadata_stat_seconds,
        files_seen=files_seen,
        cache_hits=cache_hits,
        cache_missing=cache_missing,
        cache_stale=cache_stale,
        duplicate_paths_skipped=duplicate_paths_skipped,
        excluded_projection_files=excluded_projection_files,
        unsupported_suffix_skipped=unsupported_suffix_skipped,
        path_keys=path_keys,
        cache_classes=cache_classes,
    )


def _profile_sections(
    frontier: Mapping[str, Any],
    cache: Mapping[str, Any],
    excluded_roots: Sequence[Path],
    profiler: Any,
) -> tuple[dict[str, list[dict[str, Any]]], float]:
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
            rows.append(profiler(str(raw_root), cache, seen, excluded_roots))
        sections[section] = rows
    return sections, round((time.perf_counter() - started) * 1000.0, 3)


def _totals(sections: Mapping[str, Sequence[Mapping[str, Any]]], cache_entries: int, elapsed_ms: float) -> dict[str, Any]:
    rows = [row for group in sections.values() for row in group]
    files_seen = sum(int(row["files_seen"]) for row in rows)
    cache_hits = sum(int(row["cache_hits"]) for row in rows)
    cache_missing = sum(int(row["cache_missing"]) for row in rows)
    cache_stale = sum(int(row["cache_stale"]) for row in rows)
    return {
        "files_seen": files_seen,
        "cache_entries": cache_entries,
        "cache_hits": cache_hits,
        "cache_missing": cache_missing,
        "cache_stale": cache_stale,
        "cache_misses": cache_missing + cache_stale,
        "would_require_content_inspection": cache_missing + cache_stale,
        "metadata_only_probe_elapsed_ms": elapsed_ms,
        "cache_hit_percent": round((cache_hits / files_seen * 100.0), 6) if files_seen else 0.0,
        "excluded_projection_files": sum(int(row["excluded_projection_files"]) for row in rows),
    }


def _flatten_paths(sections: Mapping[str, Sequence[Mapping[str, Any]]]) -> set[str]:
    return {key for rows in sections.values() for row in rows for key in row.get("path_keys", [])}


def _flatten_classes(sections: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rows in sections.values():
        for row in rows:
            result.update({str(key): str(value) for key, value in dict(row.get("cache_classes", {})).items()})
    return result


def _strip_internal(sections: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    cleaned: dict[str, list[dict[str, Any]]] = {}
    for section, rows in sections.items():
        cleaned[section] = []
        for row in rows:
            value = dict(row)
            value.pop("path_keys", None)
            value.pop("cache_classes", None)
            cleaned[section].append(value)
    return cleaned


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
    human_output = config.get("human_output_root")
    excluded_roots = [core.expand_path(str(human_output)).resolve()] if human_output else []

    legacy_sections, legacy_elapsed = _profile_sections(frontier, cache, excluded_roots, _profile_root_legacy)
    scandir_sections, scandir_elapsed = _profile_sections(frontier, cache, excluded_roots, _profile_root_scandir)
    legacy_paths = _flatten_paths(legacy_sections)
    scandir_paths = _flatten_paths(scandir_sections)
    legacy_classes = _flatten_classes(legacy_sections)
    scandir_classes = _flatten_classes(scandir_sections)
    path_parity = legacy_paths == scandir_paths
    cache_class_parity = legacy_classes == scandir_classes
    parity_pass = path_parity and cache_class_parity

    legacy_totals = _totals(legacy_sections, len(cache), legacy_elapsed)
    scandir_totals = _totals(scandir_sections, len(cache), scandir_elapsed)
    speedup = (legacy_elapsed / scandir_elapsed) if scandir_elapsed > 0 else None
    scope_denominator = scope.get("denominator")
    runtime_scope_parity = isinstance(scope_denominator, int) and legacy_totals["files_seen"] == scope_denominator

    return {
        "schema_version": 2,
        "probe_version": PROBE_VERSION,
        "probe_mode": PROBE_MODE,
        "accepted_runtime_version": "32.0.0",
        "config_path": str(config_path),
        "state_root": str(state_root),
        "inventory_cache_path": str(cache_path),
        "scope_certificate_path": str(scope_path),
        "archive_scope_id": frontier.get("scope_id"),
        "scan_interval_seconds": int(frontier.get("scan_interval_seconds", 900)),
        "excluded_roots": [str(path) for path in excluded_roots],
        "legacy": {
            "sections": _strip_internal(legacy_sections),
            "totals": legacy_totals,
        },
        "scandir_candidate": {
            "sections": _strip_internal(scandir_sections),
            "totals": scandir_totals,
        },
        "parity": {
            "status": "PASS" if parity_pass and runtime_scope_parity else "FAIL",
            "path_set_equal": path_parity,
            "cache_classification_equal": cache_class_parity,
            "runtime_scope_denominator_equal": runtime_scope_parity,
            "legacy_only_paths": sorted(legacy_paths - scandir_paths)[:20],
            "scandir_only_paths": sorted(scandir_paths - legacy_paths)[:20],
            "speedup_x": round(speedup, 3) if speedup is not None else None,
            "legacy_elapsed_ms": legacy_elapsed,
            "scandir_elapsed_ms": scandir_elapsed,
        },
        "previous_scope_certificate": {
            "scope_id": scope.get("scope_id"),
            "coverage_percent": scope.get("coverage_percent"),
            "denominator": scope_denominator,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R33 read-only archive scan A/B profiler")
    parser.add_argument("--config", required=True, help="Path to accepted R32 config JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = profile_archive_scan(Path(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["parity"]["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
