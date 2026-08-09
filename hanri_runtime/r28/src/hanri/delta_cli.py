from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import archive as archive_mod
from . import cli as core
from . import identity_cli as r29

PROGRAM_VERSION = "30.0.0"
ACTOR = "HANRI_R30"
HUMAN_LABEL = "HANRI R30"

_RAW_LOAD_CONFIG = core.load_config
_BASE_ITER_FILES = archive_mod.iter_files

_EXCLUDED_ROOTS: tuple[Path, ...] = ()
_VOLATILE_MATERIAL_KEYS = frozenset({"generated_at", "run_id"})
_HEAVY_SNAPSHOTS = (
    "latest_ai_state.json",
    "latest_archive_frontier.json",
    "latest_archive_causal_spine.json",
    "latest_archive_scope_certificate.json",
)
_ALWAYS_PROJECT = (
    "latest_human_digest.md",
    "latest_run_receipt.json",
    "latest_health.csv",
    "latest_regression_suite.json",
)


def _resolved(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _is_within(path: Path, root: Path) -> bool:
    path_r = _resolved(path)
    root_r = _resolved(root)
    try:
        path_r.relative_to(root_r)
        return True
    except ValueError:
        return False


def configure_excluded_roots(values: Sequence[str | Path]) -> tuple[Path, ...]:
    global _EXCLUDED_ROOTS
    roots: list[Path] = []
    for raw in values:
        path = core.expand_path(str(raw)) if isinstance(raw, str) else Path(raw)
        roots.append(_resolved(path))
    _EXCLUDED_ROOTS = tuple(roots)
    return _EXCLUDED_ROOTS


def iter_files_excluding_projection(
    values: Sequence[str | Path],
    allowed_suffixes: set[str] | None = None,
) -> Iterable[Path]:
    for path in _BASE_ITER_FILES(values, allowed_suffixes=allowed_suffixes):
        if any(_is_within(path, root) for root in _EXCLUDED_ROOTS):
            continue
        yield path


def r30_load_config(path: Path) -> dict[str, Any]:
    config = _RAW_LOAD_CONFIG(path)
    if str(config.get("program_version", "")) != PROGRAM_VERSION:
        raise core.HanriError(
            f"R30 guard requires program_version={PROGRAM_VERSION}; got {config.get('program_version')!r}"
        )
    human_output_root = config.get("human_output_root")
    configure_excluded_roots([str(human_output_root)] if human_output_root else [])
    return config


def r30_render_human_digest(
    run_id: str,
    findings: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    falsifications: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]],
    stop_reasons: Sequence[str],
) -> str:
    text = r29.r29_render_human_digest(
        run_id,
        findings,
        candidates,
        falsifications,
        decisions,
        stop_reasons,
    )
    old = "# Human Decision Digest — HANRI R29"
    new = f"# Human Decision Digest — {HUMAN_LABEL}"
    if old not in text:
        raise core.HanriError("R30 identity guard: expected R29 digest marker is missing")
    return text.replace(old, new, 1)


def r30_snapshot_event(path: Path, label: str) -> dict[str, Any]:
    event = r29.r29_snapshot_event(path, label)
    event["actor"] = ACTOR
    return event


def r30_archive_frontier_event(pair: Mapping[str, Any]) -> dict[str, Any]:
    event = r29.r29_archive_frontier_event(pair)
    event["actor"] = ACTOR
    return event


def r30_causal_spine_event(spine: Mapping[str, Any]) -> dict[str, Any]:
    event = r29.r29_causal_spine_event(spine)
    event["actor"] = ACTOR
    return event


def _material_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _material_value(item)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
            if str(key) not in _VOLATILE_MATERIAL_KEYS
        }
    if isinstance(value, list):
        return [_material_value(item) for item in value]
    return value


def material_digest(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return core.sha256_file(path)
    payload = json.dumps(
        _material_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".tmp-{uuid.uuid4().hex}")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def copy_latest_outputs_delta(source_root: Path, target_root: Path) -> dict[str, Any]:
    target_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    skipped: list[str] = []
    bytes_avoided = 0
    material_digests: dict[str, str] = {}

    for name in _ALWAYS_PROJECT:
        source = source_root / name
        if not source.exists():
            continue
        _atomic_copy(source, target_root / name)
        copied.append(name)

    for name in _HEAVY_SNAPSHOTS:
        source = source_root / name
        if not source.exists():
            continue
        destination = target_root / name
        source_digest = material_digest(source)
        material_digests[name] = source_digest
        if destination.exists() and material_digest(destination) == source_digest:
            skipped.append(name)
            bytes_avoided += source.stat().st_size
            continue
        _atomic_copy(source, destination)
        copied.append(name)

    receipt = {
        "schema_version": 1,
        "program_version": PROGRAM_VERSION,
        "generated_at": core.iso_utc(),
        "projection_target": str(target_root),
        "copied": sorted(copied),
        "skipped_no_material_delta": sorted(skipped),
        "bytes_avoided": bytes_avoided,
        "material_digests": material_digests,
        "self_projection_excluded_from_archive": True,
        "external_model_api_calls": 0,
        "self_application": False,
        "can_trade": False,
    }
    local_receipt = source_root / "latest_projection_receipt.json"
    core.atomic_write_json(local_receipt, receipt)
    _atomic_copy(local_receipt, target_root / "latest_projection_receipt.json")
    return receipt


def install_r30_guard() -> None:
    r29.install_identity_guard()
    core.VERSION = PROGRAM_VERSION
    core.load_config = r30_load_config
    core.render_human_digest = r30_render_human_digest
    core.snapshot_event = r30_snapshot_event
    core.archive_frontier_event = r30_archive_frontier_event
    core.causal_spine_event = r30_causal_spine_event
    archive_mod.iter_files = iter_files_excluding_projection
    core.copy_latest_outputs = copy_latest_outputs_delta


def main(argv: Sequence[str] | None = None) -> int:
    install_r30_guard()
    return core.main(argv)
