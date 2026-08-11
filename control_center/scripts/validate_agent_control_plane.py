from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "control_center" / "scripts" / "build_agent_control_plane.py"
SOURCE_PATH = ROOT / "control_center" / "data" / "agent_control_sources.current.v1.json"
GENERATED_PATH = ROOT / "control_center" / "data" / "agent_control_plane.generated.v1.json"

spec = importlib.util.spec_from_file_location("agent_control_plane", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
generated = json.loads(GENERATED_PATH.read_text(encoding="utf-8"))

errors = module.validate_source(source)
if not errors:
    expected = module.build(source)
    if generated != expected:
        errors.append("generated_semantic_mismatch")

if generated.get("projection_kind") != "NON_AUTHORITY_PROJECTION":
    errors.append("projection_kind_mismatch")
if generated.get("global_dispatch", {}).get("auto_dispatch") is not False:
    errors.append("auto_dispatch_must_be_false")
if len(generated.get("operator_attention", [])) > 3:
    errors.append("operator_attention_exceeds_three")
if any(row.get("dispatch_authorized") is not False for row in generated.get("slots", [])):
    errors.append("slot_dispatch_authority_detected")
if any(row.get("semantic_authority") != "NONE_FROM_REGISTRY" for row in generated.get("slots", [])):
    errors.append("registry_semantic_authority_detected")
if any(row.get("apply_authority") != "NONE_FROM_REGISTRY" for row in generated.get("slots", [])):
    errors.append("registry_apply_authority_detected")

print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
raise SystemExit(0 if not errors else 2)
