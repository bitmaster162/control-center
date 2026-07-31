#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--schema", type=Path, default=ROOT / "contracts/p0-closure-receipt.schema.json")
    args = parser.parse_args()

    try:
        import jsonschema
    except ModuleNotFoundError:
        print(json.dumps({"status": "BLOCKED", "errors": ["missing_dependency:jsonschema"]}, indent=2))
        return 2
    payload = json.loads(args.receipt.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = sorted(e.message for e in jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).iter_errors(payload))

    if payload.get("status") == "RECEIPTED_CLOSED":
        for test in payload.get("negative_tests", []):
            if test.get("status") != "PASS":
                errors.append(f"closed_with_nonpassing_test:{test.get('test_id')}")
        if payload.get("continuity_test", {}).get("status") != "PASS":
            errors.append("closed_without_continuity_pass")
        rotation = payload.get("rotation", {})
        if not rotation.get("new_access_activated_at") or not rotation.get("old_access_revoked_at"):
            errors.append("closed_without_rotation_timestamps")
        if not payload.get("evidence"):
            errors.append("closed_without_evidence")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "p0_id": payload["p0_id"], "receipt_status": payload["status"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
