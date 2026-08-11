from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "control_center.source_envelope.v1"
RESULT_SCHEMA = "control_center.reducer_result.v1"

ALLOWED_SCOPES = {
    "CONTROL_ROOTS": {"CANONICAL_AUTHORITY"},
    "PROJECT_OWNER": {"PROJECT_STATE", "WORK_STATE"},
    "RETURN_BROKER": {"RETURN_TRANSPORT"},
    "HANRI": {"PROJECT_STATE", "PROPOSAL_EVIDENCE"},
    "CONTROL_CENTER": {
        "PORTFOLIO_STATE",
        "DECISION_STATE",
        "SEMANTIC_ACCEPTANCE",
        "APPLY_STATE",
        "COMMERCIAL_STATE",
    },
    "HUMAN_GATE": {"HUMAN_DECISION", "DECISION_STATE", "SEMANTIC_ACCEPTANCE"},
    "COMMERCIAL": {"COMMERCIAL_STATE"},
}

ELIGIBLE_EVIDENCE = {"HASH_VERIFIED", "VERIFIED", "RECEIPTED", "SOURCE_BACKED"}
EVIDENCE_STATES = ELIGIBLE_EVIDENCE | {"CLAIMED", "UNKNOWN"}
FRESHNESS = {"CURRENT", "STALE"}

R64_ANCHOR: dict[str, Any] = {
    "canonical.generation": "R64",
    "canonical.pointer_status": "ACTIVE",
    "canonical.pointer_sha256": "3f23e20c26df665dabe1ac5203ac510c263f45d24aab1e545fb900eff6f3f2ef",
    "canonical.manifest_sha256": "41479390257d29957896796629d92e76bb93c27db98c5df92308b0a456d71b6d",
    "canonical.current_state_sha256": "0efd620477c4895d7fd0d5751cf062096fcd9c54abc647bb3bd4b788893288dd",
    "canonical.role_index_sha256": "e305e9386a7442a0d1f3f160594be643b6f6fc64b437eece86f6284039229567",
    "canonical.role_views_sha256": "9384cb9afbfa6c86b45794e1eeba5cb1c27253338cb4c66e71f2ac8dadc07148",
    "canonical.provider_readback": "all_exact",
    "canonical.r63_is_current": False,
}


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _claim_ref(source_id: str, claim_key: str) -> str:
    return f"{source_id}::{claim_key}"


