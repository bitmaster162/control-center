#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/snapshot.v1.example.json")
    parser.add_argument("--schema", type=Path, default=ROOT / "contracts/hanri-dashboard-snapshot.schema.json")
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors: list[str] = []
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        errors.extend(sorted(e.message for e in validator.iter_errors(payload)))
    except ModuleNotFoundError:
        # Minimal fail-closed fallback for hosts without jsonschema.
        for key in schema.get("required", []):
            if key not in payload:
                errors.append(f"missing:{key}")

    meta = payload.get("meta", {})
    if meta.get("can_trade") is not False:
        errors.append("can_trade_must_be_false")
    if meta.get("capital_permission") != "DENY":
        errors.append("capital_permission_must_be_DENY")
    if meta.get("deploy_permission") != "DENY":
        errors.append("deploy_permission_must_be_DENY")
    if meta.get("self_application") is not False:
        errors.append("self_application_must_be_false")
    if meta.get("authority_generation") != "R63" or meta.get("authority_status") != "ACCEPTED":
        errors.append("authority_binding_invalid")

    source_ids = {s.get("source_id") for s in payload.get("sources", [])}
    for collection in ["kpis", "current_actions", "blockers", "events", "systems", "agents", "decisions", "memory_layers", "messages", "security"]:
        for index, item in enumerate(payload.get(collection, [])):
            refs = item.get("evidence_refs", [])
            if not refs:
                errors.append(f"{collection}[{index}]:empty_evidence_refs")
            for ref in refs:
                if ref not in source_ids:
                    errors.append(f"{collection}[{index}]:unknown_ref:{ref}")

    # Truth rendering invariant: claimed/open security cannot be marked closed.
    for item in payload.get("security", []):
        if item.get("evidence_state") == "CLAIMED" and item.get("status") == "RECEIPTED_CLOSED":
            errors.append(f"security:{item.get('id')}:claimed_rendered_closed")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "contract_version": payload["contract"]["version"], "sources": len(source_ids)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
