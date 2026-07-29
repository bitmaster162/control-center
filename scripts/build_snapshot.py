#!/usr/bin/env python3
"""Deprecated compatibility wrapper.

The old R64 script treated raw file existence as a snapshot. That is no longer
allowed. This wrapper performs only a read-only source capture and never emits a
dashboard truth projection.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-root", required=True, type=Path)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--out-json", default=Path("data/source_capture.generated.json"), type=Path)
    parser.add_argument("--out-js", type=Path, default=None, help="Ignored; raw capture is JSON only")
    args = parser.parse_args()
    print("DEPRECATED: build_snapshot.py now captures raw sources only; adjudication is required before dashboard projection.", file=sys.stderr)
    return subprocess.call([
        sys.executable,
        str(ROOT / "scripts/capture_sources.py"),
        "--control-root", str(args.control_root),
        "--captured-at", args.captured_at,
        "--out", str(args.out_json),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
