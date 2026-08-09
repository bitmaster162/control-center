from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import archive as archive_mod
from . import cli as core
from . import delta_cli as r30

PROGRAM_VERSION = "31.0.0"
ACTOR = "HANRI_R31"
HUMAN_LABEL = "HANRI R31"
MATERIAL_POLICY_VERSION = "31.0.0-ai-state-stability-v1"

_RAW_LOAD_CONFIG = core.load_config
_AI_STATE_EPHEMERAL_TOP_LEVEL = frozenset({"new_events"})


def r31_load_config(path: Path) -> dict[str, Any]:
    config = _RAW_LOAD_CONFIG(path)
    if str(config.get("program_version", "")) != PROGRAM_VERSION:
        raise core.HanriError(
            f"R31 guard requires program_version={PROGRAM_VERSION}; got {config.get('program_version')!r}"
        )
    human_output_root = config.get("human_output_root")
    r30.configure_excluded_roots([str(human_output_root)] if human_output_root else [])
    return config


def r31_render_human_digest(
    run_id: str,
    findings: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    falsifications: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]],
    stop_reasons: Sequence[str],
) -> str:
    text = r30.r30_render_human_digest(
        run_id,
        findings,
        candidates,
        falsifications,
        decisions,
        stop_reasons,
    )
    old = "# Human Decision Digest — HANRI R30"
    new = f"# Human Decision Digest — {HUMAN_LABEL}"
    if old not in text:
        raise core.HanriError("R31 identity guard: expected R30 digest marker is missing")
    return text.replace(old, new, 1)


def r31_snapshot_event(path: Path, label: str) -> dict[str, Any]:
    event = r30.r30_snapshot_event(path, label)
    event["actor"] = ACTOR
    return event


def r31_archive_frontier_event(pair: Mapping[str, Any]) -> dict[str, Any]:
    event = r30.r30_archive_frontier_event(pair)
    event["actor"] = ACTOR
    return event


def r31_causal_spine_event(spine: Mapping[str, Any]) -> dict[str, Any]:
    event = r30.r30_causal_spine_event(spine)
    event["actor"] = ACTOR
    return event


def _material_value_for_path(path: Path, value: Any) -> Any:
    normalized = r30._material_value(value)
    if path.name == "latest_ai_state.json" and isinstance(normalized, dict):
        normalized = dict(normalized)
        for key in _AI_STATE_EPHEMERAL_TOP_LEVEL:
            normalized.pop(key, None)
    return normalized


def material_digest_r31(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return core.sha256_file(path)
    payload = json.dumps(
        _material_value_for_path(path, value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def copy_latest_outputs_stable(source_root: Path, target_root: Path) -> dict[str, Any]:
    target_root.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    skipped: list[str] = []
    bytes_avoided = 0
    material_digests: dict[str, str] = {}

    for name in r30._ALWAYS_PROJECT:
        source = source_root / name
        if not source.exists():
            continue
        r30._atomic_copy(source, target_root / name)
        copied.append(name)

    for name in r30._HEAVY_SNAPSHOTS:
        source = source_root / name
        if not source.exists():
            continue
        destination = target_root / name
        source_digest = material_digest_r31(source)
        material_digests[name] = source_digest
        if destination.exists() and material_digest_r31(destination) == source_digest:
            skipped.append(name)
            bytes_avoided += source.stat().st_size
            continue
        r30._atomic_copy(source, destination)
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
        "material_policy": {
            "version": MATERIAL_POLICY_VERSION,
            "inherited_recursive_volatile_keys": sorted(r30._VOLATILE_MATERIAL_KEYS),
            "latest_ai_state_ignored_top_level_keys": sorted(_AI_STATE_EPHEMERAL_TOP_LEVEL),
            "nested_new_events_remains_material": True,
            "new_findings_remains_material": True,
            "new_candidates_remains_material": True,
            "new_decisions_remains_material": True,
            "stop_reasons_remains_material": True,
        },
        "self_projection_excluded_from_archive": True,
        "external_model_api_calls": 0,
        "self_application": False,
        "can_trade": False,
    }
    local_receipt = source_root / "latest_projection_receipt.json"
    core.atomic_write_json(local_receipt, receipt)
    r30._atomic_copy(local_receipt, target_root / "latest_projection_receipt.json")
    return receipt


def install_r31_guard() -> None:
    r30.install_r30_guard()
    core.VERSION = PROGRAM_VERSION
    core.load_config = r31_load_config
    core.render_human_digest = r31_render_human_digest
    core.snapshot_event = r31_snapshot_event
    core.archive_frontier_event = r31_archive_frontier_event
    core.causal_spine_event = r31_causal_spine_event
    archive_mod.archive_frontier_event = r31_archive_frontier_event
    archive_mod.causal_spine_event = r31_causal_spine_event
    core.copy_latest_outputs = copy_latest_outputs_stable


def main(argv: Sequence[str] | None = None) -> int:
    install_r31_guard()
    return core.main(argv)
