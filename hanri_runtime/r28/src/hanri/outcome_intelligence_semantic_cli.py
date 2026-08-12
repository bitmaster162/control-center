from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanri.outcome_intelligence_semantic import run_outcome_intelligence_v2


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description="HANRI R39.4.0.1 outcome intelligence metric semantics")
    p.add_argument("--loop-state", required=True)
    p.add_argument("--producer-bundle", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--output-receipt", required=True)
    p.add_argument("--generated-at", required=True)
    args = p.parse_args()

    state_path = Path(args.state)
    prior = _read(str(state_path)) if state_path.exists() else None
    result = run_outcome_intelligence_v2(
        loop_state=_read(args.loop_state),
        producer_bundle=_read(args.producer_bundle),
        prior_state=prior,
        policy=_read(args.policy),
        generated_at=args.generated_at,
    )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_receipt).parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(result["state"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.output_receipt).write_text(
        json.dumps(result["receipt"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    receipt = result["receipt"]
    metrics = receipt["metrics"]
    print(json.dumps({
        "status": "PASS",
        "policy_version": receipt["policy_version"],
        "source_semantic_cycle": receipt["source_semantic_cycle"],
        "explicit_outcome_count": receipt["explicit_outcome_count"],
        "tracked_recommendations": metrics["tracked_recommendations"],
        "evaluated_recommendations": metrics["evaluated_recommendations"],
        "outcome_coverage_applicable": metrics["outcome_coverage_applicable"],
        "outcome_coverage_rate": metrics["outcome_coverage_rate"],
        "learning_candidate_count": receipt["learning_candidate_count"],
        "next_attention_mode": receipt["next_attention"]["mode"],
        "execution_effects_performed": receipt["execution_effects_performed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
