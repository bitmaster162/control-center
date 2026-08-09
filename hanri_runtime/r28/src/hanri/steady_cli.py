from __future__ import annotations

import csv
import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import archive as archive_mod
from . import cli as core
from . import delta_cli as r30
from . import stability_cli as r31

PROGRAM_VERSION = "32.0.0"
ACTOR = "HANRI_R32"
HUMAN_LABEL = "HANRI R32"
STEADY_POLICY_VERSION = "32.0.0-heartbeat-fast-path-v1"
FAST_PATH_REASON = "NO_INPUT_OR_STATE_DELTA_AND_ARCHIVE_SCAN_NOT_DUE"

_RAW_LOAD_CONFIG = r31._RAW_LOAD_CONFIG
_RAW_PROCESS_ONCE = core.process_once
_RAW_STATUS = core.status


def r32_load_config(path: Path) -> dict[str, Any]:
    config = _RAW_LOAD_CONFIG(path)
    if str(config.get("program_version", "")) != PROGRAM_VERSION:
        raise core.HanriError(
            f"R32 guard requires program_version={PROGRAM_VERSION}; got {config.get('program_version')!r}"
        )
    human_output_root = config.get("human_output_root")
    r30.configure_excluded_roots([str(human_output_root)] if human_output_root else [])
    return config


def r32_render_human_digest(
    run_id: str,
    findings: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    falsifications: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]],
    stop_reasons: Sequence[str],
) -> str:
    text = r31.r31_render_human_digest(
        run_id,
        findings,
        candidates,
        falsifications,
        decisions,
        stop_reasons,
    )
    old = "# Human Decision Digest — HANRI R31"
    new = f"# Human Decision Digest — {HUMAN_LABEL}"
    if old not in text:
        raise core.HanriError("R32 identity guard: expected R31 digest marker is missing")
    return text.replace(old, new, 1)


def r32_snapshot_event(path: Path, label: str) -> dict[str, Any]:
    event = r31.r31_snapshot_event(path, label)
    event["actor"] = ACTOR
    return event


def r32_archive_frontier_event(pair: Mapping[str, Any]) -> dict[str, Any]:
    event = r31.r31_archive_frontier_event(pair)
    event["actor"] = ACTOR
    return event


def r32_causal_spine_event(spine: Mapping[str, Any]) -> dict[str, Any]:
    event = r31.r31_causal_spine_event(spine)
    event["actor"] = ACTOR
    return event


def _archive_scan_checkpoint(source_root: Path) -> dict[str, Any] | None:
    causal = source_root / "latest_archive_causal_spine.json"
    frontier = source_root / "latest_archive_frontier.json"
    path = causal if causal.exists() else frontier if frontier.exists() else None
    if path is None:
        return None
    try:
        value = core.load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return {
        "source": path.name,
        "generated_at": value.get("generated_at"),
        "scan_interval_seconds": value.get("scan_interval_seconds"),
        "scope_id": value.get("scope_id"),
        "origin_files_seen": value.get("origin_files_seen"),
        "pivot_files_seen": value.get("pivot_files_seen"),
        "current_files_seen": value.get("current_files_seen"),
    }


def _material_policy() -> dict[str, Any]:
    return {
        "version": r31.MATERIAL_POLICY_VERSION,
        "inherited_recursive_volatile_keys": sorted(r30._VOLATILE_MATERIAL_KEYS),
        "latest_ai_state_ignored_top_level_keys": sorted(r31._AI_STATE_EPHEMERAL_TOP_LEVEL),
        "nested_new_events_remains_material": True,
        "new_findings_remains_material": True,
        "new_candidates_remains_material": True,
        "new_decisions_remains_material": True,
        "stop_reasons_remains_material": True,
        "current_run_envelope_always_projected": True,
        "heartbeat_fast_path_policy": STEADY_POLICY_VERSION,
        "fast_path_requires_no_new_inputs": True,
        "fast_path_requires_no_current_state_drift": True,
        "fast_path_requires_archive_scan_not_due": True,
        "fast_path_reuses_material_state_bytes": True,
    }


