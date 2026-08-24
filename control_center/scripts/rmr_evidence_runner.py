from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from control_center.scripts.rmr_evidence_consumer import (
        ALLOWED_OPERATIONS,
        CONSUMER_DECISIONS,
        EXPECTED_AUTHORITY_CLASS,
        EvidenceConsumerError,
        RMREvidenceConsumer,
    )
except ModuleNotFoundError:  # Direct script execution from control_center/scripts.
    from rmr_evidence_consumer import (
        ALLOWED_OPERATIONS,
        CONSUMER_DECISIONS,
        EXPECTED_AUTHORITY_CLASS,
        EvidenceConsumerError,
        RMREvidenceConsumer,
    )

FORBIDDEN_ARGUMENT_KEYS = frozenset(
    {"operation", "token", "authorization", "endpoint", "base_url"}
)


class RunnerInputError(ValueError):
    """Invalid local runner input; safe to report by class only."""


class RunnerCeilingError(RuntimeError):
    """Consumer output exceeded the review-only runner authority ceiling."""


def _read_token_file(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise RunnerInputError("token_file_unreadable") from exc
    if not token:
        raise RunnerInputError("token_file_empty")
    return token


def _parse_arguments_json(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RunnerInputError("arguments_json_invalid") from exc
    if not isinstance(value, dict):
        raise RunnerInputError("arguments_json_must_be_object")

    lowered = {str(key).lower() for key in value}
    forbidden = sorted(lowered & FORBIDDEN_ARGUMENT_KEYS)
    if forbidden:
        raise RunnerInputError("reserved_argument_key")
    return value


def _assert_review_ceiling(envelope: dict[str, Any]) -> None:
    if envelope.get("authority_class") != EXPECTED_AUTHORITY_CLASS:
        raise RunnerCeilingError("authority_class_broadened")
    if envelope.get("current_truth_promoted") is not False:
        raise RunnerCeilingError("current_truth_promoted")
    if envelope.get("execution_authority") != "NONE":
        raise RunnerCeilingError("execution_authority_broadened")
    if envelope.get("consumer_decision") not in CONSUMER_DECISIONS:
        raise RunnerCeilingError("consumer_decision_out_of_set")


def execute(
    *,
    token_file: Path,
    operation: str,
    arguments_json: str = "{}",
    transport: Callable[..., Any] | None = None,
    clock: Callable[[], str] | None = None,
    request_id_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    if operation not in ALLOWED_OPERATIONS:
        raise RunnerInputError("operation_not_allowed")

    token = _read_token_file(token_file)
    arguments = _parse_arguments_json(arguments_json)

    kwargs: dict[str, Any] = {}
    if transport is not None:
        kwargs["transport"] = transport
    if clock is not None:
        kwargs["clock"] = clock
    if request_id_factory is not None:
        kwargs["request_id_factory"] = request_id_factory

    consumer = RMREvidenceConsumer(token, **kwargs)
    envelope = consumer.consume(operation, **arguments)
    _assert_review_ceiling(envelope)
    return envelope


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review-only local runner for the pinned RMR evidence consumer"
    )
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--operation", choices=sorted(ALLOWED_OPERATIONS), required=True)
    parser.add_argument("--arguments-json", default="{}")
    return parser


def _safe_error_code(exc: BaseException) -> str:
    if isinstance(exc, RunnerInputError):
        return "RUNNER_INPUT_REJECTED"
    if isinstance(exc, RunnerCeilingError):
        return "RUNNER_AUTHORITY_CEILING_REJECTED"
    if isinstance(exc, EvidenceConsumerError):
        return "RMR_EVIDENCE_REJECTED"
    return "RUNNER_INTERNAL_ERROR"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        envelope = execute(
            token_file=args.token_file,
            operation=args.operation,
            arguments_json=args.arguments_json,
        )
    except Exception as exc:
        error = {
            "status": "FAIL",
            "error_code": _safe_error_code(exc),
            "error_class": type(exc).__name__,
            "current_truth_promoted": False,
            "execution_authority": "NONE",
        }
        print(json.dumps(error, sort_keys=True), file=sys.stderr)
        return 2

    print(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
