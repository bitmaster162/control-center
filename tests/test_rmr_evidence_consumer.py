from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control_center/scripts/rmr_evidence_consumer.py"
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
    assert e["coverage_warning"] == "explicit gaps preserved"
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
