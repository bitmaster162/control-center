from __future__ import annotations

from copy import deepcopy

from build_provider_drift_operator_attention import DRIFT_VERDICT, NEUTRAL_VERDICT, build_projection
from provider_drift_resolution_transition import RESOLVED, drift_fingerprint
from validate_provider_drift_operator_attention import validate_projection


def queue(human_now: int = 0, effects: int = 0) -> dict:
    return {
        "observed_at": "2026-08-12T01:39:00+07:00",
        "human_now": [{"id": f"H{i}"} for i in range(human_now)],
        "summary": {"effect_candidates": effects},
    }


neutral = build_projection(
    {
        "verdict": NEUTRAL_VERDICT,
        "mismatches": [],
        "controller_errors": [],
    },
    queue(),
    {"transition_state": "NO_ACTIVE_DRIFT_HOLD"},
)
assert neutral["system_attention"] == []
assert neutral["absence_does_not_prove_no_drift"] is True
assert neutral["resolution_applied"] is False
assert neutral["summary"]["human_now_before"] == neutral["summary"]["human_now_after"] == 0
assert neutral["summary"]["effect_candidates_before"] == neutral["summary"]["effect_candidates_after"] == 0
assert validate_projection(neutral) == []

synthetic_drift = {
    "verdict": DRIFT_VERDICT,
    "hold_active": True,
    "source_capture": {"observed_at": "2026-08-12T04:10:00+07:00"},
    "controller_errors": ["provider_drift:CURRENT_STATE.json:sha256"],
    "mismatches": [
        {
            "root": "CURRENT_STATE.json",
            "field": "sha256",
            "expected": "expected-sha",
            "observed": "observed-sha",
        }
    ],
}
drift = build_projection(synthetic_drift, queue(human_now=2, effects=3), {"transition_state": "DRIFT_HOLD_UNRESOLVED"})
assert drift["summary"]["system_attention_count"] == 1
assert drift["summary"]["human_now_before"] == drift["summary"]["human_now_after"] == 2
assert drift["summary"]["effect_candidates_before"] == drift["summary"]["effect_candidates_after"] == 3
item = drift["system_attention"][0]
assert item["id"] == "SYSATTN::PROVIDER_DRIFT_HOLD"
assert item["requested_action"] == "READ_ONLY_PROVIDER_DRIFT_INVESTIGATION"
assert item["human_now"] is False
assert item["human_gate"] is False
assert item["effect_candidate"] is False
assert item["dispatch_authorized"] is False
assert item["apply_authorized"] is False
assert item["execution_authorized"] is False
assert item["write_authorized"] is False
assert item["auto_fix"] is False
assert item["controller_errors"] == synthetic_drift["controller_errors"]
assert item["mismatches"] == synthetic_drift["mismatches"]
assert validate_projection(drift) == []

matching_resolution = {
    "transition_state": RESOLVED,
    "active_drift_hold_before": True,
    "active_drift_hold_after": False,
    "source_drift_fingerprint": drift_fingerprint(synthetic_drift),
}
cleared = build_projection(synthetic_drift, queue(human_now=2, effects=3), matching_resolution)
assert cleared["system_attention"] == []
assert cleared["resolution_applied"] is True
assert cleared["resolved_drift_fingerprint"] == drift_fingerprint(synthetic_drift)
assert cleared["summary"]["human_now_before"] == cleared["summary"]["human_now_after"] == 2
assert cleared["summary"]["effect_candidates_before"] == cleared["summary"]["effect_candidates_after"] == 3
assert validate_projection(cleared) == []

wrong_resolution = deepcopy(matching_resolution)
wrong_resolution["source_drift_fingerprint"] = "wrong"
not_cleared = build_projection(synthetic_drift, queue(), wrong_resolution)
assert not_cleared["summary"]["system_attention_count"] == 1
assert not_cleared["resolution_applied"] is False
assert validate_projection(not_cleared) == []

for verdict in [
    "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED",
    "HOLD_INVALID_OR_INCOMPLETE_CAPTURE",
    "REFRESH_EVIDENCE_ONLY_ALLOWED",
    "NO_REFRESH_REQUIRED_CURRENT_LEASE_FRESH",
]:
    projected = build_projection({"verdict": verdict, "mismatches": [], "controller_errors": []}, queue(), matching_resolution)
    assert projected["system_attention"] == [], verdict
    assert projected["resolution_applied"] is False, verdict
    assert validate_projection(projected) == [], verdict

mutated = deepcopy(drift)
mutated["system_attention"][0]["human_now"] = True
assert "drift_item_mismatch:human_now" in validate_projection(mutated)

mutated = deepcopy(drift)
mutated["system_attention"][0]["effect_candidate"] = True
assert "drift_item_mismatch:effect_candidate" in validate_projection(mutated)

mutated = deepcopy(drift)
mutated["system_attention"][0]["write_authorized"] = True
assert "drift_item_mismatch:write_authorized" in validate_projection(mutated)

mutated = deepcopy(drift)
mutated["summary"]["human_now_after"] += 1
assert "human_now_changed" in validate_projection(mutated)

mutated = deepcopy(drift)
mutated["summary"]["effect_candidates_after"] += 1
assert "effect_candidates_changed" in validate_projection(mutated)

mutated = deepcopy(drift)
mutated["safety"]["routing_mutation_authorized"] = True
assert "safety_not_false:routing_mutation_authorized" in validate_projection(mutated)

mutated = deepcopy(neutral)
mutated["system_attention"] = [drift["system_attention"][0]]
mutated["summary"]["system_attention_count"] = 1
assert "non_drift_verdict_must_not_emit_attention" in validate_projection(mutated)

mutated = deepcopy(cleared)
mutated["system_attention"] = [drift["system_attention"][0]]
mutated["summary"]["system_attention_count"] = 1
assert "matching_resolution_must_clear_drift_attention" in validate_projection(mutated)

print("PROVIDER_DRIFT_OPERATOR_ATTENTION_ADVERSARIAL_TEST_PASS")
