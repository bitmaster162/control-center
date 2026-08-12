#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
required = [
    "index.html",
    "assets/style.css",
    "assets/app.js",
    "data/snapshot.v1.example.json",
    "contracts/hanri-dashboard-snapshot.schema.json",
    "contracts/SNAPSHOT_DATA_CONTRACT.md",
    "contracts/p0-closure-receipt.schema.json",
    "README.md",
]
for item in required:
    if not (ROOT / item).exists():
        errors.append(f"missing:{item}")

html = (ROOT / "index.html").read_text(encoding="utf-8")
for view in ["overview", "systems", "agents", "decisions", "memory", "communications", "security", "audit", "arbiter"]:
    if f'id="view-{view}"' not in html:
        errors.append(f"missing_view:{view}")

snapshot_path = ROOT / "data/snapshot.v1.example.json"
if snapshot_path.exists():
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    expected = {
        "authority_generation": "R64",
        "authority_status": "ACCEPTED",
        "control_generation_created": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "deploy_permission": "DENY",
        "self_application": False,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            errors.append(f"meta:{key}:expected:{value!r}:got:{meta.get(key)!r}")
    if payload.get("contract", {}).get("version") != "1.0.1":
        errors.append("snapshot_contract_version_not_1.0.1")
    security = {x.get("id"): x for x in payload.get("security", [])}
    for p0 in ["P0-1", "P0-2", "P0-3"]:
        item = security.get(p0, {})
        if item.get("status") != "RECEIPTED_CLOSED":
            errors.append(f"{p0}:must_be_receipted_closed")
        if item.get("evidence_state") not in {"RECEIPTED", "HASH_VERIFIED"}:
            errors.append(f"{p0}:closed_requires_receipted_evidence")

result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_snapshot.py")], cwd=ROOT, capture_output=True, text=True)
if result.returncode:
    errors.append(f"snapshot_validation_failed:{result.stdout.strip()}:{result.stderr.strip()}")

snapshot_text = snapshot_path.read_text(encoding="utf-8") if snapshot_path.exists() else ""
if re.search(r"(?:api[_-]?key|private[_-]?key|password|token)\s*[:=]\s*['\"][^'\"]+", snapshot_text, re.I):
    errors.append("possible_secret_literal")
if "EXACT_PHRASE_NOT_LOCATED" not in snapshot_text:
    errors.append("arbiter_uncertainty_not_explicit")

standalone = ROOT / "HANRI_R64_DASHBOARD_STANDALONE_CONTRACT_V1.html"
if standalone.exists():
    standalone_text = standalone.read_text(encoding="utf-8")
    for external in ['href="assets/style.css"', 'src="data/snapshot.js"', 'src="assets/app.js"']:
        if external in standalone_text:
            errors.append(f"standalone_external_dependency:{external}")
    if 'name="hanri-snapshot-sha256"' not in standalone_text:
        errors.append("standalone_snapshot_hash_missing")

if errors:
    print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
    sys.exit(1)
print(json.dumps({"status": "PASS", "checks": 11, "errors": []}, ensure_ascii=False, indent=2))
