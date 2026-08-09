from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from . import cli as core
from . import delta_cli as r30
from . import steady_cli as base

PROGRAM_VERSION = base.PROGRAM_VERSION
ACTOR = base.ACTOR
HUMAN_LABEL = base.HUMAN_LABEL
INTEGRITY_POLICY_VERSION = "32.0.0-steady-integrity-v1"
INTEGRITY_MODE = "STREAMING_SHA256_NO_JSON_PARSE"

_BASE_FAST_CONTEXT = base._fast_path_context
_BASE_RUN_FAST_PATH = base._run_fast_path
_BASE_COPY_OUTPUTS = base.copy_latest_outputs_r32


def _heavy_snapshot_raw_sha256(paths: Sequence[Path]) -> dict[str, str]:
    return {path.name: core.sha256_file(path) for path in paths}


def _heavy_snapshot_bytes(paths: Sequence[Path]) -> int:
    return sum(path.stat().st_size for path in paths)


def copy_latest_outputs_r32_integrity(source_root: Path, target_root: Path) -> dict[str, Any]:
    receipt = _BASE_COPY_OUTPUTS(source_root, target_root)
    heavy_paths = [source_root / name for name in r30._HEAVY_SNAPSHOTS if (source_root / name).exists()]
    receipt["heavy_snapshot_raw_sha256"] = _heavy_snapshot_raw_sha256(heavy_paths)
    receipt["heavy_snapshot_integrity_mode"] = INTEGRITY_MODE
    receipt["heavy_snapshot_bytes_hashed"] = _heavy_snapshot_bytes(heavy_paths)
    receipt["integrity_policy_version"] = INTEGRITY_POLICY_VERSION
    policy = dict(receipt.get("material_policy", {}))
    policy["fast_path_streaming_sha256_integrity"] = True
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

    actual = _heavy_snapshot_raw_sha256(heavy_paths)
    if actual != {str(key): str(value) for key, value in expected.items()}:
        return False, "HEAVY_RAW_SHA_MISMATCH", {}

    context = dict(context)
    context["heavy_snapshot_raw_sha256"] = actual
    context["heavy_snapshot_bytes_hashed"] = _heavy_snapshot_bytes(heavy_paths)
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
    projection["heavy_snapshot_integrity_mode"] = INTEGRITY_MODE
    projection["heavy_snapshot_bytes_hashed"] = int(context.get("heavy_snapshot_bytes_hashed", 0))
    projection["integrity_policy_version"] = INTEGRITY_POLICY_VERSION
    policy = dict(projection.get("material_policy", {}))
    policy["fast_path_streaming_sha256_integrity"] = True
    policy["heavy_json_parse_required_on_fast_path"] = False
    projection["material_policy"] = policy
    core.atomic_write_json(projection_path, projection)

    receipt = dict(receipt)
    receipt["fast_path_integrity_verified"] = True
    receipt["heavy_snapshot_integrity_mode"] = INTEGRITY_MODE
    receipt["heavy_snapshot_bytes_hashed"] = int(context.get("heavy_snapshot_bytes_hashed", 0))
    core.atomic_write_json(state_root / "latest_run_receipt.json", receipt)
    core.atomic_write_json(state_root / f"run_{receipt['run_id']}.json", receipt)

    if config.get("human_output_root"):
        target_root = core.expand_path(str(config["human_output_root"]))
        target_root.mkdir(parents=True, exist_ok=True)
        r30._atomic_copy(projection_path, target_root / "latest_projection_receipt.json")
        r30._atomic_copy(state_root / "latest_run_receipt.json", target_root / "latest_run_receipt.json")
    return receipt


def install_r32_integrity_guard() -> None:
    base.install_r32_guard()
    base._fast_path_context = fast_path_context_integrity
    base._run_fast_path = run_fast_path_integrity
    core.copy_latest_outputs = copy_latest_outputs_r32_integrity
    core.process_once = base.r32_process_once
    core.status = base.r32_status


def main(argv: Sequence[str] | None = None) -> int:
    install_r32_integrity_guard()
    return core.main(argv)
