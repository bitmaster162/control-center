from __future__ import annotations

import json
from pathlib import Path

from build_effect_readback_plane import build, load

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / "data" / "decision_effect_ledger.generated.v1.json"
RECEIPTS = ROOT / "data" / "effect_receipts.current.v1.json"
GENERATED = ROOT / "data" / "effect_readback_plane.generated.v1.json"


def main() -> int:
    expected = build(load(DECISIONS), load(RECEIPTS))
    actual = json.loads(GENERATED.read_text(encoding="utf-8"))
    errors: list[str] = []
    if actual != expected:
        errors.append("generated_projection_semantic_mismatch")
    summary = actual.get("summary", {})
    if summary.get("effects_authorized") != 0 or summary.get("executions_authorized") != 0:
        errors.append("current_projection_must_not_authorize_effect_or_execution")
    if summary.get("execution_receipts") != 0 or summary.get("readback_receipts") != 0:
        errors.append("current_receipt_counts_must_be_zero")
    candidates = actual.get("effect_candidates", [])
    if len(candidates) != 1 or candidates[0].get("work_order") != "CODEX07-R43-RETURN-PLANE-V2":
        errors.append("current_effect_candidate_mismatch")
    if candidates and candidates[0].get("stage") != "AWAITING_HUMAN_EFFECT_AUTHORIZATION":
        errors.append("current_effect_stage_mismatch")
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
