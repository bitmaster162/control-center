#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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
    "data/snapshot.current.v1.json",
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

# Historical R64 example remains immutable in semantics and is still validated.
snapshot_path = ROOT / "data/snapshot.v1.example.json"
if snapshot_path.exists():
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    expected = {
        "authority_generation": "R63",
        "authority_status": "ACCEPTED",
        "control_generation_created": False,
        "can_trade": False,
        "capital_permission": "DENY",
        "deploy_permission": "DENY",
        "self_application": False,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            errors.append(f"example_meta:{key}:expected:{value!r}:got:{meta.get(key)!r}")
    if payload.get("contract", {}).get("version") != "1.0.0":
        errors.append("example_snapshot_contract_version_not_1.0.0")
    security = {x.get("id"): x for x in payload.get("security", [])}
    for p0 in ["P0-1", "P0-2", "P0-3"]:
        if security.get(p0, {}).get("status") != "CLAIMED_NOT_RECEIPTED":
            errors.append(f"example_{p0}:must_remain_claimed_not_receipted")

# Validate both the historical example and the current projection against schema v1.
for snapshot in ["data/snapshot.v1.example.json", "data/snapshot.current.v1.json"]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_snapshot.py"), "--snapshot", str(ROOT / snapshot)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        errors.append(f"snapshot_validation_failed:{snapshot}:{result.stdout.strip()}:{result.stderr.strip()}")

current_path = ROOT / "data/snapshot.current.v1.json"
if current_path.exists():
    current = json.loads(current_path.read_text(encoding="utf-8"))
    kpis = {x.get("label"): x.get("value") for x in current.get("kpis", [])}
    systems = {x.get("id"): x for x in current.get("systems", [])}
    decisions = {x.get("id"): x for x in current.get("decisions", [])}
    security = {x.get("id"): x for x in current.get("security", [])}
    current_meta = current.get("meta", {})
    if kpis.get("Canonical authority") != "R64 ACTIVE":
        errors.append("current:r64_canonical_kpi_missing")
    if kpis.get("HANRI runtime") != "R35 LIVE":
        errors.append("current:r35_live_kpi_missing")
    if systems.get("hanri", {}).get("operational") != "OPERATIONAL":
        errors.append("current:hanri_not_operational")
    if decisions.get("D4", {}).get("verdict") != "ACCEPT" or decisions.get("D4", {}).get("implementation_status") != "ACTIVE":
        errors.append("current:d4_not_active_accept")
    if security.get("P0-1", {}).get("status") != "OPEN_REVERIFY":
        errors.append("current:p0_1_must_be_open_reverify_until_full_receipt")
    for p0 in ["P0-2", "P0-3"]:
        if security.get(p0, {}).get("status") != "OPEN":
            errors.append(f"current:{p0}_must_remain_open")
    if current_meta.get("can_trade") is not False or current_meta.get("capital_permission") != "DENY" or current_meta.get("deploy_permission") != "DENY" or current_meta.get("self_application") is not False:
        errors.append("current:effect_ceiling_violation")

for path in [snapshot_path, current_path]:
    snapshot_text = path.read_text(encoding="utf-8") if path.exists() else ""
    if re.search(r"(?:api[_-]?key|private[_-]?key|password|token)\s*[:=]\s*['\"][^'\"]+", snapshot_text, re.I):
        errors.append(f"possible_secret_literal:{path.name}")
if current_path.exists() and "EXACT_PHRASE_NOT_LOCATED" not in current_path.read_text(encoding="utf-8"):
    errors.append("current:arbiter_uncertainty_not_explicit")

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
print(json.dumps({"status": "PASS", "checks": 15, "errors": []}, ensure_ascii=False, indent=2))
