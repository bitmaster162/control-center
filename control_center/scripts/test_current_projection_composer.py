from __future__ import annotations
import json
from pathlib import Path
from compose_current_projection import validate_projection, validate_snapshot
ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "control_center/data/provider_snapshot.current.v1.json"
GENERATED = ROOT / "control_center/data/current_control_plane.generated.v1.json"

def main() -> int:
    s = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    p = json.loads(GENERATED.read_text(encoding="utf-8"))
    assert validate_snapshot(s) == []
    assert validate_projection(s, p) == []
    bad = json.loads(json.dumps(p)); bad["projects"] = [dict(x) for x in p["projects"]]
    next(x for x in bad["projects"] if x["id"] == "agent-authority-audit")["state"] = "WAIT_DEPENDENCY"
    assert "project_state_mismatch:agent-authority-audit" in validate_projection(s, bad)
    attack = json.loads(json.dumps(p)); next(x for x in attack["return_registry_observations"] if x["slot"] == "CODEX-07")["semantic_interpretation"] = "ACCEPTED"
    assert "registry_observation_mismatch:CODEX-07" in validate_projection(s, attack)
    print("CURRENT_PROJECTION_BINDING_PASS")
    return 0
if __name__ == "__main__": raise SystemExit(main())
