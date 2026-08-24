const assert = require("node:assert/strict");
const binding = require("./portfolio_policy_binding.js");
const governance = require("./portfolio_governance.js");
const terminal = require("./portfolio_terminal.js");
const policy = require("../data/portfolio_policy.candidate.v1.json");
const registrations = require("../data/portfolio_operational_registrations.current.v1.json");
const evidence = require("../data/portfolio_policy_binding_evidence.maworld.candidate.v1.json");
const control = require("../data/current_control_plane.generated.v1.json");
const agentControl = require("../data/agent_control_plane.generated.v1.json");
const freshness = require("../data/provider_freshness_evidence.current.v1.json");
const terminalEvidence = require("../data/portfolio_terminal_evidence.candidate.v1.json");

const bound = binding.buildPolicyBinding(policy, registrations, evidence);
assert.equal(bound.classification, "CANDIDATE_POLICY_BOUND");
assert.equal(bound.decision, "MAWORLD_POLICY_BINDING_PRESENT_NON_AUTHORITY");
assert.equal(bound.subject_project, "maworld");
assert.equal(bound.policy_state, "CANDIDATE_BOUND");
assert.equal(bound.portfolio_role, "INTERNAL_RESEARCH_INFRA");
assert.equal(bound.strategic_decision, "KEEP_RESEARCH_INFRA");
assert.equal(bound.operational_registration_bound, true);
assert.equal(bound.policy_authority_granted, false);
assert.equal(bound.implementation_ready, false);
assert.equal(bound.repair_authorized, false);
assert.equal(bound.execution_authority, "NONE");
assert.equal(bound.expected_terminal_reason_after_binding, "TERMINAL_EVIDENCE_MISSING");

const missingEntry = structuredClone(policy);
delete missingEntry.projects.maworld;
assert.equal(binding.buildPolicyBinding(missingEntry, registrations, evidence).reason_code, "POLICY_ENTRY_MISSING");

const policyAuthorityAttack = structuredClone(policy);
policyAuthorityAttack.safety.authority_granted = true;
assert.throws(() => binding.buildPolicyBinding(policyAuthorityAttack, registrations, evidence), /policy authority invariant mismatch/);

const repairAttack = structuredClone(policy);
repairAttack.projects.maworld.repair_authorized = true;
assert.equal(binding.buildPolicyBinding(repairAttack, registrations, evidence).reason_code, "POLICY_ENTRY_BOUNDARY_MISMATCH");

const registrationAttack = structuredClone(registrations);
registrationAttack.registrations[0].operational_metadata.owner_authority_granted = true;
assert.equal(binding.buildPolicyBinding(policy, registrationAttack, evidence).reason_code, "OPERATIONAL_REGISTRATION_BINDING_MISMATCH");

const provenanceAttack = structuredClone(evidence);
provenanceAttack.source_evidence.current_return_registry.raw_sha256 = "wrong";
assert.equal(binding.buildPolicyBinding(policy, registrations, provenanceAttack).reason_code, "RETURN_REGISTRY_PROVENANCE_MISMATCH");

const strategicAttack = structuredClone(evidence);
strategicAttack.source_evidence.deep_research_decision.decision = "MERGE";
assert.equal(binding.buildPolicyBinding(policy, registrations, strategicAttack).reason_code, "STRATEGIC_SOURCE_CONTRACT_MISMATCH");

const freshnessAttack = structuredClone(policy);
freshnessAttack.projects.maworld.freshness_policy.code_baseline_fresh_readback_required_before_implementation = false;
assert.equal(binding.buildPolicyBinding(freshnessAttack, registrations, evidence).reason_code, "FRESHNESS_POLICY_MISMATCH");

const evidenceBinding = governance.computeEvidenceBinding(control, freshness);
assert.equal(evidenceBinding.status, "EXACT_AT_CAPTURE");
const arbiter = governance.buildArbiterRecommendation(control, agentControl, policy, evidenceBinding);
assert.equal(arbiter.decision, "RECOMMEND_HUMAN_ATTENTION");
assert.equal(arbiter.recommended_project, "MAWorld");
const terminalResult = terminal.buildTerminalClassification(control, policy, terminalEvidence, evidenceBinding, arbiter, registrations);
assert.equal(terminalResult.subject_project, "maworld");
assert.equal(terminalResult.project_registration_source, "HUMAN_OPERATIONAL_REGISTRATION_OVERLAY");
assert.equal(terminalResult.classification, "HOLD");
assert.equal(terminalResult.reason_code, "TERMINAL_EVIDENCE_MISSING");
assert.equal(terminalResult.execution_authority, "NONE");

console.log("PORTFOLIO_POLICY_BINDING_TEST_PASS");
