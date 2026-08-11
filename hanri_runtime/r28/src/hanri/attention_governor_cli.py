from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanri.attention_governor import run_attention_governor


def main() -> int:
    parser = argparse.ArgumentParser(description="HANRI R39 attention-over-attention governor")
    parser.add_argument("--input", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    result = run_attention_governor(payload, policy=policy)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
