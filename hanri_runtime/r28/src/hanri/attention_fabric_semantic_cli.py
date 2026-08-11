from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanri.attention_fabric_semantic import (
    load_envelopes_from_directory,
    run_attention_fabric_semantic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="HANRI R39.3.1 semantic attention fabric")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--governor-policy", required=True)
    parser.add_argument("--fabric-policy", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = {
        "fabric_run_id": args.run_id,
        "generated_at": args.generated_at,
        "envelopes": load_envelopes_from_directory(args.input_dir),
    }
    governor_policy = json.loads(Path(args.governor_policy).read_text(encoding="utf-8"))
    fabric_policy = json.loads(Path(args.fabric_policy).read_text(encoding="utf-8"))
    result = run_attention_fabric_semantic(
        payload,
        governor_policy=governor_policy,
        fabric_policy=fabric_policy,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
