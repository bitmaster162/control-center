"""HANRI -> P6 adapter v1.

Pure normalization only. HANRI is capped at factual / transport evidence and
effect-gate candidacy. It cannot create Human/Controller semantic authority,
Current Truth authority, apply authority, or execution authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable, Mapping

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_ATTENTION_MAP = {
    "HANRI_SELF_TRACE": ("AUDIT", "FACTUAL_OBSERVATION"),
    "SYSTEM_HEALTH": ("AUDIT", "FACTUAL_OBSERVATION"),
    "OBSERVATION": ("AUDIT", "FACTUAL_OBSERVATION"),
    "AUDIT_COVERAGE": ("AUDIT", "FACTUAL_OBSERVATION"),
    "RECOMMENDATION_OUTCOME": ("AUDIT", "FACTUAL_OBSERVATION"),
    "OPERATOR_EVENT": ("AUDIT", "FACTUAL_OBSERVATION"),
}

_ALLOWED_FRESHNESS = {"FRESH", "STALE", "UNKNOWN", "UNAVAILABLE", "IDENTITY_CONFLICT"}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _valid_sha(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value.lower()) is not None


def _normalize_evidence_refs(refs: Any) -> tuple[list[dict[str, Any]], bool]:
    """Return normalized refs and whether they contain an identity conflict."""
    if not isinstance(refs, list) or not refs:
        return [], False
    out: list[dict[str, Any]] = []
    locator_to_sha: dict[str, str | None] = {}
    identity_conflict = False
    for idx, ref in enumerate(refs):
        if isinstance(ref, str):
            locator = ref.strip()
            if not locator:
                continue
            item = {"locator": locator, "sha256": None}
        elif isinstance(ref, Mapping):
            locator = str(ref.get("locator", "")).strip()
            if not locator:
                continue
            sha = ref.get("sha256")
            if sha is not None:
                sha = str(sha).lower()
                if not _valid_sha(sha):
                    continue
            item = {"locator": locator, "sha256": sha}
        else:
            continue
        prior = locator_to_sha.get(item["locator"])
        if item["locator"] in locator_to_sha and prior != item["sha256"]:
            identity_conflict = True
        locator_to_sha[item["locator"]] = item["sha256"]
        out.append(item)
    out.sort(key=lambda item: (item["locator"], item["sha256"] or ""))
    return out, identity_conflict


def _record(
    source_cut_id: str,
    subject_id: str,
    artifact_id: str,
    source_class: str,
    authority_class: str,
    observed_at: str,
    *,
    freshness: str = "FRESH",
    claim_status: str = "UNKNOWN",
    claim_value: Any = None,
    transport_status: str = "NONE",
    owner: str = "CONTROL_CENTER",
    do_not_touch: bool = False,
    requested_action: str | None = None,
    human_gate_required: bool = False,
    action_evidence_fresh: bool = False,
) -> dict[str, Any]:
    return {
        "schema": "control_plane.reconciliation_record.v1",
        "source_cut_id": source_cut_id,
        "subject_id": subject_id,
        "artifact_id": artifact_id,
        "artifact_sha256": _sha({
            "artifact_id": artifact_id,
            "subject_id": subject_id,
            "source_class": source_class,
            "claim_value": claim_value,
        }),
        "source_class": source_class,
        "authority_class": authority_class,
        "observed_at": observed_at,
        "freshness": freshness,
        "logical_version": None,
        "predecessor_id": None,
        "supersedes_id": None,
        "claim_value": claim_value,
        "claim_status": claim_status,
        "current_observation": source_class in {"AUDIT", "PROVIDER_READBACK"},
        "evidence_debt": False,
        "transport_status": transport_status,
        "semantic_status": "UNREVIEWED",
        "apply_status": "NOT_APPLIED",
        "owner": owner,
        "do_not_touch": bool(do_not_touch),
        "requested_action": requested_action,
        "human_gate_required": bool(human_gate_required),
        "action_evidence_fresh": bool(action_evidence_fresh),
        "effect_authorized": False,
        "execution_authorized": False,
    }


def _output(
    source_cut_id: str,
    source_ref: str,
    terminal: str,
    records: list[dict[str, Any]],
    effect_gate_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": "control_plane.hanri_p6_adapter_output.v1",
        "terminal": terminal,
        "source_cut_id": source_cut_id,
        "hanri_source_ref": source_ref,
        "records": records,
        "effect_gate_candidates": effect_gate_candidates,
        "invariants": {
            "hanri_semantic_authority": False,
            "hanri_current_truth_authority": False,
            "hanri_apply_authority": False,
            "hanri_execution_authority": False,
            "can_trade": False,
            "capital_permission": "DENY",
        },
    }


def _subject(env: Mapping[str, Any]) -> str | None:
    direct = env.get("subject_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    payload = env.get("payload")
    if isinstance(payload, Mapping):
        nested = payload.get("subject_id")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def adapt_attention(source_cut_id: str, env: Mapping[str, Any]) -> dict[str, Any]:
    source_ref = str(env.get("envelope_id") or "UNKNOWN")
    subject_id = _subject(env)
    if subject_id is None:
        return _output(source_cut_id, source_ref, "ADAPTER_REVISE_SUBJECT_UNBOUND", [], [])

    evidence_refs, identity_conflict = _normalize_evidence_refs(env.get("evidence_refs"))
    if not evidence_refs:
        return _output(source_cut_id, source_ref, "ADAPTER_REVISE_EVIDENCE_UNBOUND", [], [])
    if identity_conflict:
        return _output(source_cut_id, source_ref, "ADAPTER_HOLD_IDENTITY_CONFLICT", [], [])

    source_type = env.get("source_type")
    payload = env.get("payload") if isinstance(env.get("payload"), Mapping) else {}
    observed_at = str(env.get("observed_at") or "")

    if source_type == "AGENT_RETURN":
        binding = payload.get("return_plane_binding")
        if isinstance(binding, Mapping) and binding.get("delivery_id") and _valid_sha(binding.get("artifact_sha256")):
            source_class, authority_class = "VERIFIED_RETURN", "TRANSPORT_ONLY"
            transport_status = "PHYSICALLY_ACCEPTED"
        else:
            source_class, authority_class = "TRANSPORT_OBSERVATION", "TRANSPORT_ONLY"
            transport_status = "REPORTED"
    elif source_type in _ATTENTION_MAP:
        source_class, authority_class = _ATTENTION_MAP[source_type]
        transport_status = "NONE"
    else:
        return _output(source_cut_id, source_ref, "ADAPTER_HOLD_UNSUPPORTED_STATUS", [], [])

    freshness = payload.get("freshness", "UNKNOWN")
    if freshness not in _ALLOWED_FRESHNESS:
        freshness = "UNKNOWN"

    # Deliberately ignore payload semantic/apply/effect authority claims.
    record = _record(
        source_cut_id,
        subject_id,
        source_ref,
        source_class,
        authority_class,
        observed_at,
        freshness=freshness,
        claim_status=str(payload.get("claim_status", "UNKNOWN")),
        claim_value=payload.get("claim_value"),
        transport_status=transport_status,
        owner=str(payload.get("owner") or "CONTROL_CENTER"),
        do_not_touch=bool(payload.get("do_not_touch", False)),
        requested_action=payload.get("requested_action"),
        human_gate_required=bool(payload.get("human_gate_required", False)),
        action_evidence_fresh=bool(payload.get("action_evidence_fresh", False)),
    )
    return _output(source_cut_id, source_ref, "ADAPTER_PASS", [record], [])


def adapt_freshness_surface(
    source_cut_id: str,
    surface: Mapping[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    surface_id = str(surface.get("id") or "").strip()
    if not surface_id:
        return _output(source_cut_id, "freshness:UNKNOWN", "ADAPTER_REVISE_SUBJECT_UNBOUND", [], [])

    native = surface.get("freshness")
    current_proof = surface.get("current_proof") is True
    if native == "CURRENT" and current_proof:
        freshness = "FRESH"
        claim_status = "PASS"
    elif native == "STALE":
        freshness = "STALE"
        claim_status = "HOLD"
    else:
        freshness = "UNKNOWN"
        claim_status = "HOLD"

    do_not_touch = surface.get("operational_status") == "DO_NOT_TOUCH"
    record = _record(
        source_cut_id,
        f"surface:{surface_id}",
        f"freshness:{surface_id}",
        "AUDIT",
        "FACTUAL_OBSERVATION",
        observed_at,
        freshness=freshness,
        claim_status=claim_status,
        claim_value=surface.get("operational_status"),
        owner=str(surface.get("owner") or "CONTROL_CENTER"),
        do_not_touch=do_not_touch,
        action_evidence_fresh=freshness == "FRESH",
    )
    return _output(source_cut_id, f"freshness:{surface_id}", "ADAPTER_PASS", [record], [])


def adapt_approval_item(
    source_cut_id: str,
    item: Mapping[str, Any],
    observed_at: str,
    subject_id: str,
    *,
    evidence_fresh: bool,
) -> dict[str, Any]:
    action_hash = str(item.get("action_hash") or "").lower()
    if not _valid_sha(action_hash):
        return _output(source_cut_id, str(item.get("queue_id") or "UNKNOWN"), "ADAPTER_HOLD_INVALID_ACTION_HASH", [], [])

    requested_action = "::".join([
        str(item.get("operation") or "UNKNOWN"),
        str(item.get("effect_class") or "UNKNOWN"),
        str(item.get("target") or "UNKNOWN"),
    ])
    queue_id = str(item.get("queue_id") or action_hash)
    record = _record(
        source_cut_id,
        subject_id,
        queue_id,
        "AUDIT",
        "FACTUAL_OBSERVATION",
        observed_at,
        freshness="FRESH" if evidence_fresh else "STALE",
        claim_status="HOLD",
        claim_value=item.get("status"),
        requested_action=requested_action,
        human_gate_required=bool(item.get("approval_required")),
        action_evidence_fresh=evidence_fresh,
    )
    candidate = {
        "candidate_id": "hg-" + _sha({"queue_id": queue_id, "action_hash": action_hash}),
        "action_hash": action_hash,
        "requested_action": requested_action,
        "approval_required": bool(item.get("approval_required")),
        "approval_command": item.get("approval_command"),
        "expires_at": item.get("expires_at"),
        "queue_status": item.get("status"),
        "authority_granted": False,
        "effect_authorized": False,
        "execution_authorized": False,
        "auto_execute": False,
    }
    return _output(source_cut_id, queue_id, "ADAPTER_PASS", [record], [candidate])


def adapt_effect_decision(
    source_cut_id: str,
    decision: Mapping[str, Any],
    observed_at: str,
    subject_id: str,
) -> dict[str, Any]:
    source_ref = str(decision.get("action_hash") or "UNKNOWN")
    if decision.get("execution_authorized") not in (None, False):
        return _output(source_cut_id, source_ref, "ADAPTER_HOLD_AUTHORITY_ESCALATION", [], [])
    if not _valid_sha(source_ref):
        return _output(source_cut_id, source_ref, "ADAPTER_HOLD_INVALID_ACTION_HASH", [], [])

    verdict = decision.get("policy_verdict")
    if verdict == "DENY":
        claim_status, human_gate_required = "REVISE", False
    elif verdict == "HUMAN_APPROVAL":
        claim_status, human_gate_required = "HOLD", True
    elif verdict == "ALLOW":
        claim_status, human_gate_required = "PASS", False
    else:
        return _output(source_cut_id, source_ref, "ADAPTER_HOLD_UNSUPPORTED_STATUS", [], [])

    action = decision.get("action")
    requested_action = json.dumps(action if isinstance(action, Mapping) else {}, sort_keys=True)
    record = _record(
        source_cut_id,
        subject_id,
        "effect-policy:" + source_ref,
        "AUDIT",
        "FACTUAL_OBSERVATION",
        observed_at,
        freshness="FRESH",
        claim_status=claim_status,
        claim_value=verdict,
        requested_action=requested_action,
        human_gate_required=human_gate_required,
        action_evidence_fresh=True,
    )
    return _output(source_cut_id, source_ref, "ADAPTER_PASS", [record], [])