def copy_latest_outputs_r32(source_root: Path, target_root: Path) -> dict[str, Any]:
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
        source_digest = r31.material_digest_r31(source)
        material_digests[name] = source_digest
        if destination.exists() and r31.material_digest_r31(destination) == source_digest:
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
        "ai_state_run_envelope": r31._ai_state_run_envelope(source_root),
        "archive_scan_checkpoint": _archive_scan_checkpoint(source_root),
        "material_policy": _material_policy(),
        "heartbeat_fast_path": False,
        "material_state_reused": False,
        "self_projection_excluded_from_archive": True,
        "external_model_api_calls": 0,
        "self_application": False,
        "can_trade": False,
    }
    local_receipt = source_root / "latest_projection_receipt.json"
    core.atomic_write_json(local_receipt, receipt)
    r30._atomic_copy(local_receipt, target_root / "latest_projection_receipt.json")
    return receipt


def _replace_digest_run_id(text: str, run_id: str) -> str:
    lines = text.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith("Run: `") and line.endswith("`"):
            lines[index] = f"Run: `{run_id}`"
            replaced = True
            break
    if not replaced:
        raise core.HanriError("R32 fast path requires a prior human digest Run line")
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + suffix


def _unprocessed_json_exists(directory: Path, processed: set[str]) -> bool:
    if not directory.exists():
        return False
    for path in sorted(directory.glob("*.json")):
        if core.sha256_file(path) not in processed:
            return True
    return False


