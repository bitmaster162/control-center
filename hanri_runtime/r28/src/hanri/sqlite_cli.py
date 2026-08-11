from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from . import archive as archive_mod
from . import archive_scandir
from . import archive_sqlite
from . import cli as core
from . import delta_cli as r30
from . import scandir_cli as r33
from . import steady_cli as r32
from . import steady_integrity_cli as integrity

PROGRAM_VERSION = "35.0.0"
ACTOR = "HANRI_R35"
HUMAN_LABEL = "HANRI R35"
SCAN_POLICY_VERSION = archive_scandir.SCAN_POLICY_VERSION
SCAN_ENGINE = archive_scandir.SCAN_ENGINE
INVENTORY_POLICY_VERSION = archive_sqlite.STORAGE_POLICY_VERSION
INVENTORY_ENGINE = archive_sqlite.STORAGE_ENGINE
PROJECTION_REPLACE_POLICY_VERSION = r33.PROJECTION_REPLACE_POLICY_VERSION
INTEGRITY_POLICY_VERSION = "35.0.0+r36-heartbeat-integrity-fast-gate-v1"

_RAW_LOAD_JSON = core.load_json
_RAW_ATOMIC_WRITE_JSON = core.atomic_write_json
_BASE_MATERIAL_POLICY = r33._BASE_MATERIAL_POLICY
_BASE_INTEGRITY_COPY = r33._BASE_INTEGRITY_COPY


def _material_policy_r35() -> dict[str, object]:
    policy = dict(_BASE_MATERIAL_POLICY())
    policy["archive_scan_policy_version"] = SCAN_POLICY_VERSION
    policy["archive_scan_engine"] = SCAN_ENGINE
    policy["archive_scan_cache_hit_record_reuse"] = True
    policy["archive_scan_single_stat_metadata_path"] = True
    policy["archive_scan_scope_semantics_inherited"] = True
    policy["archive_inventory_backend"] = "SQLITE"
    policy["archive_inventory_policy_version"] = INVENTORY_POLICY_VERSION
    policy["archive_inventory_engine"] = INVENTORY_ENGINE
    policy["archive_inventory_bulk_index_snapshot"] = True
    policy["archive_inventory_changed_row_upsert_only"] = True
    policy["archive_inventory_seed_json_preserved"] = True
    policy["archive_inventory_monolithic_json_rewrite"] = False
    policy["archive_inventory_direct_json_fallback"] = False
    policy["archive_inventory_migration_requires_logical_sha_parity"] = True
    policy["archive_inventory_sqlite_quick_check_required"] = True
    policy["projection_atomic_replace_policy"] = PROJECTION_REPLACE_POLICY_VERSION
    policy["projection_atomic_replace_retry_bounded"] = True
    policy["projection_atomic_replace_direct_overwrite"] = False
    return policy


def _load_json_r35(path: Path) -> Any:
    candidate = Path(path)
    if candidate.name == archive_sqlite.CACHE_JSON_NAME:
        return archive_sqlite.prepare_inventory_handle(candidate, _RAW_LOAD_JSON)
    return _RAW_LOAD_JSON(candidate)


def _atomic_write_json_r35(path: Path, value: Any) -> None:
    candidate = Path(path)
    if candidate.name == archive_sqlite.CACHE_JSON_NAME:
        archive_sqlite.finalize_inventory_write(candidate, value)
        return
    _RAW_ATOMIC_WRITE_JSON(candidate, value)


def copy_latest_outputs_r35(source_root: Path, target_root: Path) -> dict[str, Any]:
    receipt = _BASE_INTEGRITY_COPY(source_root, target_root)
    metrics = archive_sqlite.get_last_scan_metrics()
    if metrics:
        receipt["archive_scan_runtime_metrics"] = metrics
    local = source_root / "latest_projection_receipt.json"
    core.atomic_write_json(local, receipt)
    r30._atomic_copy(local, target_root / "latest_projection_receipt.json")
    return receipt


def install_r35_guard() -> None:
    r32.PROGRAM_VERSION = PROGRAM_VERSION
    r32.ACTOR = ACTOR
    r32.HUMAN_LABEL = HUMAN_LABEL
    integrity.PROGRAM_VERSION = PROGRAM_VERSION
    integrity.ACTOR = ACTOR
    integrity.HUMAN_LABEL = HUMAN_LABEL
    integrity.INTEGRITY_POLICY_VERSION = INTEGRITY_POLICY_VERSION
    r32._material_policy = _material_policy_r35

    integrity.install_r32_integrity_guard()
    core.VERSION = PROGRAM_VERSION

    # Preserve the accepted R33 bounded atomic Drive projection retry exactly.
    r30._atomic_copy = r33._atomic_copy_r33

    # Replace only the inventory persistence/classification layer. The registered
    # roots, scandir traversal, scope/collision semantics and archive event layer
    # remain inherited from accepted R33/R28 code.
    core.load_json = _load_json_r35
    core.atomic_write_json = _atomic_write_json_r35
    archive_mod.scan_frontier_pair = archive_sqlite.scan_frontier_pair_sqlite
    archive_mod.scan_causal_spine = archive_sqlite.scan_causal_spine_sqlite
    core.scan_frontier_pair = archive_sqlite.scan_frontier_pair_sqlite
    core.scan_causal_spine = archive_sqlite.scan_causal_spine_sqlite
    core.copy_latest_outputs = copy_latest_outputs_r35


def main(argv: Sequence[str] | None = None) -> int:
    install_r35_guard()
    return core.main(argv)
