from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from . import archive as archive_mod
from . import cli as core
from . import delta_cli as r30
from . import scandir_cli
from . import stability_cli as r31
from .r34_profile_support import TimingBook, timed

NON_OVERLAP_KEYS = (
    "stage.archive_scan_total",
    "stage.projection_total",
    "stage.state_json_write",
    "stage.state_text_write",
    "stage.ledger_write",
    "stage.ledger_read",
    "stage.state_json_read",
    "stage.core_sha256",
)


def run_profiled_process(isolated_config_path: Path, live_projection_root: Path, sandbox_projection_root: Path) -> tuple[dict[str, Any], TimingBook, float]:
    scandir_cli.install_r33_guard()
    accepted_load_config = core.load_config
    book = TimingBook()
    phases = {"archive": False, "projection": False, "json_write_depth": 0}
    originals: list[tuple[Any, str, Any]] = []

    def replace(module: Any, name: str, value: Any) -> None:
        originals.append((module, name, getattr(module, name)))
        setattr(module, name, value)

    def profile_load_config(path: Path) -> dict[str, Any]:
        config = accepted_load_config(path)
        r30.configure_excluded_roots([live_projection_root, sandbox_projection_root])
        return config

    original_scan = core.scan_causal_spine
    def timed_scan(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        phases["archive"] = True
        try:
            return original_scan(*args, **kwargs)
        finally:
            phases["archive"] = False
            book.add("stage.archive_scan_total", time.perf_counter() - started)

    original_projection = core.copy_latest_outputs
    def timed_projection(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        phases["projection"] = True
        try:
            return original_projection(*args, **kwargs)
        finally:
            phases["projection"] = False
            book.add("stage.projection_total", time.perf_counter() - started)

    original_atomic_json = core.atomic_write_json
    def timed_atomic_json(path: Path, value: Any) -> None:
        started = time.perf_counter()
        phases["json_write_depth"] += 1
        try:
            original_atomic_json(path, value)
        finally:
            phases["json_write_depth"] -= 1
            elapsed = time.perf_counter() - started
            if not phases["projection"] and not phases["archive"]:
                book.add("stage.state_json_write", elapsed)
            book.add(f"detail.atomic_json.{Path(path).name}", elapsed)

    original_atomic_text = core.atomic_write_text
    def timed_atomic_text(path: Path, text: str) -> None:
        started = time.perf_counter()
        try:
            original_atomic_text(path, text)
        finally:
            elapsed = time.perf_counter() - started
            if not phases["projection"] and not phases["archive"] and phases["json_write_depth"] == 0:
                book.add("stage.state_text_write", elapsed)
            book.add(f"detail.atomic_text.{Path(path).name}", elapsed)

    original_append = core.append_jsonl
    def timed_append(path: Path, rows: Any) -> None:
        started = time.perf_counter()
        try:
            original_append(path, rows)
        finally:
            elapsed = time.perf_counter() - started
            if not phases["projection"] and not phases["archive"]:
                book.add("stage.ledger_write", elapsed)
            book.add(f"detail.append_jsonl.{Path(path).name}", elapsed)

    original_read_jsonl = core.read_jsonl
    def timed_read_jsonl(path: Path) -> Any:
        started = time.perf_counter()
        try:
            return original_read_jsonl(path)
        finally:
            elapsed = time.perf_counter() - started
            if not phases["projection"] and not phases["archive"]:
                book.add("stage.ledger_read", elapsed)
            book.add(f"detail.read_jsonl.{Path(path).name}", elapsed)

    original_load_json = core.load_json
    def timed_load_json(path: Path) -> Any:
        started = time.perf_counter()
        try:
            return original_load_json(path)
        finally:
            elapsed = time.perf_counter() - started
            if not phases["projection"] and not phases["archive"]:
                book.add("stage.state_json_read", elapsed)
            book.add(f"detail.load_json.{Path(path).name}", elapsed)

    original_core_sha = core.sha256_file
    def timed_core_sha(path: Path, *args: Any, **kwargs: Any) -> str:
        started = time.perf_counter()
        try:
            return original_core_sha(path, *args, **kwargs)
        finally:
            elapsed = time.perf_counter() - started
            if not phases["projection"] and not phases["archive"]:
                book.add("stage.core_sha256", elapsed)
            book.add("detail.core_sha256_all", elapsed)

    original_inspect = archive_mod.inspect_file
    def timed_inspect(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return original_inspect(*args, **kwargs)
        finally:
            book.add("detail.archive_content_inspection", time.perf_counter() - started)

    replace(core, "load_config", profile_load_config)
    replace(core, "scan_causal_spine", timed_scan)
    replace(core, "copy_latest_outputs", timed_projection)
    replace(core, "atomic_write_json", timed_atomic_json)
    replace(core, "atomic_write_text", timed_atomic_text)
    replace(core, "append_jsonl", timed_append)
    replace(core, "read_jsonl", timed_read_jsonl)
    replace(core, "load_json", timed_load_json)
    replace(core, "sha256_file", timed_core_sha)
    replace(archive_mod, "inspect_file", timed_inspect)
    replace(archive_mod, "build_scope_coverage_certificate", timed(book, "detail.archive_scope_build", archive_mod.build_scope_coverage_certificate))
    replace(archive_mod, "discover_same_name_collisions", timed(book, "detail.archive_collision_build", archive_mod.discover_same_name_collisions))
    replace(r31, "material_digest_r31", timed(book, "detail.projection_material_digest", r31.material_digest_r31))
    replace(r30, "_atomic_copy", timed(book, "detail.projection_atomic_copy", r30._atomic_copy))

    started = time.perf_counter()
    try:
        receipt = core.process_once(isolated_config_path)
    finally:
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        for module, name, value in reversed(originals):
            setattr(module, name, value)
    return receipt, book, elapsed_ms
