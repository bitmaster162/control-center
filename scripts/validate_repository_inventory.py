#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=ROOT / "data/repositories.v1.example.json")
    parser.add_argument("--schema", type=Path, default=ROOT / "contracts/repository-inventory.schema.json")
    args = parser.parse_args()

    payload = json.loads(args.inventory.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors: list[str] = []
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        errors.extend(sorted(e.message for e in validator.iter_errors(payload)))
    except ModuleNotFoundError:
        for key in schema.get("required", []):
            if key not in payload:
                errors.append(f"missing:{key}")

    effects = payload.get("effects", {})
    expected = {"git_writes": 0, "remote_writes": 0, "deployments": 0, "can_trade": False, "capital_permission": "DENY"}
    for key, value in expected.items():
        if effects.get(key) != value:
            errors.append(f"effects:{key}:expected:{value!r}:got:{effects.get(key)!r}")

    for index, repo in enumerate(payload.get("repositories", [])):
        if repo.get("status") == "PUBLISHED_VERIFIED":
            if not repo.get("local_head") or repo.get("local_head") != repo.get("remote_head"):
                errors.append(f"repositories[{index}]:published_without_exact_head_equality")
        if repo.get("status") == "RUNTIME_ONLY" and repo.get("remote_url") is not None:
            errors.append(f"repositories[{index}]:runtime_root_has_remote")
        for field in ("local_head", "remote_head"):
            value = repo.get(field)
            if value is not None and len(value) != 40:
                errors.append(f"repositories[{index}]:{field}:not_full_sha")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"status": "PASS", "repositories": len(payload.get("repositories", [])), "effects": effects}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
