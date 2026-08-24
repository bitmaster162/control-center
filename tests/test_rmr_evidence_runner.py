from __future__ import annotations

import json
from pathlib import Path

import pytest

from control_center.scripts import rmr_evidence_runner as runner
from control_center.scripts.rmr_evidence_consumer import (
    EXPECTED_AUTHORITY_CLASS,
    EXPECTED_ROUTER_STATUS,
    EXPECTED_SERVICE_STATUS,
    PINNED_RMR_HEAD,
    PINNED_RMR_TREE,
    AuthGateError,
)


SECRET = "s" * 64


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, str | None]] = []

    def __call__(self, method, path, payload, token, timeout):
        self.calls.append((method, path, payload, token))

        if method == "GET" and path == "/healthz":
            return 200, {}, {
                "service_status": EXPECTED_SERVICE_STATUS,
                "router_status": EXPECTED_ROUTER_STATUS,
                "authority_class": EXPECTED_AUTHORITY_CLASS,
                "source_head": PINNED_RMR_HEAD,
                "source_tree": PINNED_RMR_TREE,
                "approved_source_head": PINNED_RMR_HEAD,
                "approved_source_tree": PINNED_RMR_TREE,
                "source_identity_runtime_bound": True,
                "tracked_file_hashes_match": True,
                "query_only": 1,
            }

        if method == "POST" and path == "/v1/router" and payload == {"operation": "status"}:
            return 200, {}, {
                "operation": "status",
                "read_only": True,
                "query_only": 1,
                "authority_class": EXPECTED_AUTHORITY_CLASS,
                "router_status": EXPECTED_ROUTER_STATUS,
                "source_identity": {"identity_match": True},
                "build_identity": {
                    "source_head": PINNED_RMR_HEAD,
                    "source_tree": PINNED_RMR_TREE,
                },
            }

        if method == "POST" and path == "/v1/router":
            assert isinstance(payload, dict)
            return 200, {}, {
                "operation": payload["operation"],
                "read_only": True,
                "query_only": 1,
                "authority_class": EXPECTED_AUTHORITY_CLASS,
                "router_status": EXPECTED_ROUTER_STATUS,
                "returned_count": 1,
                "has_more": False,
                "provenance_status": "SOURCE_BACKED",
                "conflict_indication": False,
                "rows": [
                    {
                        "id": "row-1",
                        "provenance_status": "SOURCE_BACKED",
                        "conflict_indication": False,
                    }
                ],
                "current_truth_promoted": False,
                "execution_authority": "NONE",
            }

        raise AssertionError(f"unexpected transport call: {method} {path}")


def _token_file(tmp_path: Path, value: str = SECRET) -> Path:
    path = tmp_path / "router.token"
    path.write_text(value + "\n", encoding="utf-8")
    return path


def test_execute_uses_real_consumer_with_fake_transport_and_no_secret_leak(tmp_path):
    token_file = _token_file(tmp_path)
    transport = FakeTransport()

    envelope = runner.execute(
        token_file=token_file,
        operation="search_messages",
        arguments_json='{"query":"alpha"}',
        transport=transport,
        clock=lambda: "2026-08-24T00:00:00Z",
        request_id_factory=lambda: "req-r50",
    )

    assert envelope["request_id"] == "req-r50"
    assert envelope["operation"] == "search_messages"
    assert envelope["consumer_decision"] == "EVIDENCE_ACCEPTED_FOR_REVIEW"
    assert envelope["authority_class"] == "EVIDENCE_ONLY"
    assert envelope["current_truth_promoted"] is False
    assert envelope["execution_authority"] == "NONE"

    serialized = json.dumps(envelope, sort_keys=True)
    assert SECRET not in serialized
    assert str(token_file) not in serialized

    assert transport.calls[0][3] is None
    assert transport.calls[1][3] == SECRET
    assert transport.calls[2][3] == SECRET


@pytest.mark.parametrize(
    "raw",
    [
        "[]",
        '"text"',
        "null",
        "123",
        "true",
    ],
)
def test_arguments_json_must_be_object(raw):
    with pytest.raises(runner.RunnerInputError):
        runner._parse_arguments_json(raw)


@pytest.mark.parametrize(
    "payload",
    [
        {"operation": "status"},
        {"TOKEN": "x"},
        {"Authorization": "x"},
        {"endpoint": "http://example.invalid"},
        {"base_url": "http://example.invalid"},
    ],
)
def test_reserved_transport_and_auth_arguments_rejected(payload):
    with pytest.raises(runner.RunnerInputError):
        runner._parse_arguments_json(json.dumps(payload))


def test_invalid_token_is_not_disclosed_by_cli(tmp_path, capsys):
    token_file = _token_file(tmp_path, "invalid-secret-material")

    rc = runner.main(
        [
            "--token-file",
            str(token_file),
            "--operation",
            "status",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid-secret-material" not in captured.out
    assert "invalid-secret-material" not in captured.err
    assert str(token_file) not in captured.out
    assert str(token_file) not in captured.err
    error = json.loads(captured.err)
    assert error["status"] == "FAIL"
    assert error["error_code"] == "RMR_EVIDENCE_REJECTED"
    assert error["error_class"] == AuthGateError.__name__
    assert error["current_truth_promoted"] is False
    assert error["execution_authority"] == "NONE"


def test_runner_has_no_endpoint_override_option():
    help_text = runner.build_parser().format_help()
    assert "--endpoint" not in help_text
    assert "--base-url" not in help_text
    assert "--token-file" in help_text


def test_runner_ceiling_fails_closed_on_promotion():
    with pytest.raises(runner.RunnerCeilingError):
        runner._assert_review_ceiling(
            {
                "authority_class": "EVIDENCE_ONLY",
                "consumer_decision": "EVIDENCE_ACCEPTED_FOR_REVIEW",
                "current_truth_promoted": True,
                "execution_authority": "NONE",
            }
        )


def test_runner_ceiling_fails_closed_on_execution_authority():
    with pytest.raises(runner.RunnerCeilingError):
        runner._assert_review_ceiling(
            {
                "authority_class": "EVIDENCE_ONLY",
                "consumer_decision": "EVIDENCE_ACCEPTED_FOR_REVIEW",
                "current_truth_promoted": False,
                "execution_authority": "LOCAL",
            }
        )
