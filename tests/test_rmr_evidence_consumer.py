from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control_center/scripts/rmr_evidence_consumer.py"
SCHEMA_PATH = ROOT / "control_center/contracts/RMR_EVIDENCE_ENVELOPE_V1.schema.json"
spec = importlib.util.spec_from_file_location("rmr_evidence_consumer", MODULE_PATH)
assert spec and spec.loader
rmr = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rmr
spec.loader.exec_module(rmr)

TOKEN = "a" * 64


def health(**overrides):
    body = {
        "service_status": rmr.EXPECTED_SERVICE_STATUS,
        "router_status": rmr.EXPECTED_ROUTER_STATUS,
        "authority_class": rmr.EXPECTED_AUTHORITY_CLASS,
        "source_head": rmr.PINNED_RMR_HEAD,
        "source_tree": rmr.PINNED_RMR_TREE,
        "approved_source_head": rmr.PINNED_RMR_HEAD,
        "approved_source_tree": rmr.PINNED_RMR_TREE,
        "source_identity_runtime_bound": True,
        "tracked_file_hashes_match": True,
        "query_only": 1,
    }
    body.update(overrides)
    return body


def status(**overrides):
    body = {
        "operation": "status",
        "read_only": True,
        "query_only": 1,
        "authority_class": rmr.EXPECTED_AUTHORITY_CLASS,
        "router_status": rmr.EXPECTED_ROUTER_STATUS,
        "source_identity": {"identity_match": True},
        "build_identity": {"source_head": rmr.PINNED_RMR_HEAD, "source_tree": rmr.PINNED_RMR_TREE},
    }
    body.update(overrides)
    return body


class FakeTransport:
    def __init__(self, *, health_body=None, status_body=None, operation_body=None, auth_status=200, raise_exc=None):
        self.health_body = health_body if health_body is not None else health()
        self.status_body = status_body if status_body is not None else status()
        self.operation_body = operation_body if operation_body is not None else {
            "operation": "search_text",
            "read_only": True,
            "authority_class": rmr.EXPECTED_AUTHORITY_CLASS,
            "rows": [{"provenance_status": "DIRECT_SOURCE_BACKED", "conflict_indication": False}],
            "returned_count": 1,
            "has_more": False,
        }
        self.auth_status = auth_status
        self.raise_exc = raise_exc
        self.calls = []

    def __call__(self, method, path, payload, token, timeout):
        self.calls.append((method, path, payload, token, timeout))
        if self.raise_exc:
            raise self.raise_exc
        if method == "GET" and path == "/healthz":
            return 200, {"content-type": "application/json"}, self.health_body
        assert method == "POST" and path == "/v1/router"
        if self.auth_status != 200:
            return self.auth_status, {}, {"error": "unauthorized"}
        if payload == {"operation": "status"}:
            return 200, {"content-type": "application/json"}, self.status_body
        return 200, {"content-type": "application/json"}, self.operation_body


def client(transport):
    return rmr.RMREvidenceConsumer(
        TOKEN,
        transport=transport,
        clock=lambda: "2026-08-24T00:00:00Z",
        request_id_factory=lambda: "req-1",
    )


def test_happy_path_exact_r7_identity():
    t = FakeTransport()
    envelope = client(t).consume("search_text", key="abc", limit=20, offset=0)
    assert envelope["rmr_head"] == rmr.PINNED_RMR_HEAD
    assert envelope["rmr_tree"] == rmr.PINNED_RMR_TREE
    assert envelope["rmr_identity_sha256"] == rmr.PINNED_RMR_IDENTITY_SHA256
    assert envelope["authority_class"] == "EVIDENCE_ONLY"
    assert envelope["router_status"] == "CANDIDATE_NOT_LIVE"
    assert envelope["consumer_decision"] == "EVIDENCE_ACCEPTED_FOR_REVIEW"
    assert envelope["current_truth_promoted"] is False
    assert envelope["execution_authority"] == "NONE"


def test_non_loopback_endpoint_rejected():
    with pytest.raises(rmr.EndpointRejected):
        rmr.RMRBinding(endpoint="http://localhost:8787").validate()


def test_health_status_mismatch():
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(health_body=health(service_status="NOT_READY"))).preflight()


def test_router_status_mismatch():
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(status_body=status(router_status="LIVE"))).preflight()


def test_authority_class_mismatch():
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(status_body=status(authority_class="CURRENT_TRUTH"))).preflight()


def test_rmr_head_mismatch():
    bad = status(build_identity={"source_head": "0" * 40, "source_tree": rmr.PINNED_RMR_TREE})
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(status_body=bad)).preflight()


