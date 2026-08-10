from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from . import cli as core
from .r34_profile_instrument import NON_OVERLAP_KEYS, run_profiled_process
from .r34_profile_support import (
    EXPECTED_PROGRAM_VERSION,
    FORCE_FULL_REMOVE,
    TimingBook,
    clone_live_state,
    isolated_config,
    state_metadata_snapshot,
    validate_source_config,
)

PROBE_VERSION = "34.0.0-probe-v1"
PROBE_MODE = "ISOLATED_ACCEPTED_R33_FULL_CYCLE_REPLAY"

_validate_source_config = validate_source_config
_state_metadata_snapshot = state_metadata_snapshot
_clone_live_state = clone_live_state
_isolated_config = isolated_config


def _percent(value: float, total: float) -> float:
    return round((value / total * 100.0), 3) if total > 0 else 0.0


def profile_full_cycle(config_path: Path) -> dict[str, Any]:
    raw = core.load_json(config_path)
    validate_source_config(raw)
    live_state_root = core.expand_path(str(raw["state_root"])).resolve()
    live_projection_root = core.expand_path(str(raw["human_output_root"])).resolve()
    live_before = state_metadata_snapshot(live_state_root)
    live_scope_path = live_state_root / "latest_archive_scope_certificate.json"
    live_scope_before = core.load_json(live_scope_path) if live_scope_path.exists() else {}

    setup_started = time.perf_counter()
    sandbox_path = ""
    with tempfile.TemporaryDirectory(prefix="hanri-r34-profile-") as temp_dir:
        sandbox_root = Path(temp_dir).resolve()
        sandbox_path = str(sandbox_root)
        sandbox_state_root = sandbox_root / "state"
        sandbox_projection_root = sandbox_root / "projection"
        sandbox_state_root.mkdir(parents=True, exist_ok=True)
        sandbox_projection_root.mkdir(parents=True, exist_ok=True)
        clone_live_state(live_state_root, sandbox_state_root)
        isolated = isolated_config(raw, sandbox_state_root, sandbox_projection_root)
        isolated_config_path = sandbox_root / "r33.profile.json"
        isolated_config_path.write_text(json.dumps(isolated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        setup_elapsed_ms = round((time.perf_counter() - setup_started) * 1000.0, 3)

        receipt, book, process_elapsed_ms = run_profiled_process(isolated_config_path, live_projection_root, sandbox_projection_root)
        scope_path = sandbox_state_root / "latest_archive_scope_certificate.json"
        projection_path = sandbox_state_root / "latest_projection_receipt.json"
        scope = core.load_json(scope_path) if scope_path.exists() else {}
        projection = core.load_json(projection_path) if projection_path.exists() else {}
        scan_metrics = projection.get("archive_scan_runtime_metrics", {})

        live_after = state_metadata_snapshot(live_state_root)
        live_state_unchanged = live_before == live_after
        stage_values = book.rounded()
        headline = {key: float(stage_values.get(key, 0.0)) for key in NON_OVERLAP_KEYS}
        attributed_ms = sum(headline.values())
        residual_ms = max(process_elapsed_ms - attributed_ms, 0.0)
        headline["residual_unattributed"] = round(residual_ms, 3)
        stage_percent = {key: _percent(value, process_elapsed_ms) for key, value in headline.items()}
        largest_stage = max(headline, key=headline.get) if headline else None

        live_denominator = int(live_scope_before.get("denominator", 0) or 0)
        sandbox_denominator = int(scope.get("denominator", 0) or 0)
        scope_manifest_equal = bool(live_scope_before.get("scope_manifest_sha256") and scope.get("scope_manifest_sha256") and live_scope_before.get("scope_manifest_sha256") == scope.get("scope_manifest_sha256"))
        self_rows = [row for row in scope.get("files", []) if "HANRI_R33" in str(row.get("path", ""))]

        failures: list[str] = []
        if not live_state_unchanged:
            failures.append("LIVE_R33_STATE_CHANGED_DURING_PROBE")
        if scope.get("status") != "COMPLETE" or float(scope.get("coverage_percent", 0.0)) != 100.0:
            failures.append("SANDBOX_SCOPE_NOT_COMPLETE")
        if int(receipt.get("external_model_api_calls", -1)) != 0:
            failures.append("EXTERNAL_API_INVARIANT_FAILED")
        if receipt.get("self_application") is not False or receipt.get("can_trade") is not False:
            failures.append("AUTHORITY_INVARIANT_FAILED")
        if self_rows:
            failures.append("LIVE_R33_SELF_PROJECTION_NOT_EXCLUDED")

        result = {
            "schema_version": 1,
            "probe_version": PROBE_VERSION,
            "probe_mode": PROBE_MODE,
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "accepted_runtime_version": EXPECTED_PROGRAM_VERSION,
            "source_config_path": str(config_path),
            "live_state_root": str(live_state_root),
            "live_projection_root": str(live_projection_root),
            "sandbox_writes_only": True,
            "setup_clone_elapsed_ms": setup_elapsed_ms,
            "profiled_process_elapsed_ms": process_elapsed_ms,
            "headline_nonoverlap_ms": headline,
            "headline_percent_of_process": stage_percent,
            "largest_headline_stage": largest_stage,
            "stage_timings_ms": stage_values,
            "stage_call_counts": book.call_counts(),
            "attributed_nonoverlap_ms": round(attributed_ms, 3),
            "residual_unattributed_ms": round(residual_ms, 3),
            "archive_scan_runtime_metrics": scan_metrics,
            "scope": {
                "status": scope.get("status"),
                "coverage_percent": scope.get("coverage_percent"),
                "coverage_ratio": scope.get("coverage_ratio"),
                "denominator": sandbox_denominator,
                "live_denominator_before": live_denominator,
                "manifest_equal_to_live_before": scope_manifest_equal,
                "live_r33_self_projection_excluded": not self_rows,
            },
            "result": {
                "run_id": receipt.get("run_id"),
                "events_processed": receipt.get("events_processed"),
                "findings_generated": receipt.get("findings_generated"),
                "candidates_generated": receipt.get("candidates_generated"),
                "decisions_processed": receipt.get("decisions_processed"),
            },
            "safety": {
                "live_r33_state_unchanged_during_probe": live_state_unchanged,
                "drive_hanri_r33_writes": 0,
                "scheduler_changes": 0,
                "source_repository_writes": False,
                "external_model_api_calls": int(receipt.get("external_model_api_calls", 0)),
                "self_application": bool(receipt.get("self_application", False)),
                "can_trade": bool(receipt.get("can_trade", False)),
                "capital_permission": "DENY",
            },
        }
    result["sandbox_cleaned_after_probe"] = not Path(sandbox_path).exists()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R34 isolated full-cycle profiler for accepted HANRI R33")
    parser.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = profile_full_cycle(args.config)
    except (OSError, ValueError, json.JSONDecodeError, core.HanriError) as exc:
        print(json.dumps({"status": "ERROR", "probe_version": PROBE_VERSION, "error": type(exc).__name__, "message": str(exc), "can_trade": False}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
