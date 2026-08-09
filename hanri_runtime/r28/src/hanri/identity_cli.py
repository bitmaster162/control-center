from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from . import cli as core
from . import guarded_cli as r29

ACTOR = "HANRI_R29"
HUMAN_LABEL = "HANRI R29"

_BASE_RENDER_HUMAN_DIGEST = core.render_human_digest
_BASE_SNAPSHOT_EVENT = core.snapshot_event
_BASE_ARCHIVE_FRONTIER_EVENT = core.archive_frontier_event
_BASE_CAUSAL_SPINE_EVENT = core.causal_spine_event


def r29_render_human_digest(
    run_id: str,
    findings: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    falsifications: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]],
    stop_reasons: Sequence[str],
) -> str:
    text = _BASE_RENDER_HUMAN_DIGEST(
        run_id,
        findings,
        candidates,
        falsifications,
        decisions,
        stop_reasons,
    )
    old = "# Human Decision Digest — HANRI R28"
    new = f"# Human Decision Digest — {HUMAN_LABEL}"
    if old not in text:
        raise core.HanriError("R29 identity guard: expected R28 digest marker is missing")
    return text.replace(old, new, 1)


def r29_snapshot_event(path: Path, label: str) -> dict[str, Any]:
    event = _BASE_SNAPSHOT_EVENT(path, label)
    event["actor"] = ACTOR
    return event


def r29_archive_frontier_event(pair: Mapping[str, Any]) -> dict[str, Any]:
    event = _BASE_ARCHIVE_FRONTIER_EVENT(pair)
    event["actor"] = ACTOR
    return event


def r29_causal_spine_event(spine: Mapping[str, Any]) -> dict[str, Any]:
    event = _BASE_CAUSAL_SPINE_EVENT(spine)
    event["actor"] = ACTOR
    return event


def install_identity_guard() -> None:
    r29.install_guard()
    core.render_human_digest = r29_render_human_digest
    core.snapshot_event = r29_snapshot_event
    core.archive_frontier_event = r29_archive_frontier_event
    core.causal_spine_event = r29_causal_spine_event


def main(argv: Sequence[str] | None = None) -> int:
    install_identity_guard()
    return core.main(argv)