def test_rmr_tree_mismatch():
    bad = status(build_identity={"source_head": rmr.PINNED_RMR_HEAD, "source_tree": "0" * 40})
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(status_body=bad)).preflight()


def test_identity_sha_mismatch():
    with pytest.raises(rmr.IdentityMismatch):
        rmr.RMRBinding(identity_sha256="0" * 64).validate()


def test_401_auth_failure():
    with pytest.raises(rmr.AuthGateError):
        client(FakeTransport(auth_status=401)).preflight()


def test_timeout_or_network_failure():
    with pytest.raises(rmr.EvidenceConsumerError):
        client(FakeTransport(raise_exc=TimeoutError("timeout"))).preflight()


def test_unsupported_operation_rejected_before_network():
    t = FakeTransport()
    with pytest.raises(rmr.UnsupportedOperation):
        client(t).consume("arbitrary_sql", sql="delete from x")
    assert t.calls == []


def test_provenance_gap_pass_through():
    body = {
        "operation": "search_text",
        "read_only": True,
        "authority_class": "EVIDENCE_ONLY",
        "rows": [{"provenance_status": "PARTIAL_PROVENANCE", "coverage_warning": "explicit gaps preserved"}],
        "returned_count": 1,
        "has_more": False,
    }
    e = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert e["consumer_decision"] == "EVIDENCE_GAP"
    assert "explicit gaps preserved" in e["coverage_warning"]
    assert "conflict indication missing" in e["coverage_warning"]
    assert e["provenance_status"] == "PARTIAL_PROVENANCE"


def test_conflict_pass_through():
    body = {
        "operation": "get_conflicts",
        "read_only": True,
        "authority_class": "EVIDENCE_ONLY",
        "rows": [{"provenance_status": "DIRECT_SOURCE_BACKED", "conflict_indication": True}],
        "returned_count": 1,
        "has_more": False,
    }
    e = client(FakeTransport(operation_body=body)).consume("get_conflicts", key="x")
    assert e["consumer_decision"] == "EVIDENCE_CONFLICT"
    assert e["conflict_indication"] is True


def test_pagination_preservation():
    body = {
        "operation": "search_all",
        "read_only": True,
        "authority_class": "EVIDENCE_ONLY",
        "rows": [],
        "returned_count": 0,
        "has_more": True,
        "next_offset": 20,
    }
    e = client(FakeTransport(operation_body=body)).consume("search_all", key="abc", limit=20, offset=0)
    assert e["has_more"] is True
    assert e["consumer_decision"] == "EVIDENCE_GAP"


def test_response_digest_determinism():
    t = FakeTransport()
    c = client(t)
    e1 = c.consume("search_text", key="abc")
    e2 = c.consume("search_text", key="abc")
    assert e1["response_digest_sha256"] == e2["response_digest_sha256"]
    assert e1["input_digest_sha256"] == e2["input_digest_sha256"]


def test_no_current_truth_promotion_vocabulary():
    t = FakeTransport()
    e = client(t).consume("search_text", key="abc")
    assert e["consumer_decision"] not in rmr.FORBIDDEN_AUTHORITY_LABELS
    assert "CURRENT_TRUTH_ACCEPTED" not in rmr.CONSUMER_DECISIONS
    assert e["current_truth_promoted"] is False


def operation_body(operation="search_text", **overrides):
    body = {
        "operation": operation,
        "read_only": True,
        "authority_class": rmr.EXPECTED_AUTHORITY_CLASS,
        "rows": [{"provenance_status": "DIRECT_SOURCE_BACKED", "conflict_indication": False}],
        "returned_count": 1,
        "has_more": False,
    }
    body.update(overrides)
    return body


def test_operation_router_status_drift_after_exact_preflight_rejected():
    body = operation_body(router_status="LIVE")
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_operation_build_head_drift_after_exact_preflight_rejected():
    body = operation_body(
        build_identity={"source_head": "0" * 40, "source_tree": rmr.PINNED_RMR_TREE}
    )
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_operation_source_identity_mismatch_after_exact_preflight_rejected():
    body = operation_body(source_identity={"identity_match": False})
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_operation_echo_mismatch_rejected():
    body = operation_body(operation="search_all")
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_has_more_string_rejected_not_coerced():
    body = operation_body(has_more="false")
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_negative_returned_count_rejected():
    body = operation_body(returned_count=-1)
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_boolean_returned_count_rejected():
    body = operation_body(returned_count=True)
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_rows_non_list_rejected():
    body = operation_body(rows={"not": "a-list"})
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_row_non_mapping_rejected():
    body = operation_body(rows=["not-an-object"])
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_conflict_indication_non_bool_rejected():
    body = operation_body(conflict_indication="false")
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


