const assert = require("node:assert/strict");
const gate = require("./portfolio_terminal_evidence_gate.js");
const terminalEvidence = require("../data/portfolio_terminal_evidence.candidate.v1.json");
const registrations = require("../data/portfolio_operational_registrations.current.v1.json");
const policy = require("../data/portfolio_policy.candidate.v1.json");
const control = require("../data/current_control_plane.generated.v1.json");

const evidenceBinding = { status: "EXACT_AT_CAPTURE" };
const arbiter = { decision: "RECOMMEND_HUMAN_ATTENTION", recommended_project: "MAWorld" };

const result = gate.buildTerminalEvidenceGate(control, policy, terminalEvidence, registrations, evidenceBinding, arbiter);
assert.equal(result.classification, "TERMINAL_EVIDENCE_BOUND_OPEN_PROOF");
assert.equal(result.decision, "CONTINUE_PROOF_OBLIGATION_NO_EXECUTION_AUTHORITY");
assert.equal(result.subject_project, "maworld");
assert.equal(result.proof_obligation_open, true);
assert.equal(result.terminal_classification.classification, "CONTINUE");
assert.equal(result.terminal_classification.reason_code, "OPEN_PROOF_OR_BLOCKER");
assert.equal(result.terminal_classification.project_registration_source, "HUMAN_OPERATIONAL_REGISTRATION_OVERLAY");
assert.equal(result.implementation_ready, false);
assert.equal(result.repair_authorized, false);
assert.equal(result.dispatch_authorized, false);
assert.equal(result.execution_authority, "NONE");

const closedProof = structuredClone(terminalEvidence);
closedProof.projects.maworld.proof_obligation_open = false;
assert.throws(() => gate.validateMAWorldEvidence(closedProof, registrations, policy), /classification signals mismatch/);

const sunsetAttack = structuredClone(terminalEvidence);
sunsetAttack.projects.maworld.human_sunset_requested = true;
assert.throws(() => gate.validateMAWorldEvidence(sunsetAttack, registrations, policy), /classification signals mismatch/);

const terminalAttack = structuredClone(terminalEvidence);
terminalAttack.projects.maworld.explicit_terminal_verdict_evidenced = true;
terminalAttack.projects.maworld.explicit_terminal_verdict = "PASS";
assert.throws(() => gate.validateMAWorldEvidence(terminalAttack, registrations, policy), /classification signals mismatch/);

const missingRegisteredBlocker = structuredClone(terminalEvidence);
missingRegisteredBlocker.projects.maworld.open_proof_obligations = missingRegisteredBlocker.projects.maworld.open_proof_obligations.filter((x) => x !== "INITDB_FAILED_ROOT_CAUSE_UNRESOLVED");
assert.throws(() => gate.validateMAWorldEvidence(missingRegisteredBlocker, registrations, policy), /registered blocker missing/);

const missingRls = structuredClone(terminalEvidence);
missingRls.projects.maworld.open_proof_obligations = missingRls.projects.maworld.open_proof_obligations.filter((x) => x !== "RLS_21_OF_21_RECEIPT_NOT_EVIDENCED");
assert.throws(() => gate.validateMAWorldEvidence(missingRls, registrations, policy), /proof obligation missing/);

const returnDrift = structuredClone(terminalEvidence);
returnDrift.projects.maworld.source_binding.return_registry_raw_sha256 = "wrong";
assert.throws(() => gate.validateMAWorldEvidence(returnDrift, registrations, policy), /return source binding mismatch/);

const policyDrift = structuredClone(terminalEvidence);
policyDrift.projects.maworld.source_binding.strategic_decision = "BUILD_GENERIC_ORCHESTRATOR";
assert.throws(() => gate.validateMAWorldEvidence(policyDrift, registrations, policy), /policy source binding mismatch/);

const authorityAttack = structuredClone(terminalEvidence);
authorityAttack.safety.auto_repair_authorized = true;
assert.throws(() => gate.validateMAWorldEvidence(authorityAttack, registrations, policy), /authority invariant mismatch:auto_repair_authorized/);

const dodPromotion = structuredClone(terminalEvidence);
dodPromotion.projects.maworld.dod_dimensions.technical_acceptance = "EVIDENCED_PASS";
assert.throws(() => gate.validateMAWorldEvidence(dodPromotion, registrations, policy), /DoD state mismatch/);

console.log("PORTFOLIO_TERMINAL_EVIDENCE_TEST_PASS");
