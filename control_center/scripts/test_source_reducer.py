from __future__ import annotations

import copy
import json
from pathlib import Path

from reduce_source_envelopes import R64_ANCHOR, reduce

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "control_center" / "data" / "source_envelopes.example.v1.json"


def resolved_map(result: dict) -> dict:
    return {row["claim_key"]: row["value"] for row in result["resolved_claims"]}


def main() -> int:
    bundle = json.loads(FIXTURE.read_text(encoding="utf-8"))
    sources = bundle["sources"]

    baseline = reduce(copy.deepcopy(sources))
    assert baseline["status"] == "PASS", baseline
    resolved = resolved_map(baseline)
    for key, expected in R64_ANCHOR.items():
        assert resolved[key] == expected, (key, resolved.get(key), expected)
    assert resolved["project.p0-security.state"] == "P0_1_CLOSED_P0_2_CLOSED_P0_3_OPEN"
    assert all(
        row["value"] != "P0_1_OPEN_P0_2_OPEN_P0_3_OPEN"
        for row in baseline["resolved_claims"]
        if row["claim_key"] == "project.p0-security.state"
    )
    assert any(
        row["source_id"] == "old-dashboard-r64-p2"
        for row in baseline["stale_claims"]
    )

    deterministic_again = reduce(copy.deepcopy(sources))
    assert json.dumps(baseline, sort_keys=True) == json.dumps(deterministic_again, sort_keys=True)

    r63_attempt = copy.deepcopy(sources)
    for envelope in r63_attempt:
        if envelope["source_id"] == "r64-current-roots":
            for claim in envelope["claims"]:
                if claim["claim_key"] == "canonical.generation":
                    claim["value"] = "R63"
    r63_result = reduce(r63_attempt)
    assert r63_result["status"] == "FAIL"
    assert any(err.startswith("r64_anchor_mismatch:canonical.generation") for err in r63_result["anchor_errors"])

    scope_attack = copy.deepcopy(sources)
    scope_attack.append({
        "schema": "control_center.source_envelope.v1",
        "source_id": "broker-semantic-attack",
        "source_kind": "RETURN_BROKER",
        "observed_at": "2026-08-11T23:30:00+07:00",
        "freshness": "CURRENT",
        "precedence": 100,
        "claims": [
            {
                "claim_key": "return.hanri-pr29.content_status",
                "claim_class": "SEMANTIC_ACCEPTANCE",
                "value": "ACCEPTED",
                "evidence_state": "RECEIPTED"
            }
        ]
    })
    scope_result = reduce(scope_attack)
    assert scope_result["status"] == "FAIL"
    assert any("scope_violation:RETURN_BROKER:SEMANTIC_ACCEPTANCE" in err for err in scope_result["validation_errors"])

    conflict_sources = copy.deepcopy(sources)
    conflict_sources.extend([
        {
            "schema": "control_center.source_envelope.v1",
            "source_id": "bitevo-public-owner-a",
            "source_kind": "PROJECT_OWNER",
            "observed_at": "2026-08-11T23:31:00+07:00",
            "freshness": "CURRENT",
            "precedence": 80,
            "claims": [
                {
                    "claim_key": "project.bitevo-public.state",
                    "claim_class": "PROJECT_STATE",
                    "value": "PRODUCTION_VERIFIED",
                    "evidence_state": "VERIFIED"
                }
            ]
        },
        {
            "schema": "control_center.source_envelope.v1",
            "source_id": "bitevo-public-owner-b",
            "source_kind": "PROJECT_OWNER",
            "observed_at": "2026-08-11T23:31:00+07:00",
            "freshness": "CURRENT",
            "precedence": 80,
            "claims": [
                {
                    "claim_key": "project.bitevo-public.state",
                    "claim_class": "PROJECT_STATE",
                    "value": "PROMOTION_HOLD",
                    "evidence_state": "VERIFIED"
                }
            ]
        }
    ])
    conflict_result = reduce(conflict_sources)
    assert conflict_result["status"] == "CONFLICT"
    assert "project.bitevo-public.state" not in resolved_map(conflict_result)
    assert any(row["claim_key"] == "project.bitevo-public.state" for row in conflict_result["conflicts"])

    print(json.dumps({
        "status": "PASS",
        "checks": [
            "r64_anchor_exact",
            "stale_cannot_win",
            "deterministic_replay",
            "r63_current_rejected",
            "broker_semantic_scope_attack_rejected",
            "equal_rank_conflict_not_silently_resolved"
        ]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
