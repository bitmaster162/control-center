from __future__ import annotations

import hashlib
import http.client
import json
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

RMR_HOST = "127.0.0.1"
RMR_PORT = 8787
RMR_BASE_URL = "http://127.0.0.1:8787"
PINNED_RMR_HEAD = "8f82ad49c6ddcde7c698eec101b5f0ed985f24bc"
PINNED_RMR_TREE = "911467a1a1d355b51fbe70ff95b86cd63fb7a212"
PINNED_RMR_IDENTITY_SHA256 = "271ba9ba2f78c0cd03db7cb16ae3d2dbe9511926703658d5288677956bff02c2"
EXPECTED_AUTHORITY_CLASS = "EVIDENCE_ONLY"
EXPECTED_ROUTER_STATUS = "CANDIDATE_NOT_LIVE"
EXPECTED_SERVICE_STATUS = "READY_LOOPBACK_ONLY"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024

ALLOWED_OPERATIONS = frozenset(
    {
        "status",
        "search_text",
        "search_all",
        "search_messages",
        "search_documents",
        "search_events",
        "search_project_events",
        "search_claims",
        "get_message",
        "get_message_occurrences",
        "get_message_variants",
        "get_document",
        "get_event",
        "get_claim",
        "get_handoff",
        "get_checkpoint",
        "get_continuity_candidate",
        "get_current_truth_candidate",
        "get_project",
        "get_evidence",
        "get_git_refs",
        "get_conflicts",
        "coverage",
    }
)

CONSUMER_DECISIONS = frozenset(
    {
        "EVIDENCE_ACCEPTED_FOR_REVIEW",
        "EVIDENCE_PARTIAL",
        "EVIDENCE_CONFLICT",
        "EVIDENCE_GAP",
        "EVIDENCE_REJECTED_STALE_OR_IDENTITY_MISMATCH",
        "EVIDENCE_REJECTED_HEALTH_OR_AUTH_FAILURE",
    }
)

FORBIDDEN_AUTHORITY_LABELS = frozenset(
    {
        "CURRENT_TRUTH_ACCEPTED",
        "LIVE_AUTHORITY",
        "PRODUCTION_ACCEPTED",
        "EXECUTION_AUTHORIZED",
    }
)

Transport = Callable[[str, str, Mapping[str, Any] | None, str | None, float], tuple[int, Mapping[str, str], Any]]


class EvidenceConsumerError(RuntimeError):
    """Base fail-closed consumer error."""


class EndpointRejected(EvidenceConsumerError):
    pass


class HealthGateError(EvidenceConsumerError):
    pass


class AuthGateError(EvidenceConsumerError):
    pass


class IdentityMismatch(EvidenceConsumerError):
    pass


class UnsupportedOperation(EvidenceConsumerError):
    pass


class ResponseShapeError(EvidenceConsumerError):
    pass


