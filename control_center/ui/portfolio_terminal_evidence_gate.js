(function (root) {
  "use strict";

  let terminal = root.PortfolioTerminal;
  if (!terminal && typeof require !== "undefined") terminal = require("./portfolio_terminal.js");
  let registration = root.PortfolioRegistration;
  if (!registration && typeof require !== "undefined") registration = require("./portfolio_registration.js");

  const EXPECTED_APPROVAL = "APPROVE_MAWORLD_OPERATIONAL_PROJECT_REGISTRATION_R1";
  const REQUIRED_EXTRA_OBLIGATIONS = [
    "RLS_21_OF_21_RECEIPT_NOT_EVIDENCED",
    "SUCCESSFUL_POST_RLS_TEARDOWN_RECEIPT_NOT_EVIDENCED"
  ];

  function canonicalProjectId(value) {
    return String(value ?? "").toLowerCase().replaceAll(/[^a-z0-9]+/g, "");
  }

  function validateEnvelope(terminalEvidence) {
    if (!terminalEvidence || terminalEvidence.schema !== "control_center.portfolio_terminal_evidence.v1") throw new Error("terminal evidence schema mismatch");
    if (terminalEvidence.projection_kind !== "CANDIDATE_NON_AUTHORITY_TERMINAL_EVIDENCE") throw new Error("terminal evidence projection kind mismatch");
    const safety = terminalEvidence.safety || {};
    for (const key of ["authority_granted","terminal_authority_granted","sunset_authority_granted","auto_close_authorized","auto_sunset_authorized","auto_repair_authorized","dispatch_authorized","merge_authorized","deploy_authorized","runtime_mutation_authorized"]) {
      if (safety[key] !== false) throw new Error(`terminal evidence authority invariant mismatch:${key}`);
    }
    if (safety.can_trade !== false || safety.capital_permission !== "DENY") throw new Error("terminal evidence trading/capital invariant mismatch");
    return terminalEvidence;
  }

  function validateMAWorldEvidence(terminalEvidence, registrations, policy) {
    validateEnvelope(terminalEvidence);
    registration.validateRegistrations(registrations);
    if (!policy || policy.schema !== "control_center.portfolio_policy.v1" || policy.policy_kind !== "CANDIDATE_NON_AUTHORITY_POLICY" || policy.safety?.authority_granted !== false) throw new Error("terminal evidence policy envelope mismatch");

    const reg = (registrations.registrations || []).find((item) => canonicalProjectId(item.canonical_id) === "maworld");
    if (!reg) throw new Error("terminal evidence MAWorld operational registration missing");
    if (reg.approval?.phrase !== EXPECTED_APPROVAL || reg.result?.current_operational_registration !== "CURRENT_PORTFOLIO_OPERATIONALLY_REGISTERED") throw new Error("terminal evidence operational registration binding mismatch");

    const policyEntry = policy.projects?.maworld;
    if (!policyEntry || policyEntry.policy_state !== "CANDIDATE_BOUND" || policyEntry.policy_binding_class !== "SOURCE_BACKED_NON_AUTHORITY" || policyEntry.strategic_decision !== "KEEP_RESEARCH_INFRA") throw new Error("terminal evidence MAWorld policy binding mismatch");
    if (policyEntry.implementation_ready !== false || policyEntry.repair_authorized !== false || policyEntry.execution_authority !== "NONE") throw new Error("terminal evidence policy authority expansion");

    const evidence = terminalEvidence.projects?.maworld;
    if (!evidence || evidence.evidence_class !== "OPEN_PROOF_OBLIGATION_EVIDENCED") throw new Error("terminal evidence MAWorld open-proof evidence missing");
    if (evidence.proof_obligation_open !== true || evidence.human_sunset_requested !== false || evidence.explicit_terminal_verdict_evidenced !== false) throw new Error("terminal evidence current classification signals mismatch");

    const expectedDod = {
      technical_acceptance: "BLOCKED",
      operational_usability: "NOT_EVIDENCED",
      commercial_validation: "NOT_EVIDENCED",
      production_qualification: "NOT_EVIDENCED"
    };
    if (JSON.stringify(evidence.dod_dimensions || {}) !== JSON.stringify(expectedDod)) throw new Error("terminal evidence DoD state mismatch");

    const obligations = new Set(Array.isArray(evidence.open_proof_obligations) ? evidence.open_proof_obligations : []);
    for (const blocker of reg.operational_metadata?.blocked_by || []) {
      if (!obligations.has(blocker)) throw new Error(`terminal evidence registered blocker missing:${blocker}`);
    }
    for (const obligation of REQUIRED_EXTRA_OBLIGATIONS) {
      if (!obligations.has(obligation)) throw new Error(`terminal evidence proof obligation missing:${obligation}`);
    }

    const binding = evidence.source_binding || {};
    if (binding.operational_registration_approval !== reg.approval.phrase || binding.operational_registration_state !== reg.operational_metadata?.state || binding.operational_registration_result !== reg.result?.current_operational_registration) throw new Error("terminal evidence registration source binding mismatch");
    if (binding.policy_state !== policyEntry.policy_state || binding.policy_binding_class !== policyEntry.policy_binding_class || binding.strategic_decision !== policyEntry.strategic_decision) throw new Error("terminal evidence policy source binding mismatch");
    if (binding.return_registry_drive_file_id !== registrations.base_binding?.return_registry_drive_file_id || binding.return_registry_raw_sha256 !== registrations.base_binding?.return_registry_raw_sha256 || binding.codex03_return_sha256 !== reg.evidence_binding?.codex03_return_sha256 || binding.independent_verifier_slot !== reg.evidence_binding?.independent_verifier_slot) throw new Error("terminal evidence return source binding mismatch");
    if (binding.external_research_decision !== "KEEP_RESEARCH_INFRA" || binding.external_research_implementation_status !== "PARTIAL_INTERNAL_EVIDENCE" || binding.external_research_cutoff !== "2026-08-01") throw new Error("terminal evidence external research ceiling mismatch");

    return evidence;
  }

  function buildTerminalEvidenceGate(control, policy, terminalEvidence, registrations, evidenceBinding, arbiter) {
    const evidence = validateMAWorldEvidence(terminalEvidence, registrations, policy);
    const classification = terminal.buildTerminalClassification(control, policy, terminalEvidence, evidenceBinding, arbiter, registrations);
    if (classification.classification !== "CONTINUE" || classification.reason_code !== "OPEN_PROOF_OR_BLOCKER" || classification.subject_project !== "maworld" || classification.execution_authority !== "NONE") throw new Error("terminal evidence cross-layer classification mismatch");
    return {
      schema: "control_center.portfolio_terminal_evidence_gate.v1",
      projection_kind: "NON_AUTHORITY_TERMINAL_EVIDENCE_GATE",
      subject_project: "maworld",
      classification: "TERMINAL_EVIDENCE_BOUND_OPEN_PROOF",
      decision: "CONTINUE_PROOF_OBLIGATION_NO_EXECUTION_AUTHORITY",
      proof_obligation_open: evidence.proof_obligation_open,
      open_proof_obligations: evidence.open_proof_obligations.slice(),
      terminal_classification: classification,
      implementation_ready: false,
      repair_authorized: false,
      dispatch_authorized: false,
      execution_authority: "NONE"
    };
  }

  const api = { canonicalProjectId, validateEnvelope, validateMAWorldEvidence, buildTerminalEvidenceGate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioTerminalEvidenceGate = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