def _fast_path_context(config_path: Path, config: Mapping[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    state_root = core.expand_path(str(config["state_root"]))
    event_inbox = core.expand_path(str(config["event_inbox"]))
    decision_inbox = core.expand_path(str(config["decision_inbox"]))

    ai_state_path = state_root / "latest_ai_state.json"
    run_receipt_path = state_root / "latest_run_receipt.json"
    projection_receipt_path = state_root / "latest_projection_receipt.json"
    digest_path = state_root / "latest_human_digest.md"
    regression_path = state_root / "latest_regression_suite.json"
    processed_events_path = state_root / "processed_event_hashes.json"
    processed_decisions_path = state_root / "processed_decision_hashes.json"

    required = [
        ai_state_path,
        run_receipt_path,
        projection_receipt_path,
        digest_path,
        regression_path,
        processed_events_path,
        processed_decisions_path,
    ]
    if any(not path.exists() for path in required):
        return False, "MISSING_FAST_PATH_PREREQUISITE", {}

    try:
        previous_run = core.load_json(run_receipt_path)
        previous_projection = core.load_json(projection_receipt_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False, "INVALID_PREVIOUS_RECEIPT", {}

    if previous_run.get("program_version") != PROGRAM_VERSION:
        return False, "PREVIOUS_RUN_NOT_R32", {}
    if previous_projection.get("program_version") != PROGRAM_VERSION:
        return False, "PREVIOUS_PROJECTION_NOT_R32", {}
    if previous_run.get("config_sha256") != core.sha256_file(config_path):
        return False, "CONFIG_CHANGED", {}

    envelope = previous_projection.get("ai_state_run_envelope")
    material_digests = previous_projection.get("material_digests")
    checkpoint = previous_projection.get("archive_scan_checkpoint")
    if not isinstance(envelope, dict) or not isinstance(material_digests, dict):
        return False, "MISSING_MATERIAL_ENVELOPE", {}
    if envelope.get("source_sha256") != previous_run.get("state_sha256"):
        return False, "STATE_SHA_RECEIPT_MISMATCH", {}
    if envelope.get("material_digest") != material_digests.get("latest_ai_state.json"):
        return False, "STATE_MATERIAL_DIGEST_MISMATCH", {}
    if envelope.get("shadow_only") is not True:
        return False, "SHADOW_ONLY_INVARIANT_MISSING", {}
    if envelope.get("self_application") is not False:
        return False, "SELF_APPLICATION_INVARIANT_FAILED", {}
    if int(envelope.get("external_model_api_calls", -1)) != 0:
        return False, "EXTERNAL_API_INVARIANT_FAILED", {}
    if envelope.get("source_repository_writes") is not False:
        return False, "REPOSITORY_WRITE_INVARIANT_FAILED", {}
    if envelope.get("can_trade") is not False:
        return False, "CAN_TRADE_INVARIANT_FAILED", {}
    if int(envelope.get("new_findings", 0)) != 0 or int(envelope.get("new_candidates", 0)) != 0 or int(envelope.get("new_decisions", 0)) != 0:
        return False, "PRIOR_RUN_HAS_NEW_DECISION_SURFACE", {}
    if list(envelope.get("stop_reasons", [])):
        return False, "PRIOR_RUN_HAS_STOP_REASON", {}

    digest_text = digest_path.read_text(encoding="utf-8-sig")
    first_line = digest_text.splitlines()[0] if digest_text.splitlines() else ""
    if HUMAN_LABEL not in first_line or "HANRI R31" in first_line:
        return False, "HUMAN_DIGEST_IDENTITY_MISMATCH", {}
    if not any(line.startswith("Run: `") for line in digest_text.splitlines()):
        return False, "HUMAN_DIGEST_RUN_ID_MISSING", {}

    processed_events = core.load_hash_set(processed_events_path)
    processed_decisions = core.load_hash_set(processed_decisions_path)
    if _unprocessed_json_exists(event_inbox, processed_events):
        return False, "NEW_EVENT_INPUT", {}
    if _unprocessed_json_exists(decision_inbox, processed_decisions):
        return False, "NEW_DECISION_INPUT", {}

    r23_path_value = config.get("r23_state_path")
    if r23_path_value:
        r23_path = core.expand_path(str(r23_path_value))
        if r23_path.exists() and "R23:" + core.sha256_file(r23_path) not in processed_events:
            return False, "R23_STATE_CHANGED", {}

    for value in config.get("current_state_paths", []):
        path = core.expand_path(str(value))
        if not path.exists() or not path.is_file():
            continue
        if "STATE:" + core.sha256_file(path) not in processed_events:
            return False, "CURRENT_STATE_CHANGED", {}

    frontier_config = config.get("archive_frontier", {})
    if frontier_config.get("enabled") is True:
        if not isinstance(checkpoint, dict) or not checkpoint.get("generated_at"):
            return False, "ARCHIVE_CHECKPOINT_MISSING", {}
        scan_interval = max(int(frontier_config.get("scan_interval_seconds", 900)), 60)
        try:
            age = (core.utc_now() - core.parse_iso(str(checkpoint["generated_at"]))).total_seconds()
        except (TypeError, ValueError):
            return False, "ARCHIVE_CHECKPOINT_INVALID", {}
        if age >= scan_interval:
            return False, "ARCHIVE_SCAN_DUE", {}

    heavy_paths = [state_root / name for name in r30._HEAVY_SNAPSHOTS if (state_root / name).exists()]
    if ai_state_path not in heavy_paths:
        return False, "AI_STATE_MISSING", {}

    return True, FAST_PATH_REASON, {
        "state_root": state_root,
        "event_inbox": event_inbox,
        "decision_inbox": decision_inbox,
        "ai_state_path": ai_state_path,
        "run_receipt_path": run_receipt_path,
        "projection_receipt_path": projection_receipt_path,
        "digest_path": digest_path,
        "regression_path": regression_path,
        "previous_run": previous_run,
        "previous_projection": previous_projection,
        "previous_envelope": envelope,
        "material_digests": dict(material_digests),
        "archive_scan_checkpoint": dict(checkpoint) if isinstance(checkpoint, dict) else None,
        "digest_text": digest_text,
        "heavy_paths": heavy_paths,
    }


def _write_health_fast_path(path: Path, envelope: Mapping[str, Any]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerow(["new_events", 0])
        writer.writerow(["new_findings", 0])
        writer.writerow(["total_findings", int(envelope.get("total_findings", 0))])
        writer.writerow(["total_candidates", int(envelope.get("total_candidates", 0))])
        writer.writerow(["pending_human_decisions", int(envelope.get("pending_human_decisions", 0))])
        writer.writerow(["stop_reasons", ""])
        writer.writerow(["heartbeat_fast_path", "true"])
        writer.writerow(["can_trade", "false"])


def _project_fast_path(
    state_root: Path,
    target_root: Path,
    projection: Mapping[str, Any],
) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for name in r30._ALWAYS_PROJECT:
        source = state_root / name
        if source.exists():
            r30._atomic_copy(source, target_root / name)
    local_projection = state_root / "latest_projection_receipt.json"
    core.atomic_write_json(local_projection, projection)
    r30._atomic_copy(local_projection, target_root / "latest_projection_receipt.json")


def _run_fast_path(config_path: Path, config: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    state_root = Path(context["state_root"])
    human_output_root = core.expand_path(str(config["human_output_root"])) if config.get("human_output_root") else None
    previous_run = dict(context["previous_run"])
    previous_envelope = dict(context["previous_envelope"])
    material_digests = dict(context["material_digests"])
    heavy_paths = list(context["heavy_paths"])

    run_id = core.utc_now().strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    generated_at = core.iso_utc()
    digest_text = _replace_digest_run_id(str(context["digest_text"]), run_id)
    core.atomic_write_text(state_root / "latest_human_digest.md", digest_text)
    _write_health_fast_path(state_root / "latest_health.csv", previous_envelope)

    state_sha = str(previous_run["state_sha256"])
    material_state_run_id = previous_envelope.get("material_state_run_id") or previous_envelope.get("run_id")
    receipt = {
        "schema_version": 1,
        "program_version": PROGRAM_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "config_path": str(config_path),
        "config_sha256": core.sha256_file(config_path),
        "events_processed": 0,
        "decisions_processed": 0,
        "findings_generated": 0,
        "candidates_generated": 0,
        "stop_reasons": [],
        "state_sha256": state_sha,
        "human_digest_sha256": core.sha256_file(state_root / "latest_human_digest.md"),
        "heartbeat_fast_path": True,
        "fast_path_reason": FAST_PATH_REASON,
        "material_state_reused": True,
        "material_state_run_id": material_state_run_id,
        "external_model_api_calls": 0,
        "self_application": False,
        "can_trade": False,
    }
    core.atomic_write_json(state_root / "latest_run_receipt.json", receipt)
    core.atomic_write_json(state_root / f"run_{run_id}.json", receipt)

    current_envelope = dict(previous_envelope)
    current_envelope.update({
        "run_id": run_id,
        "generated_at": generated_at,
        "new_events": 0,
        "new_findings": 0,
        "new_candidates": 0,
        "new_decisions": 0,
        "stop_reasons": [],
        "source_sha256": state_sha,
        "material_digest": material_digests.get("latest_ai_state.json"),
        "heartbeat_fast_path": True,
        "material_state_run_id": material_state_run_id,
    })

    drive_bytes_avoided = sum(path.stat().st_size for path in heavy_paths)
    ai_state_rewrite_bytes_avoided = Path(context["ai_state_path"]).stat().st_size
    projection = {
        "schema_version": 1,
        "program_version": PROGRAM_VERSION,
        "generated_at": core.iso_utc(),
        "projection_target": str(human_output_root) if human_output_root else None,
        "copied": sorted(name for name in r30._ALWAYS_PROJECT if (state_root / name).exists()),
        "skipped_no_material_delta": sorted(path.name for path in heavy_paths),
        "bytes_avoided": drive_bytes_avoided,
        "ai_state_rewrite_bytes_avoided": ai_state_rewrite_bytes_avoided,
        "heavy_snapshot_bytes_reused": drive_bytes_avoided,
        "heavy_snapshot_files_not_read": sorted(path.name for path in heavy_paths),
        "material_digests": material_digests,
        "ai_state_run_envelope": current_envelope,
        "archive_scan_checkpoint": context.get("archive_scan_checkpoint"),
        "material_policy": _material_policy(),
        "heartbeat_fast_path": True,
        "fast_path_reason": FAST_PATH_REASON,
        "material_state_reused": True,
        "material_state_run_id": material_state_run_id,
        "self_projection_excluded_from_archive": True,
        "external_model_api_calls": 0,
        "self_application": False,
        "can_trade": False,
    }
    if human_output_root:
        _project_fast_path(state_root, human_output_root, projection)
    else:
        core.atomic_write_json(state_root / "latest_projection_receipt.json", projection)

    receipt["fast_path_elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    core.atomic_write_json(state_root / "latest_run_receipt.json", receipt)
    core.atomic_write_json(state_root / f"run_{run_id}.json", receipt)
    if human_output_root:
        r30._atomic_copy(state_root / "latest_run_receipt.json", human_output_root / "latest_run_receipt.json")
    return receipt


def r32_process_once(config_path: Path) -> dict[str, Any]:
    config = r32_load_config(config_path)
    eligible, _, context = _fast_path_context(config_path, config)
    if not eligible:
        return _RAW_PROCESS_ONCE(config_path)

    state_root = core.expand_path(str(config["state_root"]))
    lock_file = core.expand_path(str(config.get("lock_file", state_root / "hanri.lock")))
    fallback = False
    with core.FileLock(lock_file, int(config.get("lock_stale_seconds", 1800))):
        eligible, _, context = _fast_path_context(config_path, config)
        if eligible:
            return _run_fast_path(config_path, config, context)
        fallback = True
    if fallback:
        return _RAW_PROCESS_ONCE(config_path)
    raise core.HanriError("R32 unreachable fast-path state")


def r32_status(config_path: Path) -> dict[str, Any]:
    config = r32_load_config(config_path)
    state_root = core.expand_path(str(config["state_root"]))
    run_path = state_root / "latest_run_receipt.json"
    projection_path = state_root / "latest_projection_receipt.json"
    ai_path = state_root / "latest_ai_state.json"
    if not run_path.exists() or not ai_path.exists():
        return _RAW_STATUS(config_path)
    try:
        run = core.load_json(run_path)
        projection = core.load_json(projection_path) if projection_path.exists() else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return _RAW_STATUS(config_path)
    envelope = projection.get("ai_state_run_envelope", {}) if isinstance(projection, dict) else {}
    return {
        "status": "OK",
        "run_id": run.get("run_id"),
        "material_state_run_id": run.get("material_state_run_id") or envelope.get("material_state_run_id") or envelope.get("run_id"),
        "pending_human_decisions": envelope.get("pending_human_decisions"),
        "stop_reasons": run.get("stop_reasons", []),
        "heartbeat_fast_path": bool(run.get("heartbeat_fast_path", False)),
        "state_path": str(ai_path),
        "state_sha256": run.get("state_sha256"),
        "can_trade": False,
    }


def install_r32_guard() -> None:
    r31.install_r31_guard()
    core.VERSION = PROGRAM_VERSION
    core.load_config = r32_load_config
    core.render_human_digest = r32_render_human_digest
    core.snapshot_event = r32_snapshot_event
    core.archive_frontier_event = r32_archive_frontier_event
    core.causal_spine_event = r32_causal_spine_event
    archive_mod.archive_frontier_event = r32_archive_frontier_event
    archive_mod.causal_spine_event = r32_causal_spine_event
    core.copy_latest_outputs = copy_latest_outputs_r32
    core.process_once = r32_process_once
    core.status = r32_status


def main(argv: Sequence[str] | None = None) -> int:
    install_r32_guard()
    return core.main(argv)
