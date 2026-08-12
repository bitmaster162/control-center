from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanri.improvement_recommendations import run_bounded_improvement_recommendations


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description="HANRI R39.6 bounded improvement recommendation compiler")
    p.add_argument("--learning-state", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--output-receipt", required=True)
    p.add_argument("--generated-at", required=True)
    args = p.parse_args()

    state_path = Path(args.state)
    prior = _read(str(state_path)) if state_path.exists() else None
    result = run_bounded_improvement_recommendations(
        learning_state=_read(args.learning_state),
        prior_state=prior,
        policy=_read(args.policy),
        generated_at=args.generated_at,
    )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = Path(args.output_receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(result["state"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt_path.write_text(
        json.dumps(result["receipt"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    receipt = result["receipt"]
    summary = receipt["recommendation_summary"]
    print(json.dumps({
        "status": receipt["status"],
        "policy_version": receipt["policy_version"],
        "transition": receipt["transition"],
        "source_semantic_cycle": receipt["source_semantic_cycle"],
        "recommendation_count": receipt["recommendation_count"],
        "recommendation_status": summary["recommendation_status"],
        "corrective_review_packets": summary["corrective_review_packets"],
        "evidence_collection_packets": summary["evidence_collection_packets"],
        "reinforcement_review_packets": summary["reinforcement_review_packets"],
        "next_attention_mode": receipt["next_attention"]["mode"],
        "execution_effects_performed": receipt["execution_effects_performed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
