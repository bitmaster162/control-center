from __future__ import annotations

from typing import Sequence

from . import sqlite_cli as r35

PROGRAM_VERSION = "36.0.0"
ACTOR = "HANRI_R36"
HUMAN_LABEL = "HANRI R36"
INTEGRITY_POLICY_VERSION = "36.0.0-heartbeat-integrity-fast-gate-v1"


def install_r36_guard() -> None:
    # R36 is an identity/release overlay on the accepted R35 SQLite runtime.
    # Keep sqlite_cli.py byte-compatible with R35 regressions and update its
    # dynamic module globals only for the R36 entrypoint before installation.
    r35.PROGRAM_VERSION = PROGRAM_VERSION
    r35.ACTOR = ACTOR
    r35.HUMAN_LABEL = HUMAN_LABEL
    r35.INTEGRITY_POLICY_VERSION = INTEGRITY_POLICY_VERSION
    r35.install_r35_guard()


def main(argv: Sequence[str] | None = None) -> int:
    install_r36_guard()
    return r35.core.main(argv)