class _BoundedReadResponse:
    def __init__(self, *, content_length=None, raw=b"{}"):
        self.status = 200
        self._content_length = content_length
        self._raw = raw
        self.read_called = False
        self.read_amount = None

    def getheader(self, name):
        if name.lower() == "content-length":
            return self._content_length
        return None

    def read(self, amount=None):
        self.read_called = True
        self.read_amount = amount
        return self._raw

    def getheaders(self):
        return [("Content-Type", "application/json")]


class _BoundedReadConnection:
    def __init__(self, response):
        self.response = response
        self.closed = False

    def request(self, method, path, body=None, headers=None):
        return None

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def test_oversized_content_length_rejected_without_full_body_read(monkeypatch):
    monkeypatch.setattr(rmr, "MAX_RESPONSE_BYTES", 32)
    response = _BoundedReadResponse(content_length="33", raw=b"{}")
    connection = _BoundedReadConnection(response)
    monkeypatch.setattr(rmr.http.client, "HTTPConnection", lambda *args, **kwargs: connection)

    with pytest.raises(rmr.ResponseTooLarge):
        rmr._default_transport("GET", "/healthz", None, None, 1.0)
    assert response.read_called is False
    assert connection.closed is True


def test_oversized_response_without_content_length_uses_bounded_read(monkeypatch):
    monkeypatch.setattr(rmr, "MAX_RESPONSE_BYTES", 32)
    response = _BoundedReadResponse(content_length=None, raw=b"x" * 33)
    connection = _BoundedReadConnection(response)
    monkeypatch.setattr(rmr.http.client, "HTTPConnection", lambda *args, **kwargs: connection)

    with pytest.raises(rmr.ResponseTooLarge):
        rmr._default_transport("GET", "/healthz", None, None, 1.0)
    assert response.read_called is True
    assert response.read_amount == 33
    assert connection.closed is True


def test_happy_path_envelope_validates_against_existing_schema():
    envelope = client(FakeTransport()).consume("search_text", key="abc", limit=20, offset=0)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=envelope, schema=schema)


