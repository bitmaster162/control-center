from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import cli as core
from . import delta_cli as r30
from . import steady_cli as base

PROGRAM_VERSION = base.PROGRAM_VERSION
ACTOR = base.ACTOR
HUMAN_LABEL = base.HUMAN_LABEL
INTEGRITY_POLICY_VERSION = "36.0.0-heartbeat-integrity-fast-gate-v1"
INTEGRITY_MODE = "STREAMING_SHA256_NO_JSON_PARSE"
CACHED_INTEGRITY_MODE = "CACHED_STAT_GUARD"
DEFAULT_FULL_REHASH_INTERVAL_SECONDS = 900
MIN_FULL_REHASH_INTERVAL_SECONDS = 60

_BASE_FAST_CONTEXT = base._fast_path_context
_BASE_RUN_FAST_PATH = base._run_fast_path
_BASE_COPY_OUTPUTS = base.copy_latest_outputs_r32
_FULL_PROCESS_ONCE = base._RAW_PROCESS_ONCE


def _heavy_snapshot_raw_sha256(paths: Sequence[Path]) -> dict[str, str]:
    return {path.name: core.sha256_file(path) for path in paths}


def _heavy_snapshot_bytes(paths: Sequence[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def _heavy_snapshot_stat_checkpoint(paths: Sequence[Path]) -> dict[str, dict[str, int]]:
    checkpoint: dict[str, dict[str, int]] = {}
    for path in paths:
        stat = path.stat()
        checkpoint[path.name] = {
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
    return checkpoint


def _full_rehash_interval_seconds(config: Mapping[str, Any]) -> int:
    try:
        configured = int(
            config.get(
                "integrity_full_rehash_interval_seconds",
                DEFAULT_FULL_REHASH_INTERVAL_SECONDS,
            )
        )
    except (TypeError, ValueError):
        configured = DEFAULT_FULL_REHASH_INTERVAL_SECONDS
    interval = max(configured, MIN_FULL_REHASH_INTERVAL_SECONDS)

    frontier = config.get("archive_frontier", {})
    if isinstance(frontier, Mapping) and frontier.get("enabled") is True:
        try:
            scan_interval = int(
                frontier.get("scan_interval_seconds", DEFAULT_FULL_REHASH_INTERVAL_SECONDS)
            )
        except (TypeError, ValueError):
            scan_interval = DEFAULT_FULL_REHASH_INTERVAL_SECONDS
        interval = min(interval, max(scan_interval, MIN_FULL_REHASH_INTERVAL_SECONDS))
    return interval


def copy_latest_outputs_r32_integrity(source_root: Path, target_root: Path) -> dict[str, Any]:
    receipt = _BASE_COPY_OUTPUTS(source_root, target_root)
    heavy_paths = [source_root / name for name in r30._HEAVY_SNAPSHOTS if (source_root / name).exists()]
    started = time.perf_counter()
    receipt["heavy_snapshot_raw_sha256"] = _heavy_snapshot_raw_sha256(heavy_paths)
    receipt["heavy_snapshot_integrity_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    receipt["heavy_snapshot_integrity_mode"] = INTEGRITY_MODE
    receipt["heavy_snapshot_bytes_hashed"] = _heavy_snapshot_bytes(heavy_paths)
    receipt["heavy_snapshot_stat_checkpoint"] = _heavy_snapshot_stat_checkpoint(heavy_paths)
    receipt["heavy_snapshot_full_verified_at"] = core.iso_utc()
    receipt["heavy_snapshot_full_sha_performed"] = True
    receipt["heavy_snapshot_integrity_cache_age_seconds"] = 0.0
    receipt["heavy_snapshot_integrity_refresh_reason"] = "FULL_PROJECTION"
    receipt["integrity_policy_version"] = INTEGRITY_POLICY_VERSION
    policy = dict(receipt.get("material_policy", {}))
    policy["fast_path_streaming_sha256_integrity"] = True
    policy["fast_path_cached_stat_integrity_gate"] = True
    policy["fast_path_full_rehash_required_periodically"] = True
    policy["fast_path_heavy_sha_passes"] = 1
    policy["heavy_json_parse_required_on_fast_path"] = False
    receipt["material_policy"] = policy
    local = source_root / "latest_projection_receipt.json"
    core.atomic_write_json(local, receipt)
    r30._atomic_copy(local, target_root / "latest_projection_receipt.json")
    return receipt


def fast_path_context_integrity(
    config_path: Path,
    config: Mapping[str, Any],
) -> tuple[bool, str, dict[str, Any]]:
    eligible, reason, context = _BASE_FAST_CONTEXT(config_path, config)
    if not eligible:
        return eligible, reason, context

    previous_projection = context.get("previous_projection", {})
    expected = previous_projection.get("heavy_snapshot_raw_sha256") if isinstance(previous_projection, dict) else None
    heavy_paths = [Path(path) for path in context.get("heavy_paths", [])]
    if not isinstance(expected, dict) or not expected:
        return False, "HEAVY_RAW_SHA_CHECKPOINT_MISSING", {}
    if set(expected) != {path.name for path in heavy_paths}:
        return False, "HEAVY_RAW_SHA_CHECKPOINT_SET_MISMATCH", {}

    expected_normalized = {str(key): str(value) for key, value in expected.items()}
    interval_seconds = _full_rehash_interval_seconds(config)

    stat_started = time.perf_counter()
    current_stats = _heavy_snapshot_stat_checkpoint(heavy_paths)
    stat_elapsed_ms = round((time.perf_counter() - stat_started) * 1000.0, 3)

    previous_stats = previous_projection.get("heavy_snapshot_stat_checkpoint")
    full_verified_at = previous_projection.get("heavy_snapshot_full_verified_at")
    cache_age_seconds: float | None = None
    refresh_reason: str | None = None

    if not isinstance(previous_stats, dict) or not previous_stats:
        refresh_reason = "STAT_CHECKPOINT_MISSING"
    elif previous_stats != current_stats:
        refresh_reason = "STAT_CHECKPOINT_CHANGED"
    elif not isinstance(full_verified_at, str) or not full_verified_at:
        refresh_reason = "FULL_VERIFIED_AT_MISSING"
    else:
        try:
            cache_age_seconds = (core.utc_now() - core.parse_iso(full_verified_at)).total_seconds()
        except (TypeError, ValueError):
            refresh_reason = "FULL_VERIFIED_AT_INVALID"
        else:
            if cache_age_seconds < 0:
                refresh_reason = "CLOCK_ROLLBACK"
            elif cache_age_seconds >= interval_seconds:
                refresh_reason = "FULL_REHASH_INTERVAL_DUE"

    if refresh_reason is None:
        context = dict(context)
        context["heavy_snapshot_raw_sha256"] = expected_normalized
        context["heavy_snapshot_stat_checkpoint"] = current_stats
        context["heavy_snapshot_full_verified_at"] = full_verified_at
        context["heavy_snapshot_full_sha_performed"] = False
        context["heavy_snapshot_integrity_mode"] = CACHED_INTEGRITY_MODE
        context["heavy_snapshot_bytes_hashed"] = 0
        context["heavy_snapshot_integrity_elapsed_ms"] = stat_elapsed_ms
        context["heavy_snapshot_integrity_cache_age_seconds"] = round(float(cache_age_seconds or 0.0), 3)
        context["heavy_snapshot_integrity_refresh_reason"] = None
        context["heavy_snapshot_full_rehash_interval_seconds"] = interval_seconds
        return True, reason, context

    hash_started = time.perf_counter()
    actual = _heavy_snapshot_raw_sha256(heavy_paths)
    hash_elapsed_ms = round((time.perf_counter() - hash_started) * 1000.0, 3)
    if actual != expected_normalized:
        return False, "HEAVY_RAW_SHA_MISMATCH", {}

    context = dict(context)
    context["heavy_snapshot_raw_sha256"] = actual
    context["heavy_snapshot_stat_checkpoint"] = current_stats
    context["heavy_snapshot_full_verified_at"] = core.iso_utc()
    context["heavy_snapshot_full_sha_performed"] = True
    context["heavy_snapshot_integrity_mode"] = INTEGRITY_MODE
    context["heavy_snapshot_bytes_hashed"] = _heavy_snapshot_bytes(heavy_paths)
    context["heavy_snapshot_integrity_elapsed_ms"] = round(stat_elapsed_ms + hash_elapsed_ms, 3)
    context["heavy_snapshot_integrity_cache_age_seconds"] = 0.0
    context["heavy_snapshot_integrity_refresh_reason"] = refresh_reason
    context["heavy_snapshot_full_rehash_interval_seconds"] = interval_seconds
    return True, reason, context


def run_fast_path_integrity(
    config_path: Path,
    config: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    receipt = _BASE_RUN_FAST_PATH(config_path, config, context)
    state_root = core.expand_path(str(config["state_root"]))
    projection_path = state_root / "latest_projection_receipt.json"
    projection = core.load_json(projection_path)
    projection.pop("heavy_snapshot_files_not_read", None)
    projection["heavy_snapshot_raw_sha256"] = dict(context.get("heavy_snapshot_raw_sha256", {}))
    projection["heavy_snapshot_stat_checkpoint"] = dict(context.get("heavy_snapshot_stat_checkpoint", {}))
    projection["heavy_snapshot_full_verified_at"] = context.get("heavy_snapshot_full_verified_at")
    projection["heavy_snapshot_full_sha_performed"] = bool(context.get("heavy_snapshot_full_sha_performed", False))
    projection["heavy_snapshot_integrity_mode"] = context.get("heavy_snapshot_integrity_mode", INTEGRITY_MODE)
    projection["heavy_snapshot_bytes_hashed"] = int(context.get("heavy_snapshot_bytes_hashed", 0))
    projection["heavy_snapshot_integrity_elapsed_ms"] = context.get("heavy_snapshot_integrity_elapsed_ms")
    projection["heavy_snapshot_integrity_cache_age_seconds"] = context.get(
        "heavy_snapshot_integrity_cache_age_seconds"
    )
    projection["heavy_snapshot_integrity_refresh_reason"] = context.get(
        "heavy_snapshot_integrity_refresh_reason"
    )
    projection["heavy_snapshot_full_rehash_interval_seconds"] = int(
        context.get(
            "heavy_snapshot_full_rehash_interval_seconds",
            _full_rehash_interval_seconds(config),
        )
    )
    projection["integrity_policy_version"] = INTEGRITY_POLICY_VERSION
    policy = dict(projection.get("material_policy", {}))
    policy["fast_path_streaming_sha256_integrity"] = bool(
        context.get("heavy_snapshot_full_sha_performed", False)
    )
    policy["fast_path_cached_stat_integrity_gate"] = True
    policy["fast_path_full_rehash_required_periodically"] = True
    policy["fast_path_heavy_sha_passes"] = 1 if context.get("heavy_snapshot_full_sha_performed") else 0
    policy["fast_path_full_rehash_interval_seconds"] = projection[
        "heavy_snapshot_full_rehash_interval_seconds"
    ]
    policy["heavy_json_parse_required_on_fast_path"] = False
    projection["material_policy"] = policy
    core.atomic_write_json(projection_path, projection)

    receipt = dict(receipt)
    receipt["fast_path_integrity_verified"] = True
    receipt["heavy_snapshot_integrity_mode"] = projection["heavy_snapshot_integrity_mode"]
    receipt["heavy_snapshot_full_sha_performed"] = projection["heavy_snapshot_full_sha_performed"]
    receipt["heavy_snapshot_bytes_hashed"] = projection["heavy_snapshot_bytes_hashed"]
    receipt["heavy_snapshot_integrity_elapsed_ms"] = projection["heavy_snapshot_integrity_elapsed_ms"]
    receipt["heavy_snapshot_integrity_cache_age_seconds"] = projection[
        "heavy_snapshot_integrity_cache_age_seconds"
    ]
    receipt["heavy_snapshot_integrity_refresh_reason"] = projection[
        "heavy_snapshot_integrity_refresh_reason"
    ]
    receipt["heavy_snapshot_full_verified_at"] = projection["heavy_snapshot_full_verified_at"]
    receipt["heavy_snapshot_full_rehash_interval_seconds"] = projection[
        "heavy_snapshot_full_rehash_interval_seconds"
    ]
    receipt["fast_path_total_observed_ms"] = round(
        float(receipt.get("fast_path_elapsed_ms", 0.0))
        + float(context.get("heavy_snapshot_integrity_elapsed_ms", 0.0)),
        3,
    )
    core.atomic_write_json(state_root / "latest_run_receipt.json", receipt)
    core.atomic_write_json(state_root / f"run_{receipt['run_id']}.json", receipt)

    if config.get("human_output_root"):
        target_root = core.expand_path(str(config["human_output_root"]))
        target_root.mkdir(parents=True, exist_ok=True)
        r30._atomic_copy(projection_path, target_root / "latest_projection_receipt.json")
        r30._atomic_copy(state_root / "latest_run_receipt.json", target_root / "latest_run_receipt.json")
    return receipt


def r32_process_once_integrity(config_path: Path) -> dict[str, Any]:
    config = base.r32_load_config(config_path)

    eligible, _, _ = _BASE_FAST_CONTEXT(config_path, config)
    if not eligible:
        return _FULL_PROCESS_ONCE(config_path)

    state_root = core.expand_path(str(config["state_root"]))
    lock_file = core.expand_path(str(config.get("lock_file", state_root / "hanri.lock")))
    with core.FileLock(lock_file, int(config.get("lock_stale_seconds", 1800))):
        eligible, _, context = fast_path_context_integrity(config_path, config)
        if eligible:
            return run_fast_path_integrity(config_path, config, context)

    return _FULL_PROCESS_ONCE(config_path)


def install_r32_integrity_guard() -> None:
    base.install_r32_guard()
    core.copy_latest_outputs = copy_latest_outputs_r32_integrity
    core.process_once = r32_process_once_integrity
    core.status = base.r32_status


def main(argv: Sequence[str] | None = None) -> int:
    install_r32_integrity_guard()
    return core.main(argv)
