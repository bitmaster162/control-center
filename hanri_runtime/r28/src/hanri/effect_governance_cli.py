from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .effect_governance import evaluate_actions, load_policy


def _load_actions(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("actions"), list):
        return payload["actions"]
    raise ValueError("input must be a JSON list or an object with an actions list")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HANRI R37 shadow effect-governance evaluator")
    parser.add_argument("--policy", required=True, help="Path to R37 effect policy JSON")
    parser.add_argument("--input", required=True, help="Path to action-candidate JSON")
    parser.add_argument("--output", help="Optional receipt output path")
    parser.add_argument("--now", help="Optional deterministic ISO-8601 evaluation time")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    policy = load_policy(args.policy)
    actions = _load_actions(Path(args.input))
    receipt = evaluate_actions(actions, policy, now=args.now)
    rendered = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"HANRI_R37_EFFECT_GOVERNANCE_SHADOW_PASS {output}")
    else:
        print(rendered, end="")
    print(
        "R37_EFFECT_COUNTS "
        + " ".join(f"{key}={value}" for key, value in sorted(receipt["verdict_counts"].items()))
    )
    print("EXECUTION_EFFECTS_PERFORMED 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
