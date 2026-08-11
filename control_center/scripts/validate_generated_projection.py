from __future__ import annotations

import json
import sys
from pathlib import Path

from validate_control_plane_projection import validate

EXPECTED_SOURCE = "GENERATED_FROM_PROVIDER_SNAPSHOT"
EXPECTED_DRIVE_FILE_ID = "10HUmbzBVCQDnbFAL6UQ6B2O336ENkEW5"
EXPECTED_POINTER_SHA256 = "3d28490e97568393c1ed6f33f34bc03406cdc98a4b74d32e2df6c5ed08f4d3d3"
PATH_ONLY_ERRORS = {"R64_pointer_locator_mismatch", "R64_pointer_artifact_mismatch"}


def check(payload: dict) -> list[str]:
    errors = validate(payload)
    if payload.get("projection_source") != EXPECTED_SOURCE:
        errors.append("generated_projection_source_mismatch")
        return errors

    errors = [error for error in errors if error not in PATH_ONLY_ERRORS]
    pointer = payload.get("canonical_current", {}).get("pointer", {})
    if pointer.get("drive_file_id") != EXPECTED_DRIVE_FILE_ID:
        errors.append("generated_pointer_drive_file_id_mismatch")
    if pointer.get("sha256") != EXPECTED_POINTER_SHA256:
        errors.append("generated_pointer_sha_mismatch")
    if pointer.get("provider_readback") != "all_exact":
        errors.append("generated_pointer_readback_mismatch")
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if len(argv) != 1:
        print("usage: validate_generated_projection.py <projection.json>", file=sys.stderr)
        return 64
    path = Path(argv[0])
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = check(payload)
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "projection": str(path), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
