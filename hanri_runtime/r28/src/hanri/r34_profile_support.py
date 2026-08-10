from __future__ import annotations

import json
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping

from . import cli as core

EXPECTED_PROGRAM_VERSION = "33.0.0"
FORCE_FULL_REMOVE = (
    "latest_projection_receipt.json",
    "latest_archive_frontier.json",
    "latest_archive_causal_spine.json",
    "latest_archive_scope_certificate.json",
)


def validate_source_config(raw: Mapping[str, Any]) -> None:
    if str(raw.get("program_version", "")) != EXPECTED_PROGRAM_VERSION:
        raise core.HanriError("R34 profiler requires accepted R33 config version 33.0.0")
    if raw.get("shadow_only") is not True:
        raise core.HanriError("R34 profiler requires shadow_only=true")
    if raw.get("external_model_api") != "DENY":
        raise core.HanriError("R34 profiler requires external_model_api=DENY")
    if raw.get("can_trade") is not False:
        raise core.HanriError("R34 profiler requires can_trade=false")
    state_root = core.expand_path(str(raw.get("state_root", "")))
    if "ControlCenterHANRIR33" not in str(state_root):
        raise core.HanriError("R34 profiler requires accepted R33 state_root")


def state_metadata_snapshot(root: Path) -> dict[str, tuple[int, int]]:
    if not root.exists():
        return {}
    result: dict[str, tuple[int, int]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        result[str(path.relative_to(root)).casefold()] = (int(stat.st_size), int(stat.st_mtime_ns))
    return result


def clone_live_state(live_state_root: Path, sandbox_state_root: Path) -> None:
    if not live_state_root.exists():
        raise core.HanriError(f"accepted R33 state root missing: {live_state_root}")
    shutil.copytree(
        live_state_root,
        sandbox_state_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("hanri.lock", "*.tmp-*"),
    )
    for name in FORCE_FULL_REMOVE:
        path = sandbox_state_root / name
        if path.exists():
            path.unlink()


def isolated_config(raw: Mapping[str, Any], sandbox_state_root: Path, sandbox_projection_root: Path) -> dict[str, Any]:
    value = json.loads(json.dumps(dict(raw)))
    value["state_root"] = str(sandbox_state_root)
    value["human_output_root"] = str(sandbox_projection_root)
    value["lock_file"] = str(sandbox_state_root / "hanri.lock")
    return value


class TimingBook:
    def __init__(self) -> None:
        self.elapsed_ms: dict[str, float] = defaultdict(float)
        self.calls: dict[str, int] = defaultdict(int)

    def add(self, key: str, elapsed_seconds: float) -> None:
        self.elapsed_ms[key] += elapsed_seconds * 1000.0
        self.calls[key] += 1

    def rounded(self) -> dict[str, float]:
        return {key: round(value, 3) for key, value in sorted(self.elapsed_ms.items())}

    def call_counts(self) -> dict[str, int]:
        return {key: int(value) for key, value in sorted(self.calls.items())}


def timed(book: TimingBook, key: str, function: Callable[..., Any]) -> Callable[..., Any]:
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            book.add(key, time.perf_counter() - started)
    return wrapped
