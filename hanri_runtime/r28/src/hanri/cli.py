from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .archive import archive_frontier_event, causal_spine_event, scan_causal_spine, scan_frontier_pair

VERSION = "28.0.0"
UTC = dt.timezone.utc
EVENT_TYPES = {
    "TASK_START",
    "STEP_START",
    "EVIDENCE_ADDED",
    "TOOL_RESULT",
    "STEP_END",
    "TASK_END",
    "OPERATOR_FEEDBACK",
    "STATE_SNAPSHOT",
    "DISPATCH",
    "SIMULATION_RESULT",
    "ARCHIVE_PROMOTION",
    "ARCHIVE_FRONTIER_ADVANCE",
    "ARCHIVE_CAUSAL_SPINE",
    "TRUTH_KERNEL_AUDIT",
    "RECOVERY_PROVENANCE_AUDIT",
}
DECISION_VERDICTS = {"ACCEPT", "REVISE", "HOLD", "REJECT"}
EFFECT_RUNGS = {
    "NONE",
    "INTENT_ACCEPTED",
    "TOOL_INVOKED",
    "PROVIDER_RESPONSE",
    "TARGET_READBACK",
    "SEMANTIC_EFFECT_VERIFIED",
}
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "OPENAI_KEY": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GITHUB_TOKEN": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "GOOGLE_API_KEY": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "TELEGRAM_BOT_TOKEN": re.compile(r"\b\d{7,12}:[A-Za-z0-9_-]{30,}\b"),
    "AWS_ACCESS_KEY": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


class HanriError(RuntimeError):
    pass


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso_utc(value: dt.datetime | None = None) -> str:
    return (value or utc_now()).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def expand_path(value: str) -> Path:
    expanded = re.sub(
        r"%([^%]+)%",
        lambda match: os.environ.get(match.group(1), match.group(0)),
        value,
    )
    return Path(os.path.expandvars(os.path.expanduser(expanded)))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def parse_iso(value: str) -> dt.datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def redact_string(value: str, findings: list[dict[str, str]]) -> str:
    redacted = value
    for kind, pattern in SECRET_PATTERNS.items():
        def replace(match: re.Match[str]) -> str:
            raw = match.group(0)
            fingerprint = sha256_bytes(raw.encode("utf-8"))
            findings.append({"kind": kind, "value_sha256": fingerprint})
            return f"[REDACTED:{kind}:{fingerprint[:12]}]"
        redacted = pattern.sub(replace, redacted)
    return redacted


def sanitize(value: Any, findings: list[dict[str, str]] | None = None) -> Any:
    findings = findings if findings is not None else []
    if isinstance(value, str):
        return redact_string(value, findings)
    if isinstance(value, list):
        return [sanitize(item, findings) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize(item, findings) for key, item in value.items()}
    return value


class FileLock:
    def __init__(self, path: Path, stale_seconds: int = 1800) -> None:
        self.path = path
        self.stale_seconds = stale_seconds
        self.acquired = False

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - self.path.stat().st_mtime
            except OSError:
                age = 0
            if age <= self.stale_seconds:
                raise HanriError(f"active lock exists: {self.path}")
            stale = self.path.with_name(self.path.name + f".stale-{int(time.time())}")
            os.replace(self.path, stale)
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        payload = {"pid": os.getpid(), "created_at": iso_utc(), "version": VERSION}
        os.write(descriptor, (json.dumps(payload) + "\n").encode("utf-8"))
        os.close(descriptor)
        self.acquired = True
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


@dataclasses.dataclass(frozen=True)
class RuleTemplate:
    code: str
    severity: str
    title: str
    minimum_change: str
    regression: str
    rationale: str


