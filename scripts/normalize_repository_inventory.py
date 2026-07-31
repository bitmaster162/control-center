#!/usr/bin/env python3
"""Normalize Antigravity census/export JSON into a deterministic repository inventory.

Read-only. It never runs Git, creates repositories or changes source files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _full_sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if len(value) == 40 and all(c in "0123456789abcdef" for c in value) else None


def normalize(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, value in sorted(payload.get("git_repositories", {}).items()):
        local_head = _full_sha(value.get("local_head"))
        remote_head = _full_sha(value.get("remote_head"))
        exact_sync = (
            local_head is not None
            and remote_head is not None
            and local_head == remote_head
            and value.get("ahead") == 0
            and value.get("behind") == 0
        )
        visibility = str(value.get("visibility") or "UNKNOWN").upper()
        if visibility not in {"PRIVATE", "PUBLIC", "LOCAL_ONLY", "UNKNOWN"}:
            visibility = "UNKNOWN"
        rows.append({
            "id": key,
            "name": value.get("project_name", key),
            "category": "CANONICAL_GIT" if value.get("upstream") else "PRIVATE_GIT",
            "status": "REMOTE_SYNCED" if exact_sync else "RECONCILE_REQUIRED",
            "code_root": value.get("path"),
            "remote_url": value.get("remote_url"),
            "visibility": visibility,
            "branch": value.get("branch"),
            "local_head": local_head,
            "remote_head": remote_head,
            "local_head_prefix": value.get("local_head") if isinstance(value.get("local_head"), str) and local_head is None else None,
            "remote_head_prefix": value.get("remote_head") if isinstance(value.get("remote_head"), str) and remote_head is None else None,
            "ahead": value.get("ahead") if isinstance(value.get("ahead"), int) else None,
            "behind": value.get("behind") if isinstance(value.get("behind"), int) else None,
            "next": value.get("next", "Controller reconciliation required."),
            "evidence_state": "SOURCE_BACKED",
            "evidence_refs": ["repo-census-r2"],
            "freshness": "CURRENT",
        })
    for key, value in sorted(payload.get("non_git_sources", {}).items()):
        rows.append({
            "id": key,
            "name": value.get("project_name", key),
            "category": "NON_GIT_SOURCE",
            "status": "BOUNDARY_AUDIT_REQUIRED",
            "code_root": value.get("path"),
            "remote_url": None,
            "visibility": "LOCAL_ONLY",
            "branch": None,
            "local_head": None,
            "remote_head": None,
            "local_head_prefix": None,
            "remote_head_prefix": None,
            "ahead": None,
            "behind": None,
            "next": "Separate source from data, secrets and generated artifacts before Git initialization.",
            "evidence_state": "SOURCE_BACKED",
            "evidence_refs": ["repo-census-r2"],
            "freshness": "CURRENT",
        })
    return sorted(rows, key=lambda row: row["id"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rows = normalize(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "hanri.repository_inventory.v1",
        "generated_at": payload.get("generated_at") or payload.get("generated_at_utc") or "1970-01-01T00:00:00Z",
        "source_refs": ["repo-census-r2"],
        "repositories": rows,
        "effects": {"git_writes": 0, "remote_writes": 0, "deployments": 0, "can_trade": False, "capital_permission": "DENY"},
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