class ResponseTooLarge(EvidenceConsumerError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_endpoint(endpoint: str) -> None:
    if endpoint != RMR_BASE_URL:
        raise EndpointRejected(f"RMR endpoint must be exactly {RMR_BASE_URL}")


def _is_nonbool_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _read_bounded_response(response: http.client.HTTPResponse) -> bytes:
    declared = response.getheader("Content-Length")
    if declared is not None:
        try:
            declared_bytes = int(declared)
        except (TypeError, ValueError) as exc:
            raise EvidenceConsumerError("invalid RMR Content-Length") from exc
        if declared_bytes < 0:
            raise EvidenceConsumerError("invalid negative RMR Content-Length")
        if declared_bytes > MAX_RESPONSE_BYTES:
            raise ResponseTooLarge("RMR response exceeds MAX_RESPONSE_BYTES")

    raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ResponseTooLarge("RMR response exceeds MAX_RESPONSE_BYTES")
    return raw


def _default_transport(
    method: str,
    path: str,
    payload: Mapping[str, Any] | None,
    token: str | None,
    timeout: float,
) -> tuple[int, Mapping[str, str], Any]:
    body: bytes | None = None
    headers: dict[str, str] = {"Connection": "close", "Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    if token is not None:
        headers["Authorization"] = "Bearer " + token

    conn = http.client.HTTPConnection(RMR_HOST, RMR_PORT, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = _read_bounded_response(response)
        parsed = json.loads(raw.decode("utf-8")) if raw else None
        return response.status, {k.lower(): v for k, v in response.getheaders()}, parsed
    except EvidenceConsumerError:
        raise
    except (OSError, socket.timeout, http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EvidenceConsumerError("RMR transport failure") from exc
    finally:
        conn.close()


@dataclass(frozen=True)
class RMRBinding:
    endpoint: str = RMR_BASE_URL
    head: str = PINNED_RMR_HEAD
    tree: str = PINNED_RMR_TREE
    identity_sha256: str = PINNED_RMR_IDENTITY_SHA256
    authority_class: str = EXPECTED_AUTHORITY_CLASS
    router_status: str = EXPECTED_ROUTER_STATUS
    service_status: str = EXPECTED_SERVICE_STATUS

    def validate(self) -> None:
        validate_endpoint(self.endpoint)
        if self.head != PINNED_RMR_HEAD or self.tree != PINNED_RMR_TREE:
            raise IdentityMismatch("RMR source binding drift")
        if self.identity_sha256 != PINNED_RMR_IDENTITY_SHA256:
            raise IdentityMismatch("RMR identity SHA drift")
        if self.authority_class != EXPECTED_AUTHORITY_CLASS:
            raise IdentityMismatch("RMR authority binding drift")
        if self.router_status != EXPECTED_ROUTER_STATUS:
            raise IdentityMismatch("RMR router-status binding drift")
        if self.service_status != EXPECTED_SERVICE_STATUS:
            raise IdentityMismatch("RMR service-status binding drift")


class RMREvidenceConsumer:
    """Read-only evidence consumer. It never promotes RMR output to Current Truth."""

    def __init__(
        self,
        token: str,
        *,
        binding: RMRBinding | None = None,
        transport: Transport | None = None,
        timeout: float = 30.0,
        clock: Callable[[], str] = _utc_now,
        request_id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        if not isinstance(token, str) or len(token.strip()) != 64 or any(c.isspace() for c in token.strip()):
            raise AuthGateError("RMR token must be a non-whitespace 64-character secret")
        self._token = token.strip()
        self.binding = binding or RMRBinding()
        self.binding.validate()
        self._transport = transport or _default_transport
        self.timeout = float(timeout)
        self._clock = clock
        self._request_id_factory = request_id_factory

    def _health_gate(self) -> Mapping[str, Any]:
        try:
            status, headers, body = self._transport("GET", "/healthz", None, None, min(self.timeout, 10.0))
        except EvidenceConsumerError:
            raise
        except Exception as exc:
            raise EvidenceConsumerError("RMR health transport failure") from exc
        if status != 200 or not isinstance(body, Mapping):
            raise HealthGateError("RMR health check failed")
        if "access-control-allow-origin" in {str(k).lower() for k in headers}:
            raise HealthGateError("unexpected CORS exposure")
        expected = {
            "service_status": self.binding.service_status,
            "router_status": self.binding.router_status,
            "authority_class": self.binding.authority_class,
            "source_head": self.binding.head,
            "source_tree": self.binding.tree,
            "approved_source_head": self.binding.head,
            "approved_source_tree": self.binding.tree,
        }
        for key, value in expected.items():
            if body.get(key) != value:
                raise IdentityMismatch(f"RMR health identity mismatch: {key}")
        if body.get("source_identity_runtime_bound") is not True:
            raise IdentityMismatch("RMR source identity is not runtime-bound")
        if body.get("tracked_file_hashes_match") is not True:
            raise IdentityMismatch("RMR tracked-file hashes mismatch")
        if not _is_nonbool_int(body.get("query_only")) or body.get("query_only") != 1:
            raise HealthGateError("RMR query_only invariant failed")
        return body

    def _status_gate(self) -> Mapping[str, Any]:
        status, headers, body = self._transport(
            "POST", "/v1/router", {"operation": "status"}, self._token, self.timeout
        )
        if status == 401:
            raise AuthGateError("RMR authentication failed")
        if status != 200 or not isinstance(body, Mapping):
            raise HealthGateError("RMR status gate failed")
        if "access-control-allow-origin" in {str(k).lower() for k in headers}:
            raise HealthGateError("unexpected CORS exposure")
        if body.get("read_only") is not True:
            raise HealthGateError("RMR read-only invariant failed")
        if not _is_nonbool_int(body.get("query_only")) or body.get("query_only") != 1:
            raise HealthGateError("RMR query_only invariant failed")
        if body.get("authority_class") != self.binding.authority_class:
            raise IdentityMismatch("RMR authority-class mismatch")
        if body.get("router_status") != self.binding.router_status:
            raise IdentityMismatch("RMR router-status mismatch")
        source_identity = body.get("source_identity") or {}
        build_identity = body.get("build_identity") or {}
        if not isinstance(source_identity, Mapping) or source_identity.get("identity_match") is not True:
            raise IdentityMismatch("RMR source identity mismatch")
        if build_identity.get("source_head") != self.binding.head:
            raise IdentityMismatch("RMR HEAD mismatch")
        if build_identity.get("source_tree") != self.binding.tree:
            raise IdentityMismatch("RMR tree mismatch")
        return body

    def _validate_operation_currentness(self, operation: str, body: Mapping[str, Any]) -> None:
        if body.get("operation") != operation:
            raise ResponseShapeError("RMR operation echo mismatch")
        if body.get("read_only") is not True:
            raise IdentityMismatch("RMR operation escaped read-only ceiling")
        if body.get("authority_class") != self.binding.authority_class:
            raise IdentityMismatch("RMR operation authority-class mismatch")

        exact_optional = {
            "router_status": self.binding.router_status,
            "service_status": self.binding.service_status,
            "source_head": self.binding.head,
            "source_tree": self.binding.tree,
            "approved_source_head": self.binding.head,
            "approved_source_tree": self.binding.tree,
        }
        for key, expected in exact_optional.items():
            if key in body and body.get(key) != expected:
                raise IdentityMismatch(f"RMR operation currentness mismatch: {key}")

        if "query_only" in body:
            query_only = body.get("query_only")
            if not _is_nonbool_int(query_only) or query_only != 1:
                raise HealthGateError("RMR operation query_only invariant failed")

        if "source_identity_runtime_bound" in body and body.get("source_identity_runtime_bound") is not True:
            raise IdentityMismatch("RMR operation source identity is not runtime-bound")
        if "tracked_file_hashes_match" in body and body.get("tracked_file_hashes_match") is not True:
            raise IdentityMismatch("RMR operation tracked-file hashes mismatch")

        if "source_identity" in body:
            source_identity = body.get("source_identity")
            if not isinstance(source_identity, Mapping) or source_identity.get("identity_match") is not True:
                raise IdentityMismatch("RMR operation source identity mismatch")

        if "build_identity" in body:
            build_identity = body.get("build_identity")
            if not isinstance(build_identity, Mapping):
                raise ResponseShapeError("RMR operation build_identity must be an object")
            if build_identity.get("source_head") != self.binding.head:
                raise IdentityMismatch("RMR operation HEAD mismatch")
            if build_identity.get("source_tree") != self.binding.tree:
                raise IdentityMismatch("RMR operation tree mismatch")

    @staticmethod
    def _validate_response_metadata(body: Mapping[str, Any]) -> None:
        if "rows" in body:
            rows = body.get("rows")
            if not isinstance(rows, list):
                raise ResponseShapeError("RMR rows must be a list when present")
            for row in rows:
                if not isinstance(row, Mapping):
                    raise ResponseShapeError("RMR row must be an object")
                if "conflict_indication" in row and not isinstance(row.get("conflict_indication"), bool):
                    raise ResponseShapeError("row conflict_indication must be boolean")
                if "coverage_warning" in row:
                    warning = row.get("coverage_warning")
                    if warning is not None and not isinstance(warning, str):
                        raise ResponseShapeError("row coverage_warning must be string or null")
                if "provenance_status" in row:
                    provenance = row.get("provenance_status")
                    if provenance is not None and not isinstance(provenance, str):
                        raise ResponseShapeError("row provenance_status must be string or null")

        if "returned_count" in body:
            returned_count = body.get("returned_count")
            if not _is_nonbool_int(returned_count) or returned_count < 0:
                raise ResponseShapeError("RMR returned_count must be a non-negative integer")

        if "has_more" in body and not isinstance(body.get("has_more"), bool):
            raise ResponseShapeError("RMR has_more must be boolean")

        if "conflict_indication" in body and not isinstance(body.get("conflict_indication"), bool):
            raise ResponseShapeError("RMR conflict_indication must be boolean")

        if "coverage_warning" in body:
            warning = body.get("coverage_warning")
            if warning is not None and not isinstance(warning, str):
                raise ResponseShapeError("RMR coverage_warning must be string or null")

    @staticmethod
    def _returned_count(body: Mapping[str, Any]) -> int:
        if "returned_count" in body:
            return body["returned_count"]
        rows = body.get("rows")
        if isinstance(rows, list):
            return len(rows)
        return 1

    def preflight(self) -> dict[str, Any]:
        health = self._health_gate()
        status = self._status_gate()
        return {"health": dict(health), "status": dict(status)}

    @staticmethod
    def _classify(body: Mapping[str, Any]) -> tuple[str, str | None, bool, bool]:
        rows = body.get("rows")
        returned_count = RMREvidenceConsumer._returned_count(body)
        has_more = body.get("has_more", False)

        provenance_values: list[str] = []
        coverage_warning = None
        conflict = False
        if isinstance(rows, list):
            for row in rows:
                p = row.get("provenance_status")
                if isinstance(p, str):
                    provenance_values.append(p)
                w = row.get("coverage_warning")
                if coverage_warning is None and isinstance(w, str) and w.strip():
                    coverage_warning = w.strip()
                if row.get("conflict_indication") is True:
                    conflict = True

        if body.get("conflict_indication") is True:
            conflict = True
        if coverage_warning is None and isinstance(body.get("coverage_warning"), str):
            coverage_warning = body.get("coverage_warning") or None

        if conflict:
            return "EVIDENCE_CONFLICT", coverage_warning, True, has_more
        if coverage_warning or has_more:
            return "EVIDENCE_GAP", coverage_warning, False, has_more
        if any(p in {"PARTIAL_PROVENANCE", "CANDIDATE_ONLY"} for p in provenance_values):
            return "EVIDENCE_PARTIAL", coverage_warning, False, has_more
        if returned_count == 0 and body.get("operation", "").startswith("search_"):
            return "EVIDENCE_GAP", coverage_warning or "zero rows returned", False, has_more
        return "EVIDENCE_ACCEPTED_FOR_REVIEW", coverage_warning, False, has_more

    def consume(self, operation: str, **arguments: Any) -> dict[str, Any]:
        if operation not in ALLOWED_OPERATIONS:
            raise UnsupportedOperation(operation)
        self.preflight()

        payload = {"operation": operation, **arguments}
        input_digest = _sha256_json(payload)
        started = time.monotonic()
        status, headers, body = self._transport("POST", "/v1/router", payload, self._token, self.timeout)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if status == 401:
            raise AuthGateError("RMR authentication failed")
        if status != 200 or not isinstance(body, Mapping):
            raise EvidenceConsumerError(f"RMR operation failed with HTTP {status}")
        if "access-control-allow-origin" in {str(k).lower() for k in headers}:
            raise HealthGateError("unexpected CORS exposure")

        self._validate_operation_currentness(operation, body)
        self._validate_response_metadata(body)

        decision, coverage_warning, conflict, has_more = self._classify(body)
        if decision not in CONSUMER_DECISIONS or decision in FORBIDDEN_AUTHORITY_LABELS:
            raise EvidenceConsumerError("invalid consumer decision")

        rows = body.get("rows")
        returned_count = self._returned_count(body)

        provenance_status = None
        if isinstance(rows, list):
            vals = sorted(
                {str(row.get("provenance_status")) for row in rows if isinstance(row, Mapping) and row.get("provenance_status")}
            )
            if vals:
                provenance_status = vals if len(vals) > 1 else vals[0]

        return {
            "request_id": self._request_id_factory(),
            "timestamp_utc": self._clock(),
            "rmr_head": self.binding.head,
            "rmr_tree": self.binding.tree,
            "rmr_identity_sha256": self.binding.identity_sha256,
            "rmr_identity_binding": "PINNED_CONFIG_PLUS_RUNTIME_IDENTITY_MATCH",
            "operation": operation,
            "input_digest_sha256": input_digest,
            "returned_count": returned_count,
            "has_more": has_more,
            "authority_class": EXPECTED_AUTHORITY_CLASS,
            "router_status": EXPECTED_ROUTER_STATUS,
            "provenance_status": provenance_status,
            "coverage_warning": coverage_warning,
            "conflict_indication": conflict,
            "response_digest_sha256": _sha256_json(body),
            "consumer_decision": decision,
            "elapsed_ms": elapsed_ms,
            "evidence": body,
            "current_truth_promoted": False,
            "execution_authority": "NONE",
        }
