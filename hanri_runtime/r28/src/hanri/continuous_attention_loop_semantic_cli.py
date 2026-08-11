from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
from hanri.continuous_attention_loop_semantic import POLICY_VERSION, advance_continuous_attention_loop_v2

UTC = dt.timezone.utc

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_json(path, payload):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    for name in ("producer-bundle", "fabric-receipt", "policy", "state", "output-receipt"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--generated-at")
    a = p.parse_args()
    policy = read_json(a.policy)
    if policy.get("policy_version") != POLICY_VERSION:
        raise ValueError("policy_version_mismatch")
    state_path = Path(a.state)
    result = advance_continuous_attention_loop_v2(
        producer_bundle=read_json(a.producer_bundle),
        fabric_result=read_json(a.fabric_receipt),
        prior_state=read_json(state_path) if state_path.exists() else None,
        policy=policy,
        generated_at=a.generated_at or dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    write_json(state_path, result["state"])
    write_json(a.output_receipt, result["receipt"])
    print(json.dumps({"status":"PASS", "transition":result["receipt"]["transition"], "wake_index":result["receipt"]["wake_index"], "semantic_cycle_count":result["receipt"]["semantic_cycle_count"], "evidence_hash_algorithm":result["receipt"]["evidence_hash_algorithm"], "execution_effects_performed":0}, sort_keys=True))
    return 0

if __name__ == "__main__":
    main()