def validate_envelopes(envelopes: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    source_ids: set[str] = set()

    for index, envelope in enumerate(envelopes):
        prefix = f"envelope[{index}]"
        if envelope.get("schema") != SCHEMA:
            errors.append(f"{prefix}:schema_mismatch")

        source_id = envelope.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            errors.append(f"{prefix}:source_id_missing")
            source_id = f"__invalid_{index}"
        elif source_id in source_ids:
            errors.append(f"{prefix}:duplicate_source_id:{source_id}")
        source_ids.add(source_id)

        source_kind = envelope.get("source_kind")
        if source_kind not in ALLOWED_SCOPES:
            errors.append(f"{prefix}:invalid_source_kind:{source_kind}")

        if envelope.get("freshness") not in FRESHNESS:
            errors.append(f"{prefix}:invalid_freshness:{envelope.get('freshness')}")

        observed_at = envelope.get("observed_at")
        if not isinstance(observed_at, str) or not observed_at:
            errors.append(f"{prefix}:observed_at_missing")

        precedence = envelope.get("precedence")
        if not isinstance(precedence, int) or not 0 <= precedence <= 100:
            errors.append(f"{prefix}:precedence_invalid")

        claims = envelope.get("claims")
        if not isinstance(claims, list):
            errors.append(f"{prefix}:claims_not_list")
            continue

        seen_keys: set[str] = set()
        for claim_index, claim in enumerate(claims):
            cp = f"{prefix}.claim[{claim_index}]"
            key = claim.get("claim_key")
            if not isinstance(key, str) or not key:
                errors.append(f"{cp}:claim_key_missing")
                continue
            if key in seen_keys:
                errors.append(f"{cp}:duplicate_claim_key_in_source:{key}")
            seen_keys.add(key)

            claim_class = claim.get("claim_class")
            if source_kind in ALLOWED_SCOPES and claim_class not in ALLOWED_SCOPES[source_kind]:
                errors.append(f"{cp}:scope_violation:{source_kind}:{claim_class}:{key}")

            if claim.get("evidence_state") not in EVIDENCE_STATES:
                errors.append(f"{cp}:invalid_evidence_state:{key}")

            supersedes = claim.get("supersedes", [])
            if not isinstance(supersedes, list) or not all(isinstance(x, str) and "::" in x for x in supersedes):
                errors.append(f"{cp}:invalid_supersedes:{key}")

    return errors


def reduce(envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    validation_errors = validate_envelopes(envelopes)
    if validation_errors:
        return {
            "schema": RESULT_SCHEMA,
            "status": "FAIL",
            "validation_errors": validation_errors,
            "resolved_claims": [],
            "conflicts": [],
            "stale_claims": [],
            "unresolved_evidence": [],
            "superseded_claims": [],
            "anchor_errors": ["r64_anchor_not_evaluated_due_to_validation_failure"],
        }

    eligible: list[dict[str, Any]] = []
    stale_claims: list[dict[str, Any]] = []
    unresolved_evidence: list[dict[str, Any]] = []

    for envelope in envelopes:
        for claim in envelope["claims"]:
            row = {
                "source_id": envelope["source_id"],
                "source_kind": envelope["source_kind"],
                "observed_at": envelope["observed_at"],
                "freshness": envelope["freshness"],
                "precedence": envelope["precedence"],
                "claim_key": claim["claim_key"],
                "claim_class": claim["claim_class"],
                "value": claim.get("value"),
                "evidence_state": claim["evidence_state"],
                "supersedes": claim.get("supersedes", []),
            }
            row["claim_ref"] = _claim_ref(row["source_id"], row["claim_key"])

            if row["freshness"] == "STALE":
                stale_claims.append(row)
            elif row["evidence_state"] not in ELIGIBLE_EVIDENCE:
                unresolved_evidence.append(row)
            else:
                eligible.append(row)

    superseded_refs = {
        ref
        for row in eligible
        for ref in row.get("supersedes", [])
    }
    superseded_claims = [row for row in eligible if row["claim_ref"] in superseded_refs]
    active = [row for row in eligible if row["claim_ref"] not in superseded_refs]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in active:
        grouped[row["claim_key"]].append(row)

    resolved_claims: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for claim_key in sorted(grouped):
        rows = grouped[claim_key]
        max_precedence = max(row["precedence"] for row in rows)
        top_precedence = [row for row in rows if row["precedence"] == max_precedence]
        newest_time = max(row["observed_at"] for row in top_precedence)
        finalists = [row for row in top_precedence if row["observed_at"] == newest_time]

        values = {_stable_value(row["value"]) for row in finalists}
        if len(values) > 1:
            conflicts.append({
                "claim_key": claim_key,
                "precedence": max_precedence,
                "observed_at": newest_time,
                "candidates": sorted(
                    [
                        {
                            "source_id": row["source_id"],
                            "source_kind": row["source_kind"],
                            "value": row["value"],
                            "evidence_state": row["evidence_state"],
                        }
                        for row in finalists
                    ],
                    key=lambda x: x["source_id"],
                ),
            })
            continue

        winner = sorted(finalists, key=lambda row: row["source_id"])[0]
        resolved_claims.append({
            "claim_key": claim_key,
            "value": winner["value"],
            "source_id": winner["source_id"],
            "source_kind": winner["source_kind"],
            "evidence_state": winner["evidence_state"],
            "observed_at": winner["observed_at"],
            "precedence": winner["precedence"],
        })

    resolved_map = {row["claim_key"]: row["value"] for row in resolved_claims}
    anchor_errors: list[str] = []
    for key, expected in R64_ANCHOR.items():
        if key not in resolved_map:
            anchor_errors.append(f"r64_anchor_missing:{key}")
        elif resolved_map[key] != expected:
            anchor_errors.append(
                f"r64_anchor_mismatch:{key}:expected={_stable_value(expected)}:got={_stable_value(resolved_map[key])}"
            )

    status = "PASS"
    if conflicts:
        status = "CONFLICT"
    if anchor_errors:
        status = "FAIL"

    return {
        "schema": RESULT_SCHEMA,
        "status": status,
        "source_ids": sorted(envelope["source_id"] for envelope in envelopes),
        "resolved_claims": resolved_claims,
        "conflicts": conflicts,
        "stale_claims": sorted(stale_claims, key=lambda row: (row["claim_key"], row["source_id"])),
        "unresolved_evidence": sorted(unresolved_evidence, key=lambda row: (row["claim_key"], row["source_id"])),
        "superseded_claims": sorted(superseded_claims, key=lambda row: (row["claim_key"], row["source_id"])),
        "validation_errors": [],
        "anchor_errors": anchor_errors,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if len(argv) != 1:
        print("usage: reduce_source_envelopes.py <source-bundle.json>", file=sys.stderr)
        return 64

    path = Path(argv[0])
    payload = json.loads(path.read_text(encoding="utf-8"))
    envelopes = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(envelopes, list):
        result = {
            "schema": RESULT_SCHEMA,
            "status": "FAIL",
            "validation_errors": ["bundle.sources_must_be_list"],
            "resolved_claims": [],
            "conflicts": [],
            "stale_claims": [],
            "unresolved_evidence": [],
            "superseded_claims": [],
            "anchor_errors": ["r64_anchor_not_evaluated_due_to_validation_failure"],
        }
    else:
        result = reduce(envelopes)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
