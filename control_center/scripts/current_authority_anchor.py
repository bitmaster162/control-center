from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data"
DEFAULT_PROVIDER_SNAPSHOT = DATA / "provider_snapshot.current.v1.json"
PROVIDER_SCHEMA = "control_center.provider_snapshot.v1"
PROVIDER_KIND = "NON_AUTHORITY_PROVIDER_READBACK"

_REQUIRED_ROOT_KEYS = (
    "generation",
    "status",
    "decision",
    "pointer_drive_file_id",
    "pointer_sha256",
    "manifest_sha256",
    "current_state_drive_file_id",
    "current_state_sha256",
    "role_index_drive_file_id",
    "role_index_sha256",
    "role_views_drive_file_id",
    "role_views_sha256",
    "provider_readback",
)
_SHA_KEYS = (
    "pointer_sha256",
    "manifest_sha256",
    "current_state_sha256",
    "role_index_sha256",
    "role_views_sha256",
)


def load_provider_snapshot(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_PROVIDER_SNAPSHOT
    return json.loads(target.read_text(encoding="utf-8"))


def canonical_roots(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    source = snapshot or load_provider_snapshot()
    errors: list[str] = []
    if source.get("schema") != PROVIDER_SCHEMA:
        errors.append("provider_snapshot_schema_mismatch")
    if source.get("snapshot_kind") != PROVIDER_KIND:
        errors.append("provider_snapshot_kind_mismatch")
    roots = source.get("canonical_roots", {})
    for key in _REQUIRED_ROOT_KEYS:
        if key not in roots or roots.get(key) in (None, ""):
            errors.append(f"canonical_root_missing:{key}")
    for key in _SHA_KEYS:
        if key in roots and not re.fullmatch(r"[0-9a-f]{64}", str(roots.get(key, ""))):
            errors.append(f"canonical_root_sha_invalid:{key}")
    if roots.get("status") != "ACTIVE":
        errors.append("canonical_root_status_not_active")
    if roots.get("provider_readback") != "all_exact":
        errors.append("canonical_root_provider_readback_not_exact")
    if roots.get("r63_is_current") is not False:
        errors.append("canonical_root_r63_current_flag_invalid")
    if errors:
        raise ValueError(";".join(errors))
    return dict(roots)


def canonical_authority_anchor(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    roots = canonical_roots(snapshot)
    return {
        "generation": roots["generation"],
        "status": roots["status"],
        "decision": roots["decision"],
        "pointer_drive_file_id": roots["pointer_drive_file_id"],
        "pointer_sha256": roots["pointer_sha256"],
        "provider_readback": roots["provider_readback"],
    }


def append_anchor_errors(
    name: str,
    anchor: dict[str, Any],
    errors: list[str],
    snapshot: dict[str, Any] | None = None,
) -> None:
    expected = canonical_authority_anchor(snapshot)
    for key, value in expected.items():
        if anchor.get(key) != value:
            errors.append(f"{name}_anchor_mismatch:{key}")


def append_root_hash_errors(
    name: str,
    observed: dict[str, Any],
    mapping: dict[str, str],
    errors: list[str],
    snapshot: dict[str, Any] | None = None,
) -> None:
    roots = canonical_roots(snapshot)
    for observed_key, canonical_key in mapping.items():
        if observed.get(observed_key) != roots.get(canonical_key):
            errors.append(f"{name}_root_mismatch:{observed_key}")
