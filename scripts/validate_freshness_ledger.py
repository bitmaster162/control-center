from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_IDS = {
    "continuity-os",
    "archive-os",
    "decision-governor",
    "fable-5",
    "codex-01",
    "codex-05",
}


def validate(payload: dict) -> list[str]:
    errors: list[str] = []

    if payload.get("schema_version") != "1.0.0":
        errors.append("schema_version must be 1.0.0")

    policy = payload.get("policy", {})
    for key in (
        "source_readback_is_not_operational_freshness",
        "current_requires_target_state_proof",
        "missing_discovery_never_authorizes_rerun",
        "promotion_is_human_gated",
    ):
        if policy.get(key) is not True:
            errors.append(f"policy.{key} must be true")

    surfaces = payload.get("surfaces")
    if not isinstance(surfaces, list):
        return errors + ["surfaces must be an array"]

    ids = [item.get("id") for item in surfaces if isinstance(item, dict)]
    if set(ids) != REQUIRED_IDS or len(ids) != len(REQUIRED_IDS):
        errors.append("surfaces must contain exactly the six required unique ids")

    for item in surfaces:
        if not isinstance(item, dict):
            errors.append("each surface must be an object")
            continue
        sid = item.get("id", "<missing>")
        current_proof = item.get("current_proof") is True
        proof_refs = item.get("proof_refs") or []
        freshness = item.get("freshness")
        promotion_allowed = item.get("promotion_allowed") is True
        source_available = item.get("source_available") is True
        operational_status = item.get("operational_status")

        if freshness == "CURRENT" and not current_proof:
            errors.append(f"{sid}: CURRENT requires current_proof=true")
        if current_proof and not proof_refs:
            errors.append(f"{sid}: current_proof=true requires proof_refs")
        if promotion_allowed and not current_proof:
            errors.append(f"{sid}: promotion_allowed requires current_proof=true")
        if source_available and freshness == "CURRENT" and not current_proof:
            errors.append(f"{sid}: source availability cannot imply CURRENT")
        if operational_status == "DO_NOT_TOUCH" and promotion_allowed:
            errors.append(f"{sid}: DO_NOT_TOUCH cannot be auto-promoted")
        if not item.get("missing_proof"):
            errors.append(f"{sid}: missing_proof must be non-empty")
        if not item.get("promotion_rule"):
            errors.append(f"{sid}: promotion_rule must be non-empty")
        if not item.get("observations"):
            errors.append(f"{sid}: observations must be non-empty")

    invariants = payload.get("invariants", {})
    if invariants.get("can_trade") is not False:
        errors.append("invariants.can_trade must be false")
    if invariants.get("capital_permission") != "DENY":
        errors.append("invariants.capital_permission must be DENY")
    if invariants.get("self_application") is not False:
        errors.append("invariants.self_application must be false")
    if invariants.get("auto_dispatch") is not False:
        errors.append("invariants.auto_dispatch must be false")
    if invariants.get("auto_promotion") is not False:
        errors.append("invariants.auto_promotion must be false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        type=Path,
        default=ROOT / "data/freshness.r38.2.example.json",
    )
    args = parser.parse_args()

    try:
        payload = json.loads(args.ledger.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: unable to parse ledger: {exc}")
        return 2

    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("HANRI_R38_2_FRESHNESS_LEDGER_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
