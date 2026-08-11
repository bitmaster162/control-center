from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from hanri.continuous_attention_loop import POLICY_VERSION, advance_continuous_attention_loop

UTC = dt.timezone.utc


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_exact(path: Path, payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="HANRI R39.3 continuous attention loop")
    parser.add_argument("--producer-bundle", required=True)
    parser.add_argument("--fabric-receipt", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output-receipt", required=True)
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    generated_at = args.generated_at or dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")
    policy = _read_json(Path(args.policy))
    if policy.get("policy_version") != POLICY_VERSION:
        raise SystemExit(f"expected policy_version={POLICY_VERSION}")

    state_path = Path(args.state)
    prior_state = _read_json(state_path) if state_path.exists() else None
    result = advance_continuous_attention_loop(
        producer_bundle=_read_json(Path(args.producer_bundle)),
        fabric_result=_read_json(Path(args.fabric_receipt)),
        prior_state=prior_state,
        policy=policy,
        generated_at=generated_at,
    )

    _write_exact(state_path, result["state"])
    _write_exact(Path(args.output_receipt), result["receipt"])

    receipt = result["receipt"]
    print(json.dumps({
        "status": "PASS",
        "policy_version": POLICY_VERSION,
        "transition": receipt["transition"],
        "wake_index": receipt["wake_index"],
        "semantic_cycle_count": receipt["semantic_cycle_count"],
        "coverage_complete": receipt["coverage_complete"],
        "active_proposal_count": receipt["active_proposal_count"],
        "tracked_proposal_count": receipt["tracked_proposal_count"],
        "unresolved_negative_outcome_count": len(receipt["unresolved_negative_outcomes"]),
        "next_attention_mode": receipt["next_attention"]["mode"],
        "state_sha256": receipt["state_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
        "execution_effects_performed": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
