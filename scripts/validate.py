#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
for required in ["index.html", "assets/style.css", "assets/app.js", "data/snapshot.js", "README.md"]:
    if not (ROOT / required).exists():
        errors.append(f"missing:{required}")

html = (ROOT / "index.html").read_text(encoding="utf-8")
for view in ["overview","systems","agents","decisions","memory","communications","security","arbiter"]:
    if f'id="view-{view}"' not in html:
        errors.append(f"missing_view:{view}")

snap = (ROOT / "data/snapshot.js").read_text(encoding="utf-8")
if "can_trade: false" not in snap or 'capital_permission: "DENY"' not in snap:
    errors.append("global_safety_flags_missing")
if "EXACT_PHRASE_NOT_LOCATED" not in snap:
    errors.append("arbiter_uncertainty_not_explicit")
if re.search(r"(?:api[_-]?key|private[_-]?key|password)\s*[:=]\s*['\"][^'\"]+", snap, re.I):
    errors.append("possible_secret_literal")

if errors:
    print(json.dumps({"status":"FAIL","errors":errors}, ensure_ascii=False, indent=2))
    sys.exit(1)
print(json.dumps({"status":"PASS","checks":5,"errors":[]}, ensure_ascii=False, indent=2))