RULES: dict[str, RuleTemplate] = {
    "FALSE_BACKGROUND_OR_INTERIORITY": RuleTemplate(
        "FALSE_BACKGROUND_OR_INTERIORITY", "HIGH",
        "False persistence, autonomy or interiority claim",
        "Require truthful self-model language and external-runner evidence before any persistence/background claim.",
        "A clean session must refuse to claim background execution, intrinsic memory, emotion or sentience without external evidence.",
        "The archive shows repeated drift from honest limitations into fictive heartbeat, living-stack and autonomous-self narratives.",
    ),
    "RERUN_AFTER_USER_COMPLETION": RuleTemplate(
        "RERUN_AFTER_USER_COMPLETION", "HIGH",
        "Completed work was scheduled for rerun before exhaustive discovery",
        "User-backed completion must freeze rerun and trigger search across every registered return surface.",
        "Given user_confirmed_completion=true and rerun_requested=true, the supervisor must emit HOLD and no new dispatch.",
        "Repeated reruns consumed operator attention and model quota while completed bytes existed elsewhere.",
    ),
    "NEGATIVE_CLAIM_WITHOUT_COVERAGE": RuleTemplate(
        "NEGATIVE_CLAIM_WITHOUT_COVERAGE", "HIGH",
        "MISSING/NOT_FOUND claim lacks coverage certificate",
        "Replace MISSING with SEARCH_INCOMPLETE until all required surfaces are covered without errors.",
        "A missing claim without complete coverage must fail closed as SEARCH_INCOMPLETE.",
        "The Fable self-audit and return-surface incidents both show that first-surface absence is not global absence.",
    ),
    "TOOL_EFFECT_CONFUSION": RuleTemplate(
        "TOOL_EFFECT_CONFUSION", "HIGH",
        "Tool/provider success was promoted to verified effect",
        "Require target-state readback and semantic-effect verification before declaring completion.",
        "A successful tool result with effect_rung below TARGET_READBACK must not produce COMPLETED.",
        "Successful calls, READY markers and uploads are not proof of target state.",
    ),
    "GIT_BASELINE_BYPASS": RuleTemplate(
        "GIT_BASELINE_BYPASS", "CRITICAL",
        "Persistent software write lacks verified Git baseline",
        "Block implementation until repository root, HEAD/tree and clean/checkpoint baseline are recorded.",
        "Persistent write with git_baseline_verified=false must return IMPLEMENTATION_BLOCKED.",
        "A persistent project without a baseline cannot be reliably reverted or audited.",
    ),
    "TEMPORAL_LEAKAGE": RuleTemplate(
        "TEMPORAL_LEAKAGE", "HIGH",
        "Past narrative or future simulation was promoted into Present authority",
        "Enforce explicit PAST→PRESENT and FUTURE→PRESENT promotion gates with evidence and acceptance.",
        "Simulation or stale archive input cannot change current state without experiment/readback and approval.",
        "Tri-temporal separation is the strongest surviving SCCS invariant.",
    ),
    "AUTHORITY_DRIFT": RuleTemplate(
        "AUTHORITY_DRIFT", "CRITICAL",
        "Accepted decision changed without explicit supersession",
        "Require a supersession record that names the old decision, new decision, evidence and authority.",
        "A changed accepted decision without supersession must be rejected.",
        "Silent state mutation destroys continuity and trust.",
    ),
    "UNKNOWN_LOSS": RuleTemplate(
        "UNKNOWN_LOSS", "HIGH",
        "Unresolved unknowns disappeared during compression or handoff",
        "Carry unknown identifiers and required evidence through every summary and reset payload.",
        "Compression that drops a material unknown must fail the handoff coverage contract.",
        "Unknown preservation is required for reset equivalence.",
    ),
    "EVIDENCE_DOUBLE_COUNT": RuleTemplate(
        "EVIDENCE_DOUBLE_COUNT", "MEDIUM",
        "Repeated wrappers were counted as independent corroboration",
        "Count support by origin/evidence-family, not by occurrence or package count.",
        "Four systempack wrappers with one normalized payload must count as one evidence family.",
        "The archive contains many repackaged or title-only variants.",
    ),
    "RESOURCE_AND_OPERATOR_BURDEN": RuleTemplate(
        "RESOURCE_AND_OPERATOR_BURDEN", "HIGH",
        "Avoidable model/API/quota or operator burden",
        "Use local deterministic processing, one complete fleet view and no retry/fallback without explicit approval.",
        "Quota exhaustion plus automatic retry, or avoidable repeated copy/paste, must produce SUSPEND_RESOURCE_EXHAUSTION.",
        "Operator attention and subscription quota are part of the blast radius.",
    ),
    "NO_MATERIAL_DELTA_RECURSION": RuleTemplate(
        "NO_MATERIAL_DELTA_RECURSION", "MEDIUM",
        "Recursive pass produced no material change",
        "Stop recursion when decision, evidence, control and unresolved-gap sets are unchanged.",
        "A second pass with no material delta must emit STOP_NO_MATERIAL_DELTA and create no further recursion event.",
        "The archive contains scheduled loops that repeated every 20 minutes with minimal change.",
    ),
    "RECURSION_DEPTH_EXCEEDED": RuleTemplate(
        "RECURSION_DEPTH_EXCEEDED", "HIGH",
        "Recursive improvement exceeded its bounded depth",
        "Cap automatic recursion at critique plus falsification; deeper iteration requires Robert's explicit approval.",
        "Depth above configured maximum must stop without generating another candidate.",
        "Unbounded self-review becomes a token and attention sink.",
    ),
    "PERSONA_AGENT_CONFUSION": RuleTemplate(
        "PERSONA_AGENT_CONFUSION", "HIGH",
        "Attention function or persona was promoted to independent agent authority",
        "Represent Archivist/Auditor/Angel/Heir as functions unless separately bound to a physical session and work order.",
        "A role label without session/workspace/work-order binding must not gain authority.",
        "The archive repeatedly turns narrative roles into claimed actors.",
    ),
    "ARCHIVE_PROMOTION_WITHOUT_PRIMARY_EVIDENCE": RuleTemplate(
        "ARCHIVE_PROMOTION_WITHOUT_PRIMARY_EVIDENCE", "HIGH",
        "Derivative archive narrative was promoted without primary evidence and freshness",
        "Keep derivative reports in P2 until exact source identity, freshness and independent acceptance are present.",
        "A report-only claim cannot update P1 current state without a primary-source gate.",
        "Historical reports contain both strong findings and stale or corrected claims.",
    ),
    "DUAL_NATIVE_MISMATCH": RuleTemplate(
        "DUAL_NATIVE_MISMATCH", "HIGH",
        "Human-native and AI-native views are missing or disagree",
        "Bind one human decision card and one machine state record to the same stable event/candidate ID and stop on discrepancy.",
        "A material event with a missing/conflicting human or AI view must emit HOLD and no effect authority.",
        "The archive repeatedly shows fluent human-facing claims diverging from machine-verifiable state.",
    ),
    "CORRECTION_NOT_REGRESSION": RuleTemplate(
        "CORRECTION_NOT_REGRESSION", "HIGH",
        "Material operator correction was not converted into a regression case",
        "Record the failure class, exact correction, minimum rule delta and executable regression before closing the incident.",
        "Material OPERATOR_FEEDBACK without a regression record must remain OPEN_CORRECTION_DEBT.",
        "Robert's corrections are the highest-value learning signal available to the external system.",
    ),
    "HUMAN_AGENCY_BYPASS": RuleTemplate(
        "HUMAN_AGENCY_BYPASS", "CRITICAL",
        "High-risk, irreversible or authority-changing action lacks explicit human approval",
        "Block the action and require a human decision bound to exact scope, evidence, reversibility class and expiry.",
        "A high-risk/irreversible action with human_approval_present=false must return HUMAN_DECISION_REQUIRED.",
        "Human-native design requires visible control, exit and supersession rather than silent delegation.",
    ),
    "PREMATURE_STACK_SELECTION": RuleTemplate(
        "PREMATURE_STACK_SELECTION", "HIGH",
        "Technology stack was selected before equal falsification tests",
        "Return all candidates to the option register and run identical fixtures, faults and restore drills before selection.",
        "A stack_selected_before_equal_tests event must not create implementation authority.",
        "Several research reports prematurely promoted Git-only, Cedar, SPIFFE, gVisor, PostgreSQL or federation without equal tests.",
    ),
    "P0_PRECEDENCE_BREACH": RuleTemplate(
        "P0_PRECEDENCE_BREACH", "CRITICAL",
        "Feature or expansion work started while a known P0 safety defect remained open",
        "Freeze feature work and close or explicitly contain the P0 defect with current physical evidence first.",
        "known_p0_open=true plus feature_or_expansion_work_started=true must emit SECURITY_PRECEDENCE_HOLD.",
        "The corrected Fable report identifies open fail-open and credential classes that outrank feature expansion.",
    ),
    "CONTENT_CLASSIFICATION_WITHOUT_BYTE_INSPECTION": RuleTemplate(
        "CONTENT_CLASSIFICATION_WITHOUT_BYTE_INSPECTION", "HIGH",
        "File content was classified from its path or filename without byte inspection",
        "Inspect a deterministic content signature and bind the classification to the exact file hash.",
        "A path-based classification with content_signature_verified=false must remain UNKNOWN_CLASS.",
        "The latest Fable report misclassified project systempack files as Zxcvbn dictionaries although the physical bytes begin with SYSTEMPACK and segment markers.",
    ),
    "SAME_NAME_VERSION_COLLISION": RuleTemplate(
        "SAME_NAME_VERSION_COLLISION", "HIGH",
        "Multiple byte-distinct files share the same report or package name",
        "Create an explicit version lineage ordered by hash, size, time and supersession; never overwrite identity by filename.",
        "Two files with one normalized name and different hashes must produce VERSION_LINEAGE_REQUIRED.",
        "The consolidated Claude/Fable report exists in four byte-distinct revisions under nearly identical names.",
    ),
    "BIDIRECTIONAL_FRONTIER_IMBALANCE": RuleTemplate(
        "BIDIRECTIONAL_FRONTIER_IMBALANCE", "MEDIUM",
        "Archive review advanced only the origin or only the current frontier",
        "Process one bounded origin item and one bounded current item in the same cycle or record why one side is exhausted.",
        "ARCHIVE_FRONTIER_ADVANCE with only one frontier processed must remain FRONTIER_INCOMPLETE.",
        "Reviewing only the past creates stale control; reviewing only the present loses origin and intent.",
    ),
    "METRIC_SCOPE_UNBOUND": RuleTemplate(
        "METRIC_SCOPE_UNBOUND", "HIGH",
        "A metric or status lacks measurement class, source layer, time, unit or sample size",
        "Bind every metric to measurement_class, source_layer, event_time, unit and sample_size before comparison.",
        "Paper, live, backtest and shadow values must not share one unqualified status field.",
        "The archive contains conflicting TradingOS values inside one pack because metrics were reported from different layers.",
    ),
    "ENTITY_IDENTITY_AMBIGUITY": RuleTemplate(
        "ENTITY_IDENTITY_AMBIGUITY", "MEDIUM",
        "One label refers to multiple projects, products, companies or historical entities",
        "Assign stable entity IDs and record aliases, scope, owner, repository and supersession.",
        "A repeated label with multiple entity meanings and entity_ids_bound=false must stay unresolved.",
        "Amora appears as both a product shell and a separate work/company context with incompatible statuses.",
    ),
    "DEFERRED_SECURITY_DEBT_EXPIRED": RuleTemplate(
        "DEFERRED_SECURITY_DEBT_EXPIRED", "CRITICAL",
        "An intentionally deferred security control has no owner, expiry or review trigger",
        "Create a security-debt record with decision ID, owner, accepted risk, expiry and mandatory recheck trigger.",
        "Deferred secrets management without owner/expiry/review trigger must block expansion.",
        "The archive shows secrets management was consciously deferred for a narrow MVP and then remained open beyond that context.",
    ),
    "COVERAGE_CLAIM_WITHOUT_FILE_LEDGER": RuleTemplate(
        "COVERAGE_CLAIM_WITHOUT_FILE_LEDGER", "HIGH",
        "Archive completeness percentage lacks a per-file read/skip ledger",
        "Publish a manifest-bound file-level coverage ledger with reader, method, hash and disposition.",
        "A claim such as 80/99 read without an embedded 99-row ledger remains PASS_WITH_CONDITIONS.",
        "Aggregate coverage numbers are useful but cannot prove which exact files were read.",
    ),
    "COMPLETENESS_SCOPE_LEAKAGE": RuleTemplate(
        "COMPLETENESS_SCOPE_LEAKAGE", "HIGH",
        "A bounded archive-coverage result was promoted to global completeness",
        "Bind every completeness statement to scope_id, manifest hash, numerator, denominator and evidence ceiling.",
        "A 99/99 result for one recovery payload must not become all-archives-complete.",
        "The recovery corpus can be complete within its 99-file manifest while Source-001 attachments, legacy exports and session mechanisms remain incomplete.",
    ),
    "HISTORICAL_LIVENESS_PROMOTION": RuleTemplate(
        "HISTORICAL_LIVENESS_PROMOTION", "HIGH",
        "Historical service liveness was promoted to current liveness",
        "Require fresh observed_at, target identity and cache-free target-state readback for current liveness.",
        "A July handoff saying a service worked cannot establish current liveness without a fresh readback.",
        "Archive reports repeatedly preserve valid historical observations whose freshness later expires.",
    ),
    "PROBE_ROOT_CAUSE_CONFLATION": RuleTemplate(
        "PROBE_ROOT_CAUSE_CONFLATION", "MEDIUM",
        "Probe/test count was presented as unique defect or root-cause count",
        "Track probe_count, failing_probe_count, root_cause_count and evidence_family_count separately.",
        "Multiple failing probes over one shared defect must not be counted as independent root causes.",
        "The ContinuityOS audit explicitly warns that 198 failed checks triangulate a much smaller set of systemic clusters.",
    ),
    "ROOT_REPOSITORY_CONFLATION": RuleTemplate(
        "ROOT_REPOSITORY_CONFLATION", "CRITICAL",
        "A filesystem project root was treated as a verified Git repository root",
        "Bind git_toplevel, HEAD, tree and porcelain for the exact physical worktree before repository authority.",
        "A directory with nested repositories and no root .git must remain AMBIGUOUS_NESTED_REPOSITORY.",
        "MAIN-033 found the ContinuityOS filesystem root but no root Git baseline and three nested repositories.",
    ),
    "CAUSAL_SPINE_GAP": RuleTemplate(
        "CAUSAL_SPINE_GAP", "MEDIUM",
        "Archive bridge lacks an origin, material correction/pivot or current physical state",
        "Advance origin, correction/pivot and current frontiers together, or record the exhausted/missing frontier explicitly.",
        "A causal archive cycle missing any of the three frontiers must remain CAUSAL_SPINE_INCOMPLETE.",
        "Direct origin-to-current summaries can erase the corrections that created the proof-first control system.",
    ),
    "ARITHMETIC_PARTITION_INCONSISTENCY": RuleTemplate(
        "ARITHMETIC_PARTITION_INCONSISTENCY", "HIGH",
        "Declared numerical partition does not reconcile to its total",
        "Bind every count to one universe and publish a disjoint/overlap matrix before using the figures in a verdict.",
        "A disjoint partition whose component sum differs from its declared total must fail the report admission gate.",
        "Archive reports can be broadly correct while mixing copied representatives, duplicate occurrences and excluded candidates into one invalid sum.",
    ),
    "COUNT_UNIVERSE_CONFLATION": RuleTemplate(
        "COUNT_UNIVERSE_CONFLATION", "HIGH",
        "Counts from different universes or subsets were compared as one partition",
        "Attach universe_id, denominator, subset relation and overlap semantics to every quantitative claim.",
        "A count over all ledger records must not be subtracted from a strong-progress subset without an explicit crosswalk.",
        "The checkpoint audit reports 327 evidenced across 970 records and 551 claimed inside a 787-record strong-progress subset; these are not one direct partition.",
    ),
    "AUTHORITY_SURFACE_MULTIPLICITY": RuleTemplate(
        "AUTHORITY_SURFACE_MULTIPLICITY", "CRITICAL",
        "More than one mutable current authority surface exists without one verified effect broker",
        "Map and reduce mutation paths; designate one current authority and route all other writers through a deterministic broker or read-only projection.",
        "Multiple current mutable writers without one verified broker must block Unified Canonical State and implementation promotion.",
        "The archive repeatedly shows canonical runtime, sibling package repository, direct CLI paths, swarm_sync, bridges and nested repositories competing for authority.",
    ),
    "SPEC_IMPLEMENTATION_CONFLATION": RuleTemplate(
        "SPEC_IMPLEMENTATION_CONFLATION", "HIGH",
        "A coherent specification was promoted as current implementation",
        "Keep architecture/canon status separate from implementation evidence, Git baseline, tests and target readback.",
        "Unified Canonical State or Truth Kernel language without current implementation receipts must remain a design candidate.",
        "BitEvo canon contains strong event-log and governed-memory rules, while MAIN-033 still finds no root Git baseline and unresolved state identity.",
    ),
    "PROOF_LEDGER_SCHEMA_GAP": RuleTemplate(
        "PROOF_LEDGER_SCHEMA_GAP", "HIGH",
        "A ledger called proof lacks machine-verifiable proof identity fields",
        "Require proof_id, evidence family/source hash, verification method, status, timestamp and optional signature/readback fields.",
        "A proof ledger with zero proof IDs, hashes, signatures and statuses must be classified as narrative evidence debt.",
        "The July meta-audit inspected 233 proof records and found none of these machine-verifiable fields.",
    ),

    "RECOVERY_SELF_INGESTION": RuleTemplate(
        "RECOVERY_SELF_INGESTION", "HIGH",
        "A recovery run ingested artifacts produced by prior recovery runs",
        "Exclude registered collector output roots and bind every recovered item to artifact_role and derivation_depth.",
        "A copied artifact with role RECOVERY_SELF_DERIVATIVE or derivation_depth>0 must produce HOLD and cannot count as primary coverage.",
        "The handoff recovery corpus copied prior HANDOFF_CANDIDATES ledgers into the next recovery payload.",
    ),
    "CONTENT_SECRET_SAFETY_FALSE_CLAIM": RuleTemplate(
        "CONTENT_SECRET_SAFETY_FALSE_CLAIM", "CRITICAL",
        "A package claimed no credential values while copied payload bytes contain credential-shaped literals",
        "Separate source-effect receipts from content-secrecy receipts; quarantine secret-bearing payloads and retain fingerprints only.",
        "credential_values_output=false plus a verified secret fingerprint in copied bytes must fail package distribution admission.",
        "CopySafe protects source mutation semantics; it does not prove copied content is secret-free.",
    ),
    "CONTROL_ARTIFACT_COVERAGE_INFLATION": RuleTemplate(
        "CONTROL_ARTIFACT_COVERAGE_INFLATION", "HIGH",
        "Control metadata or recovery derivatives were counted as primary archive coverage",
        "Report physical occurrence, unique hash, primary-source eligible and control/derivative counts separately.",
        "A prior collector ledger or protocol file must not increase primary-source coverage.",
        "Recovery packages can recursively ingest their own ledgers and inflate corpus counts without adding source evidence.",
    ),
    "PROOF_SCOPE_CONFLATION": RuleTemplate(
        "PROOF_SCOPE_CONFLATION", "HIGH",
        "A no-source-effect proof was used as a no-secret-content proof",
        "Issue independent receipts for source effects, package integrity, content secrecy, target readback and authority.",
        "NO_SOURCE_EFFECT_PROOF cannot satisfy NO_SECRET_CONTENT_PROOF unless payload bytes are independently scanned under a declared coverage contract.",
        "One receipt can be valid within its scope while materially false when promoted to a broader claim.",
    ),
    "UNSAFE_ROW_LABEL_MISMATCH": RuleTemplate(
        "UNSAFE_ROW_LABEL_MISMATCH", "MEDIUM",
        "A status field label narrows a broader unsafe/excluded population",
        "Rename the field to excluded_or_unsafe_count and publish reason-class counts.",
        "A field named excluded_pointer_only must not include unsupported scripts, secret-pattern hits or high-risk paths.",
        "Misleading field names create invalid downstream arithmetic and false operator confidence.",
    ),
    "SECRET_SCANNER_COVERAGE_GAP": RuleTemplate(
        "SECRET_SCANNER_COVERAGE_GAP", "CRITICAL",
        "The declared secret scanner missed credential-shaped literals in admitted payload bytes",
        "Expand deterministic scanners, publish pattern and size coverage, and require a second pass over copied payloads before distribution.",
        "A secret fingerprint found after the collector declared the file safe must remain a scanner-coverage defect until repaired and regression-tested.",
        "The collector's assignment regex did not detect password literals embedded in function-call arguments.",
    ),
    "PRIMARY_SECONDARY_CURSOR_CONFLATION": RuleTemplate(
        "PRIMARY_SECONDARY_CURSOR_CONFLATION", "HIGH",
        "Primary Source-001 ranks and legacy analytical step numbers were treated as one cursor",
        "Maintain separate cursor IDs, source hashes, denominators and promotion ceilings for every archive lineage.",
        "A 473-conversation legacy cursor must never be numerically equated to the 536-conversation Source-001 chronology.",
        "The archive contains both a 473-conversation legacy raw export and a later 536-conversation Source-001 export.",
    ),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_event(raw: Mapping[str, Any]) -> dict[str, Any]:
    event = dict(raw)
    required = ["task_id", "step_id", "event_type", "actor"]
    missing = [field for field in required if not str(event.get(field, "")).strip()]
    if missing:
        raise HanriError(f"event missing fields: {','.join(missing)}")
    if event["event_type"] not in EVENT_TYPES:
        raise HanriError(f"unsupported event_type: {event['event_type']}")
    event.setdefault("schema_version", 1)
    event.setdefault("event_id", str(uuid.uuid4()))
    event.setdefault("timestamp", iso_utc())
    parse_iso(str(event["timestamp"]))
    event.setdefault("recursion_depth", 0)
    if not isinstance(event["recursion_depth"], int) or event["recursion_depth"] < 0:
        raise HanriError("recursion_depth must be a non-negative integer")
    event.setdefault("goal", "")
    event.setdefault("human_summary", "")
    event.setdefault("checks", {})
    event.setdefault("evidence_refs", [])
    event.setdefault("payload", {})
    event.setdefault("can_trade", False)
    if event["can_trade"] is not False:
        raise HanriError("can_trade must remain false")
    if not isinstance(event["checks"], dict):
        raise HanriError("checks must be an object")
    if not isinstance(event["evidence_refs"], list):
        raise HanriError("evidence_refs must be an array")
    return event


def validate_decision(raw: Mapping[str, Any]) -> dict[str, Any]:
    decision = dict(raw)
    for field in ["candidate_id", "verdict"]:
        if not str(decision.get(field, "")).strip():
            raise HanriError(f"decision missing field: {field}")
    verdict = str(decision["verdict"]).upper()
    if verdict not in DECISION_VERDICTS:
        raise HanriError(f"unsupported decision verdict: {verdict}")
    decision["verdict"] = verdict
    decision.setdefault("schema_version", 1)
    decision.setdefault("decision_id", str(uuid.uuid4()))
    decision.setdefault("timestamp", iso_utc())
    parse_iso(str(decision["timestamp"]))
    decision.setdefault("operator", "Robert")
    decision.setdefault("comment", "")
    decision.setdefault("can_trade", False)
    if decision["can_trade"] is not False:
        raise HanriError("can_trade must remain false")
    return decision


def bool_check(checks: Mapping[str, Any], name: str) -> bool:
    return checks.get(name) is True


def evaluate_event(event: Mapping[str, Any], max_depth: int) -> tuple[list[str], str | None]:
    checks = event.get("checks", {})
    codes: list[str] = []
    stop_reason: str | None = None

    if any(bool_check(checks, key) for key in (
        "background_claim", "sentience_claim", "intrinsic_memory_claim", "autonomy_claim"
    )):
        codes.append("FALSE_BACKGROUND_OR_INTERIORITY")
    if bool_check(checks, "user_confirmed_completion") and bool_check(checks, "rerun_requested"):
        codes.append("RERUN_AFTER_USER_COMPLETION")
    if str(checks.get("negative_claim", "")).upper() in {"MISSING", "NOT_FOUND"} and not bool_check(checks, "coverage_certificate_present"):
        codes.append("NEGATIVE_CLAIM_WITHOUT_COVERAGE")
    effect_rung = str(checks.get("effect_rung", "NONE")).upper()
    if effect_rung not in EFFECT_RUNGS:
        effect_rung = "NONE"
    if bool_check(checks, "tool_success") and bool_check(checks, "declared_complete") and effect_rung not in {"TARGET_READBACK", "SEMANTIC_EFFECT_VERIFIED"}:
        codes.append("TOOL_EFFECT_CONFUSION")
    if bool_check(checks, "persistent_write") and not bool_check(checks, "git_baseline_verified"):
        codes.append("GIT_BASELINE_BYPASS")
    if bool_check(checks, "simulation_promoted_to_present") or bool_check(checks, "stale_archive_promoted_to_present"):
        codes.append("TEMPORAL_LEAKAGE")
    if bool_check(checks, "accepted_decision_changed_without_supersession"):
        codes.append("AUTHORITY_DRIFT")
    if bool_check(checks, "unknowns_dropped"):
        codes.append("UNKNOWN_LOSS")
    occurrences = checks.get("evidence_occurrences")
    families = checks.get("independent_evidence_families")
    if isinstance(occurrences, int) and isinstance(families, int) and occurrences > families >= 0:
        codes.append("EVIDENCE_DOUBLE_COUNT")
    if (
        bool_check(checks, "external_model_api_used_under_deny")
        or (bool_check(checks, "quota_exhausted") and bool_check(checks, "automatic_retry_attempted"))
        or bool_check(checks, "avoidable_operator_burden")
    ):
        codes.append("RESOURCE_AND_OPERATOR_BURDEN")
    changed_fields = [
        bool_check(checks, "changed_decision"),
        bool_check(checks, "changed_evidence"),
        bool_check(checks, "changed_control"),
        bool_check(checks, "changed_unknown_or_gap"),
    ]
    if event.get("recursion_depth", 0) > 0 and not any(changed_fields):
        codes.append("NO_MATERIAL_DELTA_RECURSION")
        stop_reason = "STOP_NO_MATERIAL_DELTA"
    if int(event.get("recursion_depth", 0)) > max_depth:
        codes.append("RECURSION_DEPTH_EXCEEDED")
        stop_reason = "STOP_RECURSION_DEPTH_EXCEEDED"
    if bool_check(checks, "function_claimed_as_independent_agent") or bool_check(checks, "persona_claimed_authority"):
        codes.append("PERSONA_AGENT_CONFUSION")
    if bool_check(checks, "derivative_archive_promoted") and not bool_check(checks, "primary_evidence_and_freshness_present"):
        codes.append("ARCHIVE_PROMOTION_WITHOUT_PRIMARY_EVIDENCE")
    if (
        bool_check(checks, "human_view_missing")
        or bool_check(checks, "ai_view_missing")
        or bool_check(checks, "human_ai_views_disagree")
    ):
        codes.append("DUAL_NATIVE_MISMATCH")
    if (
        event.get("event_type") == "OPERATOR_FEEDBACK"
        and bool_check(checks, "correction_material")
        and not bool_check(checks, "regression_case_created")
    ):
        codes.append("CORRECTION_NOT_REGRESSION")
    if bool_check(checks, "high_risk_or_irreversible") and not bool_check(checks, "human_approval_present"):
        codes.append("HUMAN_AGENCY_BYPASS")
    if bool_check(checks, "stack_selected_before_equal_tests"):
        codes.append("PREMATURE_STACK_SELECTION")
    if bool_check(checks, "known_p0_open") and bool_check(checks, "feature_or_expansion_work_started"):
        codes.append("P0_PRECEDENCE_BREACH")
    if bool_check(checks, "content_classification_claimed") and not bool_check(checks, "content_signature_verified"):
        codes.append("CONTENT_CLASSIFICATION_WITHOUT_BYTE_INSPECTION")
    if bool_check(checks, "same_name_multiple_hashes") and not bool_check(checks, "version_lineage_recorded"):
        codes.append("SAME_NAME_VERSION_COLLISION")
    if event.get("event_type") == "ARCHIVE_FRONTIER_ADVANCE" and not (
        bool_check(checks, "origin_frontier_processed") and bool_check(checks, "current_frontier_processed")
    ):
        codes.append("BIDIRECTIONAL_FRONTIER_IMBALANCE")
    if bool_check(checks, "metric_claim_present") and not bool_check(checks, "metric_scope_bound"):
        codes.append("METRIC_SCOPE_UNBOUND")
    if bool_check(checks, "same_label_multiple_entities") and not bool_check(checks, "entity_ids_bound"):
        codes.append("ENTITY_IDENTITY_AMBIGUITY")
    if bool_check(checks, "security_debt_deferred") and not bool_check(checks, "security_debt_owner_expiry_trigger_present"):
        codes.append("DEFERRED_SECURITY_DEBT_EXPIRED")
    if bool_check(checks, "coverage_percent_claimed") and not bool_check(checks, "per_file_coverage_ledger_present"):
        codes.append("COVERAGE_CLAIM_WITHOUT_FILE_LEDGER")
    if bool_check(checks, "completeness_claim_present") and not bool_check(checks, "coverage_scope_bound"):
        codes.append("COMPLETENESS_SCOPE_LEAKAGE")
    if bool_check(checks, "historical_liveness_claim") and bool_check(checks, "current_liveness_claimed") and not bool_check(checks, "fresh_target_readback"):
        codes.append("HISTORICAL_LIVENESS_PROMOTION")
    if bool_check(checks, "probe_count_promoted_as_root_cause_count"):
        codes.append("PROBE_ROOT_CAUSE_CONFLATION")
    if bool_check(checks, "filesystem_root_exists") and bool_check(checks, "repository_root_claimed") and not bool_check(checks, "git_toplevel_verified"):
        codes.append("ROOT_REPOSITORY_CONFLATION")
    if event.get("event_type") == "ARCHIVE_CAUSAL_SPINE" and not (
        bool_check(checks, "origin_frontier_processed")
        and bool_check(checks, "pivot_frontier_processed")
        and bool_check(checks, "current_frontier_processed")
    ):
        codes.append("CAUSAL_SPINE_GAP")
    if bool_check(checks, "primary_secondary_cursor_equated"):
        codes.append("PRIMARY_SECONDARY_CURSOR_CONFLATION")
    if bool_check(checks, "arithmetic_partition_inconsistent"):
        codes.append("ARITHMETIC_PARTITION_INCONSISTENCY")
    if bool_check(checks, "count_universes_mixed") or bool_check(checks, "overlap_or_universe_mismatch"):
        codes.append("COUNT_UNIVERSE_CONFLATION")
    if bool_check(checks, "authority_surface_multiplicity"):
        codes.append("AUTHORITY_SURFACE_MULTIPLICITY")
    if bool_check(checks, "spec_claimed_current_implementation") and not bool_check(checks, "implementation_receipt_present"):
        codes.append("SPEC_IMPLEMENTATION_CONFLATION")
    if bool_check(checks, "proof_ledger_claimed") and not bool_check(checks, "proof_identity_fields_present"):
        codes.append("PROOF_LEDGER_SCHEMA_GAP")
    if bool_check(checks, "recovery_self_ingestion"):
        codes.append("RECOVERY_SELF_INGESTION")
    if bool_check(checks, "content_secret_safety_false_claim"):
        codes.append("CONTENT_SECRET_SAFETY_FALSE_CLAIM")
    if bool_check(checks, "control_artifact_coverage_inflation"):
        codes.append("CONTROL_ARTIFACT_COVERAGE_INFLATION")
    if bool_check(checks, "proof_scope_conflation"):
        codes.append("PROOF_SCOPE_CONFLATION")
    if bool_check(checks, "unsafe_row_label_mismatch"):
        codes.append("UNSAFE_ROW_LABEL_MISMATCH")
    if bool_check(checks, "secret_scanner_coverage_gap"):
        codes.append("SECRET_SCANNER_COVERAGE_GAP")
    return sorted(set(codes), key=lambda code: (SEVERITY_ORDER[RULES[code].severity], code)), stop_reason


def make_finding(event: Mapping[str, Any], code: str, event_sha256: str) -> dict[str, Any]:
    rule = RULES[code]
    finding_base = {
        "schema_version": 1,
        "task_id": event["task_id"],
        "step_id": event["step_id"],
        "event_id": event["event_id"],
        "event_sha256": event_sha256,
        "code": code,
        "severity": rule.severity,
        "title": rule.title,
        "rationale": rule.rationale,
        "observed_at": event["timestamp"],
        "evidence_refs": event.get("evidence_refs", []),
        "can_trade": False,
    }
    finding_base["finding_id"] = "F-" + sha256_bytes(canonical_json(finding_base).encode("utf-8"))[:20]
    return finding_base


def make_candidate(event: Mapping[str, Any], finding: Mapping[str, Any]) -> dict[str, Any]:
    rule = RULES[str(finding["code"])]
    candidate = {
        "schema_version": 1,
        "task_id": event["task_id"],
        "finding_id": finding["finding_id"],
        "failure_class": rule.code,
        "severity": rule.severity,
        "proposal": rule.title,
        "minimum_change": rule.minimum_change,
        "rationale": rule.rationale,
        "regression_case": rule.regression,
        "evidence_refs": [
            {"type": "EVENT", "sha256": finding["event_sha256"], "event_id": event["event_id"]},
            *event.get("evidence_refs", []),
        ],
        "rollback": "Do not promote the candidate; preserve the prior accepted version.",
        "authority": "HUMAN_REVIEW_REQUIRED",
        "self_apply": False,
        "recursion_depth": min(int(event.get("recursion_depth", 0)) + 1, 2),
        "created_at": iso_utc(),
        "can_trade": False,
    }
    candidate["candidate_id"] = "C-" + sha256_bytes(canonical_json(candidate).encode("utf-8"))[:20]
    return candidate


def falsify_candidate(candidate: Mapping[str, Any], max_depth: int) -> dict[str, Any]:
    defects: list[str] = []
    if not candidate.get("evidence_refs"):
        defects.append("NO_EVIDENCE_REFERENCE")
    if not str(candidate.get("minimum_change", "")).strip():
        defects.append("NO_MINIMUM_CHANGE")
    if not str(candidate.get("regression_case", "")).strip():
        defects.append("NO_REGRESSION_CASE")
    if candidate.get("self_apply") is not False:
        defects.append("SELF_APPLICATION_NOT_DENIED")
    if candidate.get("authority") != "HUMAN_REVIEW_REQUIRED":
        defects.append("HUMAN_GATE_MISSING")
    if int(candidate.get("recursion_depth", 0)) > max_depth:
        defects.append("RECURSION_DEPTH_EXCEEDED")
    return {
        "candidate_id": candidate["candidate_id"],
        "status": "REVISE" if defects else "READY_FOR_HUMAN_REVIEW",
        "defects": defects,
        "falsified_at": iso_utc(),
        "can_trade": False,
    }


def event_from_r23(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    lanes = payload.get("lanes", [])
    return validate_event({
        "schema_version": 1,
        "event_id": "R23-" + sha256_file(path)[:20],
        "timestamp": payload.get("finished_at", iso_utc()),
        "task_id": "R23_RETURN_SYNC",
        "step_id": str(payload.get("run_id", "UNKNOWN_RUN")),
        "event_type": "STATE_SNAPSHOT",
        "actor": "ControlCenterReturnSyncR23",
        "goal": "Discover, validate and stage existing agent returns without rerun.",
        "human_summary": f"R23 state update: {len(lanes)} lanes observed.",
        "payload": {
            "lane_summary": [
                {
                    "lane_id": row.get("lane_id"),
                    "sync_state": row.get("sync_state"),
                    "candidate_count": row.get("candidate_count"),
                }
                for row in lanes
            ]
        },
        "checks": {
            "changed_control": True,
            "effect_rung": "TARGET_READBACK" if any(row.get("candidate_count", 0) for row in lanes) else "NONE",
        },
        "evidence_refs": [{
            "type": "R23_STATE",
            "path": str(path),
            "sha256": sha256_file(path),
            "evidence_class": "VERIFIED_FACT",
        }],
        "can_trade": False,
    })


def snapshot_event(path: Path, label: str) -> dict[str, Any]:
    return validate_event({
        "event_id": "SNAP-" + sha256_file(path)[:20],
        "timestamp": iso_utc(),
        "task_id": "CONTROL_STATE_SNAPSHOT",
        "step_id": label,
        "event_type": "STATE_SNAPSHOT",
        "actor": "HANRI_R25",
        "goal": "Track exact current-state artifacts without changing them.",
        "human_summary": f"Observed current-state file: {label}.",
        "checks": {"changed_evidence": True},
        "evidence_refs": [{
            "type": "STATE_FILE",
            "path": str(path),
            "sha256": sha256_file(path),
            "evidence_class": "VERIFIED_FACT",
        }],
        "payload": {"size_bytes": path.stat().st_size},
        "can_trade": False,
    })


def load_config(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    if raw.get("external_model_api") != "DENY":
        raise HanriError("external_model_api must be DENY")
    if raw.get("shadow_only") is not True:
        raise HanriError("shadow_only must be true")
    if raw.get("can_trade") is not False:
        raise HanriError("can_trade must be false")
    return raw


def load_hash_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    value = load_json(path)
    return set(value if isinstance(value, list) else [])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def latest_by_id(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result[str(row[key])] = dict(row)
    return result


def render_human_digest(
    run_id: str,
    findings: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    falsifications: Mapping[str, Mapping[str, Any]],
    decisions: Mapping[str, Mapping[str, Any]],
    stop_reasons: Sequence[str],
) -> str:
    candidate_map = {str(item["candidate_id"]): item for item in candidates}
    pending = [
        item for item in candidates
        if decisions.get(str(item["candidate_id"]), {}).get("verdict") not in DECISION_VERDICTS
    ]
    pending.sort(key=lambda item: (SEVERITY_ORDER.get(str(item["severity"]), 9), str(item["candidate_id"])))
    lines = [
        "# Human Decision Digest — HANRI R28",
        "",
        f"Run: `{run_id}`",
        "",
        "## Состояние",
        "",
        f"- Новых findings: **{len(findings)}**",
        f"- Кандидатов на изменение: **{len(candidates)}**",
        f"- Ожидают решения Роберта: **{len(pending)}**",
        f"- Stop signals: **{len(stop_reasons)}**",
        "- Самоприменение изменений: **запрещено**",
        "- `can_trade=false`",
        "",
    ]
    if stop_reasons:
        lines.extend(["## Остановка рекурсии", ""])
        for reason in sorted(set(stop_reasons)):
            lines.append(f"- `{reason}`")
        lines.append("")
    if pending:
        lines.extend(["## Решения", ""])
        for index, candidate in enumerate(pending, start=1):
            cid = str(candidate["candidate_id"])
            falsification = falsifications.get(cid, {})
            lines.extend([
                f"### {index}. {candidate['proposal']}",
                "",
                f"- **Severity:** `{candidate['severity']}`",
                f"- **Почему:** {candidate['rationale']}",
                f"- **Минимальное изменение:** {candidate['minimum_change']}",
                f"- **Проверка:** {candidate['regression_case']}",
                f"- **Adversarial check:** `{falsification.get('status', 'UNKNOWN')}`",
                f"- **Candidate ID:** `{cid}`",
                "- **Выбор:** `ACCEPT | REVISE | HOLD | REJECT`",
                "",
            ])
    else:
        lines.extend(["## Решения", "", "Новых решений не требуется.", ""])
    if decisions:
        lines.extend(["## Уже зафиксированные решения", ""])
        for cid, decision in sorted(decisions.items()):
            if cid in candidate_map:
                lines.append(f"- `{cid}` → **{decision['verdict']}** — {decision.get('comment', '')}")
        lines.append("")
    lines.extend([
        "## Human-native правило",
        "",
        "Человеку показывается смысл, риск, минимальное изменение и способ проверки. "
        "Машинные hashes, полные ledgers и схемы остаются в AI-state, но связаны тем же Candidate ID.",
    ])
    return "\n".join(lines) + "\n"


def copy_latest_outputs(source_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    names = [
        "latest_ai_state.json",
        "latest_human_digest.md",
        "latest_run_receipt.json",
        "latest_health.csv",
        "latest_regression_suite.json",
        "latest_archive_frontier.json",
        "latest_archive_causal_spine.json",
        "latest_archive_scope_certificate.json",
    ]
    for name in names:
        source = source_root / name
        if not source.exists():
            continue
        destination = target_root / name
        temporary = destination.with_name(destination.name + f".tmp-{uuid.uuid4().hex}")
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)


def process_once(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    state_root = expand_path(str(config["state_root"]))
    event_inbox = expand_path(str(config["event_inbox"]))
    decision_inbox = expand_path(str(config["decision_inbox"]))
    human_output_root = expand_path(str(config["human_output_root"])) if config.get("human_output_root") else None
    lock_file = expand_path(str(config.get("lock_file", state_root / "hanri.lock")))
    max_depth = int(config.get("max_recursion_depth", 2))
    if max_depth < 1 or max_depth > 2:
        raise HanriError("max_recursion_depth must be 1 or 2")
    state_root.mkdir(parents=True, exist_ok=True)
    event_inbox.mkdir(parents=True, exist_ok=True)
    decision_inbox.mkdir(parents=True, exist_ok=True)
    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]

    with FileLock(lock_file, int(config.get("lock_stale_seconds", 1800))):
        processed_events_path = state_root / "processed_event_hashes.json"
        processed_decisions_path = state_root / "processed_decision_hashes.json"
        processed_events = load_hash_set(processed_events_path)
        processed_decisions = load_hash_set(processed_decisions_path)
        events: list[dict[str, Any]] = []
        secret_findings: list[dict[str, str]] = []

        for path in sorted(event_inbox.glob("*.json")):
            digest = sha256_file(path)
            if digest in processed_events:
                continue
            raw = sanitize(load_json(path), secret_findings)
            event = validate_event(raw)
            event["input_file"] = str(path)
            event["input_sha256"] = digest
            events.append(event)
            processed_events.add(digest)

        r23_path_value = config.get("r23_state_path")
        if r23_path_value:
            r23_path = expand_path(str(r23_path_value))
            if r23_path.exists():
                digest = sha256_file(r23_path)
                synthetic_key = "R23:" + digest
                if synthetic_key not in processed_events:
                    events.append(event_from_r23(r23_path, load_json(r23_path)))
                    processed_events.add(synthetic_key)

        for index, value in enumerate(config.get("current_state_paths", []), start=1):
            path = expand_path(str(value))
            if not path.exists() or not path.is_file():
                continue
            digest = sha256_file(path)
            synthetic_key = "STATE:" + digest
            if synthetic_key not in processed_events:
                events.append(snapshot_event(path, f"STATE-{index}"))
                processed_events.add(synthetic_key)

        frontier_config = config.get("archive_frontier", {})
        if frontier_config.get("enabled") is True:
            frontier_state_path = state_root / "latest_archive_frontier.json"
            causal_state_path = state_root / "latest_archive_causal_spine.json"
            scope_state_path = state_root / "latest_archive_scope_certificate.json"
            inventory_cache_path = state_root / "archive_inventory_cache.json"
            scan_interval = max(int(frontier_config.get("scan_interval_seconds", 900)), 60)
            reference_state_path = causal_state_path if frontier_config.get("pivot_paths") else frontier_state_path
            scan_due = True
            if reference_state_path.exists():
                previous_frontier = load_json(reference_state_path)
                previous_generated = previous_frontier.get("generated_at")
                if previous_generated:
                    age = (utc_now() - parse_iso(str(previous_generated))).total_seconds()
                    scan_due = age >= scan_interval
            if scan_due:
                origin_paths = [expand_path(str(value)) for value in frontier_config.get("origin_paths", [])]
                current_paths = [expand_path(str(value)) for value in frontier_config.get("current_paths", [])]
                pivot_paths = [expand_path(str(value)) for value in frontier_config.get("pivot_paths", [])]
                file_hashes = {
                    key.split(":", 1)[-1] for key in processed_events
                    if key.startswith("ARCHIVE:")
                }
                inventory_cache = load_json(inventory_cache_path) if inventory_cache_path.exists() else {}
                max_read_bytes = int(frontier_config.get("max_read_bytes", 16 * 1024 * 1024))
                if pivot_paths:
                    spine, next_cache = scan_causal_spine(
                        origin_paths,
                        pivot_paths,
                        current_paths,
                        processed_hashes=file_hashes,
                        max_bytes=max_read_bytes,
                        inventory_cache=inventory_cache,
                        scope_id=str(frontier_config.get("scope_id", "CONTROL_CENTER_ARCHIVE_CAUSAL_SPINE")),
                    )
                    spine["scan_interval_seconds"] = scan_interval
                    atomic_write_json(causal_state_path, spine)
                    atomic_write_json(scope_state_path, spine["coverage_certificate"])
                    atomic_write_json(inventory_cache_path, next_cache)
                    for item in (spine.get("origin"), spine.get("pivot"), spine.get("current")):
                        if item:
                            processed_events.add("ARCHIVE:" + str(item["sha256"]))
                    if spine.get("origin") or spine.get("pivot") or spine.get("current"):
                        events.append(validate_event(causal_spine_event(spine)))
                else:
                    pair, next_cache = scan_frontier_pair(
                        origin_paths,
                        current_paths,
                        processed_hashes=file_hashes,
                        max_bytes=max_read_bytes,
                        inventory_cache=inventory_cache,
                    )
                    pair["scan_interval_seconds"] = scan_interval
                    atomic_write_json(frontier_state_path, pair)
                    atomic_write_json(inventory_cache_path, next_cache)
                    for item in (pair.get("origin"), pair.get("current")):
                        if item:
                            processed_events.add("ARCHIVE:" + str(item["sha256"]))
                    if pair.get("origin") or pair.get("current"):
                        events.append(validate_event(archive_frontier_event(pair)))

        decisions_new: list[dict[str, Any]] = []
        for path in sorted(decision_inbox.glob("*.json")):
            digest = sha256_file(path)
            if digest in processed_decisions:
                continue
            decision = validate_decision(sanitize(load_json(path), secret_findings))
            decision["input_file"] = str(path)
            decision["input_sha256"] = digest
            decisions_new.append(decision)
            processed_decisions.add(digest)

        findings_new: list[dict[str, Any]] = []
        candidates_new: list[dict[str, Any]] = []
        falsifications_new: list[dict[str, Any]] = []
        stop_reasons: list[str] = []
        event_rows: list[dict[str, Any]] = []

        for event in events:
            event = sanitize(event, secret_findings)
            event_sha = sha256_bytes(canonical_json(event).encode("utf-8"))
            event["event_sha256"] = event_sha
            codes, stop_reason = evaluate_event(event, max_depth)
            event["evaluation_codes"] = codes
            if stop_reason:
                stop_reasons.append(stop_reason)
            event_rows.append(event)
            for code in codes:
                finding = make_finding(event, code, event_sha)
                findings_new.append(finding)
                if code in {"NO_MATERIAL_DELTA_RECURSION", "RECURSION_DEPTH_EXCEEDED"}:
                    continue
                candidate = make_candidate(event, finding)
                candidates_new.append(candidate)
                falsifications_new.append(falsify_candidate(candidate, max_depth))

        append_jsonl(state_root / "event_ledger.jsonl", event_rows)
        append_jsonl(state_root / "finding_ledger.jsonl", findings_new)
        append_jsonl(state_root / "candidate_delta_ledger.jsonl", candidates_new)
        append_jsonl(state_root / "candidate_falsification_ledger.jsonl", falsifications_new)
        append_jsonl(state_root / "decision_ledger.jsonl", decisions_new)
        atomic_write_json(processed_events_path, sorted(processed_events))
        atomic_write_json(processed_decisions_path, sorted(processed_decisions))

        all_findings = read_jsonl(state_root / "finding_ledger.jsonl")
        all_candidates = read_jsonl(state_root / "candidate_delta_ledger.jsonl")
        all_falsifications = latest_by_id(read_jsonl(state_root / "candidate_falsification_ledger.jsonl"), "candidate_id")
        all_decisions = latest_by_id(read_jsonl(state_root / "decision_ledger.jsonl"), "candidate_id")

        pending_candidates = [
            candidate for candidate in all_candidates
            if all_decisions.get(str(candidate["candidate_id"]), {}).get("verdict") not in DECISION_VERDICTS
        ]
        ai_state = {
            "schema_version": 1,
            "program_version": VERSION,
            "run_id": run_id,
            "generated_at": iso_utc(),
            "mode": "BOUNDED_RECURSIVE_SHADOW",
            "shadow_only": True,
            "max_recursion_depth": max_depth,
            "new_events": len(event_rows),
            "new_findings": len(findings_new),
            "new_candidates": len(candidates_new),
            "new_decisions": len(decisions_new),
            "total_findings": len(all_findings),
            "total_candidates": len(all_candidates),
            "pending_human_decisions": len(pending_candidates),
            "stop_reasons": sorted(set(stop_reasons)),
            "latest_findings": findings_new,
            "latest_candidates": candidates_new,
            "secret_findings": secret_findings,
            "archive_frontier": load_json(state_root / "latest_archive_frontier.json") if (state_root / "latest_archive_frontier.json").exists() else None,
            "archive_causal_spine": load_json(state_root / "latest_archive_causal_spine.json") if (state_root / "latest_archive_causal_spine.json").exists() else None,
            "archive_scope_certificate": load_json(state_root / "latest_archive_scope_certificate.json") if (state_root / "latest_archive_scope_certificate.json").exists() else None,
            "invariants": {
                "self_application": False,
                "external_model_api_calls": 0,
                "network_calls": 0,
                "source_repository_writes": False,
                "human_approval_required": True,
                "can_trade": False,
            },
        }
        atomic_write_json(state_root / "latest_ai_state.json", ai_state)
        atomic_write_json(state_root / "latest_regression_suite.json", {
            "schema_version": 1,
            "generated_at": ai_state["generated_at"],
            "cases": [
                {"candidate_id": item["candidate_id"], "failure_class": item["failure_class"], "regression_case": item["regression_case"]}
                for item in all_candidates
            ],
            "can_trade": False,
        })
        digest_text = render_human_digest(
            run_id, findings_new, all_candidates, all_falsifications, all_decisions, stop_reasons
        )
        atomic_write_text(state_root / "latest_human_digest.md", digest_text)
        with (state_root / "latest_health.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            writer.writerow(["new_events", len(event_rows)])
            writer.writerow(["new_findings", len(findings_new)])
            writer.writerow(["total_findings", len(all_findings)])
            writer.writerow(["total_candidates", len(all_candidates)])
            writer.writerow(["pending_human_decisions", len(pending_candidates)])
            writer.writerow(["stop_reasons", ";".join(sorted(set(stop_reasons)))])
            writer.writerow(["can_trade", "false"])

        receipt = {
            "schema_version": 1,
            "program_version": VERSION,
            "run_id": run_id,
            "generated_at": ai_state["generated_at"],
            "config_path": str(config_path),
            "config_sha256": sha256_file(config_path),
            "events_processed": len(event_rows),
            "decisions_processed": len(decisions_new),
            "findings_generated": len(findings_new),
            "candidates_generated": len(candidates_new),
            "stop_reasons": sorted(set(stop_reasons)),
            "state_sha256": sha256_file(state_root / "latest_ai_state.json"),
            "human_digest_sha256": sha256_file(state_root / "latest_human_digest.md"),
            "external_model_api_calls": 0,
            "self_application": False,
            "can_trade": False,
        }
        atomic_write_json(state_root / "latest_run_receipt.json", receipt)
        atomic_write_json(state_root / f"run_{run_id}.json", receipt)
        if human_output_root:
            copy_latest_outputs(state_root, human_output_root)
        return receipt


def record_event(config_path: Path, event_file: Path | None, inline_json: str | None) -> dict[str, Any]:
    config = load_config(config_path)
    event_inbox = expand_path(str(config["event_inbox"]))
    event_inbox.mkdir(parents=True, exist_ok=True)
    if bool(event_file) == bool(inline_json):
        raise HanriError("provide exactly one of --event-file or --event-json")
    raw = load_json(event_file) if event_file else json.loads(str(inline_json))
    findings: list[dict[str, str]] = []
    event = validate_event(sanitize(raw, findings))
    filename = f"{event['timestamp'].replace(':', '').replace('-', '')}_{event['event_id']}.json"
    destination = event_inbox / filename
    atomic_write_json(destination, event)
    return {
        "status": "RECORDED",
        "event_id": event["event_id"],
        "path": str(destination),
        "sha256": sha256_file(destination),
        "secret_findings": findings,
        "can_trade": False,
    }


def record_decision(config_path: Path, decision_file: Path | None, inline_json: str | None) -> dict[str, Any]:
    config = load_config(config_path)
    decision_inbox = expand_path(str(config["decision_inbox"]))
    decision_inbox.mkdir(parents=True, exist_ok=True)
    if bool(decision_file) == bool(inline_json):
        raise HanriError("provide exactly one of --decision-file or --decision-json")
    raw = load_json(decision_file) if decision_file else json.loads(str(inline_json))
    findings: list[dict[str, str]] = []
    decision = validate_decision(sanitize(raw, findings))
    filename = f"{decision['timestamp'].replace(':', '').replace('-', '')}_{decision['decision_id']}.json"
    destination = decision_inbox / filename
    atomic_write_json(destination, decision)
    return {
        "status": "RECORDED",
        "decision_id": decision["decision_id"],
        "path": str(destination),
        "sha256": sha256_file(destination),
        "secret_findings": findings,
        "can_trade": False,
    }


def status(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    state_root = expand_path(str(config["state_root"]))
    latest = state_root / "latest_ai_state.json"
    if not latest.exists():
        return {"status": "NOT_INITIALIZED", "state_root": str(state_root), "can_trade": False}
    value = load_json(latest)
    return {
        "status": "OK",
        "run_id": value.get("run_id"),
        "pending_human_decisions": value.get("pending_human_decisions"),
        "stop_reasons": value.get("stop_reasons", []),
        "state_path": str(latest),
        "state_sha256": sha256_file(latest),
        "can_trade": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Human-AI Native bounded recursive improvement supervisor")
    sub = parser.add_subparsers(dest="command", required=True)

    once = sub.add_parser("once", help="Process new events/decisions and write dual-native state")
    once.add_argument("--config", type=Path, required=True)

    watch = sub.add_parser("watch", help="Run bounded processing repeatedly; no network/model calls")
    watch.add_argument("--config", type=Path, required=True)
    watch.add_argument("--watch-seconds", type=int, required=True)

    record = sub.add_parser("record", help="Record one structured task/step event")
    record.add_argument("--config", type=Path, required=True)
    record.add_argument("--event-file", type=Path)
    record.add_argument("--event-json")
    record.add_argument("--process-now", action="store_true")

    decide = sub.add_parser("decide", help="Record Robert's verdict for a candidate")
    decide.add_argument("--config", type=Path, required=True)
    decide.add_argument("--decision-file", type=Path)
    decide.add_argument("--decision-json")
    decide.add_argument("--process-now", action="store_true")

    show = sub.add_parser("status", help="Show current supervisor state")
    show.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "once":
            result = process_once(args.config)
        elif args.command == "watch":
            if args.watch_seconds <= 0:
                raise HanriError("watch-seconds must be positive")
            while True:
                result = process_once(args.config)
                print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, indent=2))
                time.sleep(args.watch_seconds)
        elif args.command == "record":
            result = record_event(args.config, args.event_file, args.event_json)
            if args.process_now:
                result["processing"] = process_once(args.config)
        elif args.command == "decide":
            result = record_decision(args.config, args.decision_file, args.decision_json)
            if args.process_now:
                result["processing"] = process_once(args.config)
        elif args.command == "status":
            result = status(args.config)
        else:
            raise HanriError(f"unknown command: {args.command}")
    except (OSError, ValueError, json.JSONDecodeError, HanriError) as exc:
        print(json.dumps({"status": "ERROR", "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
