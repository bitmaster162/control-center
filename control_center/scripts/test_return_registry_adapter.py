from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from adapt_return_registry_v4 import adapt

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "control_center" / "data" / "return_registry_v4.fixture.json"


def claims_by_key(envelope: dict) -> dict:
    return {claim["claim_key"]: claim for claim in envelope["claims"]}


def main() -> int:
    envelope = adapt(FIXTURE, observed_at="2026-08-11T23:32:00+07:00", freshness="CURRENT")
    assert envelope["source_kind"] == "RETURN_BROKER"
    assert envelope["freshness"] == "CURRENT"
    claims = claims_by_key(envelope)

    claude = claims["return_registry.slot.CLAUDE-BITUNIX.observation"]
    assert claude["claim_class"] == "RETURN_TRANSPORT"
    assert claude["value"]["reported_state"] == "PENDING_OBSERVATION_WINDOW"
    assert claude["value"]["semantic_interpretation"] == "NONE_TRANSPORT_REGISTRY_OBSERVATION_ONLY"

    codex07 = claims["return_registry.slot.CODEX-07.observation"]
    assert codex07["value"]["reported_state"] == "OUTCOME_PASS"
    assert codex07["claim_class"] == "RETURN_TRANSPORT"
    assert "content_status" not in codex07["value"]
    assert "apply_status" not in codex07["value"]

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["rules"]["can_trade"] = True
    with tempfile.TemporaryDirectory() as td:
        bad_path = Path(td) / "bad.json"
        bad_path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            adapt(bad_path, observed_at="2026-08-11T23:32:00+07:00", freshness="CURRENT")
        except ValueError as exc:
            assert "can_trade_must_be_false" in str(exc)
        else:
            raise AssertionError("unsafe registry unexpectedly adapted")

    wrong_id = copy.deepcopy(payload)
    wrong_id["rules"]["can_trade"] = False
    wrong_id["stable_drive_file_id"] = "wrong"
    with tempfile.TemporaryDirectory() as td:
        bad_path = Path(td) / "wrong-id.json"
        bad_path.write_text(json.dumps(wrong_id), encoding="utf-8")
        try:
            adapt(bad_path, observed_at="2026-08-11T23:32:00+07:00", freshness="CURRENT")
        except ValueError as exc:
            assert "stable_file_id_mismatch" in str(exc)
        else:
            raise AssertionError("wrong stable file id unexpectedly adapted")

    print(json.dumps({
        "status": "PASS",
        "checks": [
            "exact_v4_schema",
            "stable_drive_file_id_binding",
            "claude_bitunix_slot_observed",
            "reported_outcome_not_promoted_to_semantic_acceptance",
            "safety_ceiling_fail_closed",
            "wrong_registry_identity_rejected"
        ]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
