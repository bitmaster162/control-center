#!/usr/bin/env python3
import copy
import json
from validate_canonical_reseal_proposal import PROPOSAL, validate

BASE = json.loads(PROPOSAL.read_text(encoding="utf-8"))

def expect_fail(mutator, expected):
    doc = copy.deepcopy(BASE)
    mutator(doc)
    try:
        validate(doc)
    except ValueError as exc:
        assert expected in str(exc), (expected, str(exc))
        return
    raise AssertionError("expected validation failure")

validate(copy.deepcopy(BASE))
expect_fail(lambda d: d["current_integrity"].__setitem__("current_all_exact", True), "current_all_exact_must_be_false_pre_reseal")
expect_fail(lambda d: d["future_gate"].__setitem__("generic_go_is_authorization", True), "generic_go_authority_forbidden")
expect_fail(lambda d: d["candidates"]["manifest"]["content_object"]["files"][0].__setitem__("sha256", "0" * 64), "manifest_sha_mismatch")
expect_fail(lambda d: d["authorized_future_write_scope"]["drive_writes_exactly"].append({"order": 3, "file": "EXTRA.json"}), "write_scope_must_be_exactly_two")
expect_fail(lambda d: d["historical_binding"].__setitem__("historical_receipts_mutated", True), "historical_receipts_mutation_forbidden")
expect_fail(lambda d: d["post_write_readback"].__setitem__("required", False), "post_write_readback_required")
print("CANONICAL_RESEAL_PROPOSAL_V1_ADVERSARIAL_PASS")
