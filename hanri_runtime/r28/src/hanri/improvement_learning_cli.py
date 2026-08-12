from __future__ import annotations

import argparse
import json
from pathlib import Path

from hanri.improvement_learning import run_improvement_learning


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser(description="HANRI R39.5 improvement learning loop")
    p.add_argument("--outcome-state", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--state", required=True)
    p.add_argument("--output-receipt", required=True)
    p.add_argument("--generated-at", required=True)
    args = p.parse_args()

    state_path = Path(args.state)
    prior = _read(str(state_path)) if state_path.exists() else None
    result = run_improvement_learning(
        outcome_state=_read(args.outcome_state),
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
    summary = receipt["learning_summary"]
    print(json.dumps({
        "status": receipt["status"],
        "policy_version": receipt["policy_version"],
        "transition": receipt["transition"],
        "source_semantic_cycle": receipt["source_semantic_cycle"],
        "tracked_recommendations": summary["tracked_recommendations"],
        "evaluated_recommendations": summary["evaluated_recommendations"],
        "ranked_improvement_count": receipt["ranked_improvement_count"],
        "corrective_review_items": summary["corrective_review_items"],
        "reinforcement_review_items": summary["reinforcement_review_items"],
        "evidence_debt_items": summary["evidence_debt_items"],
        "evidence_status": summary["evidence_status"],
        "next_attention_mode": receipt["next_attention"]["mode"],
        "execution_effects_performed": receipt["execution_effects_performed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
