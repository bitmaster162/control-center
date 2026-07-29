#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def pretty_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/snapshot.v1.example.json")
    parser.add_argument("--out-js", type=Path, default=ROOT / "data/snapshot.js")
    parser.add_argument("--out-hash", type=Path, default=ROOT / "data/snapshot.sha256")
    parser.add_argument("--standalone", type=Path, default=ROOT / "HANRI_R64_DASHBOARD_STANDALONE_CONTRACT_V1.html")
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    payload_hash = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    args.out_js.write_text(
        "window.HANRI_SNAPSHOT = " + pretty_bytes(payload).decode("utf-8").rstrip() + ";\n",
        encoding="utf-8",
        newline="\n",
    )
    args.out_hash.write_text(f"{payload_hash}  snapshot.canonical.json\n", encoding="utf-8", newline="\n")

    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/style.css").read_text(encoding="utf-8")
    snapshot_js = args.out_js.read_text(encoding="utf-8")
    app = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="assets/style.css" />', f"<style>\n{css}\n</style>")
    html = html.replace('<script src="data/snapshot.js"></script>', f"<script>\n{snapshot_js}\n</script>")
    html = html.replace('<script src="assets/app.js"></script>', f"<script>\n{app}\n</script>")
    html = html.replace("</head>", f'<meta name="hanri-snapshot-sha256" content="{payload_hash}" />\n</head>')
    args.standalone.write_text(html, encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": "PASS",
        "snapshot_sha256": payload_hash,
        "snapshot_js": str(args.out_js),
        "standalone": str(args.standalone),
        "standalone_sha256": hashlib.sha256(args.standalone.read_bytes()).hexdigest(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