def test_top_level_partial_provenance_preserved_and_classified_partial():
    body = operation_body(
        rows=[],
        returned_count=1,
        provenance_status="PARTIAL_PROVENANCE",
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["provenance_status"] == "PARTIAL_PROVENANCE"
    assert envelope["consumer_decision"] == "EVIDENCE_PARTIAL"


def test_top_level_candidate_only_preserved_and_classified_partial():
    body = operation_body(
        rows=[],
        returned_count=1,
        provenance_status="CANDIDATE_ONLY",
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["provenance_status"] == "CANDIDATE_ONLY"
    assert envelope["consumer_decision"] == "EVIDENCE_PARTIAL"


def test_top_level_and_row_provenance_merge_deterministically():
    body = operation_body(
        provenance_status=["PARTIAL_PROVENANCE", "DIRECT_SOURCE_BACKED"],
        rows=[{"provenance_status": "CANDIDATE_ONLY", "conflict_indication": False}],
        returned_count=1,
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["provenance_status"] == [
        "CANDIDATE_ONLY",
        "DIRECT_SOURCE_BACKED",
        "PARTIAL_PROVENANCE",
    ]
    assert envelope["consumer_decision"] == "EVIDENCE_PARTIAL"


@pytest.mark.parametrize(
    "bad_provenance",
    [42, {"status": "PARTIAL_PROVENANCE"}, ["A", 1], ["A", "A"]],
)
def test_malformed_top_level_provenance_rejected(bad_provenance):
    body = operation_body(provenance_status=bad_provenance)
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_search_response_missing_rows_and_returned_count_rejected():
    body = {
        "operation": "search_text",
        "read_only": True,
        "authority_class": rmr.EXPECTED_AUTHORITY_CLASS,
    }
    with pytest.raises(rmr.ResponseShapeError):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_rows_without_returned_count_derives_len_rows():
    body = operation_body()
    body.pop("returned_count")
    body["rows"] = [
        {"provenance_status": "DIRECT_SOURCE_BACKED", "conflict_indication": False},
        {"provenance_status": "DIRECT_SOURCE_BACKED", "conflict_indication": False},
    ]
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["returned_count"] == 2


def test_explicit_zero_returned_count_remains_valid_nonbool_integer():
    body = operation_body(rows=[], returned_count=0)
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["returned_count"] == 0
    assert envelope["consumer_decision"] == "EVIDENCE_GAP"


def test_current_truth_promoted_true_rejected():
    body = operation_body(current_truth_promoted=True)
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_current_truth_promoted_false_accepted():
    body = operation_body(current_truth_promoted=False)
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["current_truth_promoted"] is False
    assert envelope["evidence"]["current_truth_promoted"] is False


def test_execution_authority_forbidden_rejected():
    body = operation_body(execution_authority="EXECUTION_AUTHORIZED")
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_execution_authority_none_accepted():
    body = operation_body(execution_authority="NONE")
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["execution_authority"] == "NONE"
    assert envelope["evidence"]["execution_authority"] == "NONE"


@pytest.mark.parametrize(
    "forbidden_decision",
    sorted(rmr.FORBIDDEN_AUTHORITY_LABELS),
)
def test_forbidden_top_level_consumer_decision_rejected(forbidden_decision):
    body = operation_body(consumer_decision=forbidden_decision)
    with pytest.raises(rmr.IdentityMismatch):
        client(FakeTransport(operation_body=body)).consume("search_text", key="abc")


def test_ordinary_row_text_with_forbidden_words_is_not_authority_metadata():
    body = operation_body(
        rows=[
            {
                "provenance_status": "DIRECT_SOURCE_BACKED",
                "conflict_indication": False,
                "text": "historical text mentions CURRENT_TRUTH_ACCEPTED and EXECUTION_AUTHORIZED",
            }
        ]
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["consumer_decision"] == "EVIDENCE_ACCEPTED_FOR_REVIEW"


def test_top_level_partial_provenance_envelope_validates_existing_schema():
    body = operation_body(
        rows=[],
        returned_count=1,
        provenance_status="PARTIAL_PROVENANCE",
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=envelope, schema=schema)


def test_nonzero_evidence_missing_provenance_is_gap_not_accepted():
    body = operation_body(
        rows=[{"conflict_indication": False}],
        returned_count=1,
        has_more=False,
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["provenance_status"] is None
    assert envelope["consumer_decision"] == "EVIDENCE_GAP"
    assert "provenance status missing" in envelope["coverage_warning"]


def test_zero_row_search_remains_gap_without_invented_provenance():
    body = operation_body(rows=[], returned_count=0, has_more=False)
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["provenance_status"] is None
    assert envelope["consumer_decision"] == "EVIDENCE_GAP"
    assert envelope["coverage_warning"] == "zero rows returned"


def test_search_missing_has_more_is_explicit_gap_not_silent_false():
    body = operation_body(
        rows=[{"provenance_status": "DIRECT_SOURCE_BACKED", "conflict_indication": False}],
        returned_count=1,
    )
    body.pop("has_more")
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["has_more"] is False
    assert envelope["consumer_decision"] == "EVIDENCE_GAP"
    assert "pagination status missing" in envelope["coverage_warning"]


def test_search_explicit_has_more_false_remains_valid():
    envelope = client(FakeTransport(operation_body=operation_body(has_more=False))).consume("search_text", key="abc")
    assert envelope["has_more"] is False
    assert envelope["consumer_decision"] == "EVIDENCE_ACCEPTED_FOR_REVIEW"
    assert envelope["coverage_warning"] is None


def test_nonzero_evidence_missing_conflict_signal_is_gap():
    body = operation_body(
        rows=[{"provenance_status": "DIRECT_SOURCE_BACKED"}],
        returned_count=1,
        has_more=False,
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["conflict_indication"] is False
    assert envelope["consumer_decision"] == "EVIDENCE_GAP"
    assert "conflict indication missing" in envelope["coverage_warning"]


def test_explicit_top_level_conflict_false_is_sufficient_signal():
    body = operation_body(
        rows=[{"provenance_status": "DIRECT_SOURCE_BACKED"}],
        returned_count=1,
        has_more=False,
        conflict_indication=False,
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["conflict_indication"] is False
    assert envelope["consumer_decision"] == "EVIDENCE_ACCEPTED_FOR_REVIEW"
    assert envelope["coverage_warning"] is None


def test_explicit_conflict_true_remains_conflict_even_with_other_gap_warning():
    body = operation_body(
        rows=[{"conflict_indication": True}],
        returned_count=1,
        has_more=False,
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    assert envelope["conflict_indication"] is True
    assert envelope["consumer_decision"] == "EVIDENCE_CONFLICT"
    assert "provenance status missing" in envelope["coverage_warning"]


def test_completeness_gap_envelopes_validate_existing_schema():
    body = operation_body(
        rows=[{"provenance_status": "DIRECT_SOURCE_BACKED"}],
        returned_count=1,
        has_more=False,
    )
    envelope = client(FakeTransport(operation_body=body)).consume("search_text", key="abc")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=envelope, schema=schema)
    assert envelope["consumer_decision"] == "EVIDENCE_GAP"
