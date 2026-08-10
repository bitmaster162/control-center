from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from . import archive as archive_mod
from . import archive_scandir
from . import cli as core
from . import delta_cli as r30
from . import steady_cli as r32
from . import steady_integrity_cli as integrity

PROGRAM_VERSION = "33.0.0"
ACTOR = "HANRI_R33"
HUMAN_LABEL = "HANRI R33"
SCAN_POLICY_VERSION = archive_scandir.SCAN_POLICY_VERSION
SCAN_ENGINE = archive_scandir.SCAN_ENGINE
PROJECTION_REPLACE_POLICY_VERSION = "33.0.0-drive-atomic-replace-retry-v1"
PROJECTION_REPLACE_DELAYS_SECONDS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0)

_BASE_MATERIAL_POLICY = r32._material_policy
_BASE_INTEGRITY_COPY = integrity.copy_latest_outputs_r32_integrity


def _material_policy_r33() -> dict[str, object]:
    policy = dict(_BASE_MATERIAL_POLICY())
    policy["archive_scan_policy_version"] = SCAN_POLICY_VERSION
    policy["archive_scan_engine"] = SCAN_ENGINE
    policy["archive_scan_cache_hit_record_reuse"] = True
    policy["archive_scan_single_stat_metadata_path"] = True
    policy["archive_scan_scope_semantics_inherited"] = True
    policy["projection_atomic_replace_policy"] = PROJECTION_REPLACE_POLICY_VERSION
    policy["projection_atomic_replace_retry_bounded"] = True
    policy["projection_atomic_replace_direct_overwrite"] = False
    return policy


def _retryable_projection_replace_error(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32}


def _atomic_copy_r33(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".tmp-{uuid.uuid4().hex}")
    shutil.copyfile(source, temporary)
    try:
        for attempt in range(len(PROJECTION_REPLACE_DELAYS_SECONDS) + 1):
            try:
                os.replace(temporary, destination)
                return
            except OSError as exc:
                if not _retryable_projection_replace_error(exc) or attempt >= len(PROJECTION_REPLACE_DELAYS_SECONDS):
                    raise
                time.sleep(PROJECTION_REPLACE_DELAYS_SECONDS[attempt])
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


def copy_latest_outputs_r33(source_root: Path, target_root: Path) -> dict[str, Any]:
    receipt = _BASE_INTEGRITY_COPY(source_root, target_root)
    metrics = archive_scandir.get_last_scan_metrics()
    if metrics:
        receipt["archive_scan_runtime_metrics"] = metrics
    local = source_root / "latest_projection_receipt.json"
    core.atomic_write_json(local, receipt)
    r30._atomic_copy(local, target_root / "latest_projection_receipt.json")
    return receipt


def install_r33_guard() -> None:
    # The R32 functions resolve these globals dynamically; updating them before
    # installation preserves the accepted R32 safety/heartbeat logic while
    # giving the side-by-side candidate an isolated R33 identity/version.
    r32.PROGRAM_VERSION = PROGRAM_VERSION
    r32.ACTOR = ACTOR
    r32.HUMAN_LABEL = HUMAN_LABEL
    integrity.PROGRAM_VERSION = PROGRAM_VERSION
    integrity.ACTOR = ACTOR
    integrity.HUMAN_LABEL = HUMAN_LABEL
    integrity.INTEGRITY_POLICY_VERSION = "33.0.0-steady-integrity-inherited-v1"
    r32._material_policy = _material_policy_r33

    integrity.install_r32_integrity_guard()
    core.VERSION = PROGRAM_VERSION

    # R33 alone gets bounded retries for transient Google Drive/Windows locks.
    # Atomic temp-file replacement remains mandatory; persistent locks fail closed.
    r30._atomic_copy = _atomic_copy_r33

    # Core imported the legacy functions directly, so patch both bindings.
    archive_mod.scan_frontier_pair = archive_scandir.scan_frontier_pair_scandir
    archive_mod.scan_causal_spine = archive_scandir.scan_causal_spine_scandir
    core.scan_frontier_pair = archive_scandir.scan_frontier_pair_scandir
    core.scan_causal_spine = archive_scandir.scan_causal_spine_scandir
    core.copy_latest_outputs = copy_latest_outputs_r33


def main(argv: Sequence[str] | None = None) -> int:
    install_r33_guard()
    return core.main(argv)
