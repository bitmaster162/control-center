const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const registration = require("./portfolio_registration.js");
const terminal = require("./portfolio_terminal.js");

const control = {schema:"control_center.current_control_plane_projection.v1",projection_kind:"NON_AUTHORITY_PROJECTION",observed_at:"2026-08-12T03:45:00+07:00",canonical_current:{generation:"R64"},projects:[{id:"control-center"}]};
const agentControl = {schema:"control_center.agent_control_plane.v1",projection_kind:"NON_AUTHORITY_PROJECTION",observed_at:"2026-08-12T03:45:00+07:00",source_provenance:{return_registry:{drive_file_id:"1BXdqWzA74SvkgcygO_ktO_2uolqFshWm",raw_sha256:"ea0ff88fce2d02f664087ea2697e71688ad95cb6deb65e22df73af2081dfb03f",provider_modified_time:"2026-07-29T16:30:55.472Z",generation_label:"R50_AUDIT"}},slots:[{slot:"CODEX-03",project_hint:"MAWorld",reported_state:"RLS_TEST_FAIL",work_order:"CODEX03-R49B-MAWORLD-PHYSICAL-RLS-21OF21",reported_next:"CAPTURE_INITDB_STDOUT_STDERR_AND_FIX_ONE_ROOT_CAUSE",dispatch_authorized:false},{slot:"ANTIGRAVITY_WO041",project_hint:"MAWorld",reported_state:"ACCEPTANCE_VERIFIED_FAIL_INITDB",work_order:"ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE",reported_next:"MAWORLD_INITDB_DIAGNOSTIC_REPAIR",dispatch_authorized:false}]};
const adoptions = {schema:"control_center.portfolio_identity_adoptions.v1",adoptions:[{canonical_id:"maworld",approval:{phrase:"APPROVE_MAWORLD_CURRENT_PORTFOLIO_IDENTITY_ADOPTION_R1",scope:"CURRENT_PORTFOLIO_IDENTITY_ONLY"},result:{current_identity_state:"CURRENT_PORTFOLIO_IDENTITY_ADOPTED",operational_project_registration:"NOT_GRANTED"}}]};
const evidence = require("../data/portfolio_operational_registration_evidence.candidate.v1.json");
const registrations = require("../data/portfolio_operational_registrations.current.v1.json");

const ready = registration.buildOperationalRegistrationGate(control,agentControl,adoptions,evidence);
assert.equal(ready.classification,"READY_FOR_HUMAN_OPERATIONAL_REGISTRATION");
assert.equal(ready.decision,"HUMAN_OPERATIONAL_REGISTRATION_GATE_READY");
assert.equal(ready.subject_project,"maworld");
assert.equal(ready.owner_candidate,"CODEX-03");
assert.equal(ready.owner_authority_granted,false);
assert.equal(ready.proposed_state,"FAILURE_DIAGNOSTIC_REQUIRED");
assert.deepEqual(ready.proposed_blockers,["INITDB_FAILED_ROOT_CAUSE_UNRESOLVED","FRESH_GIT_BASELINE_READBACK_REQUIRED_BEFORE_IMPLEMENTATION"]);
assert.equal(ready.implementation_ready,false);
assert.equal(ready.repair_authorized,false);
assert.equal(ready.operational_registration_authorized,false);
assert.equal(ready.execution_authority,"NONE");
assert.equal(ready.proposed_human_approval,"APPROVE_MAWORLD_OPERATIONAL_PROJECT_REGISTRATION_R1");

const applied = registration.buildOperationalRegistrationGate(control,agentControl,adoptions,evidence,registrations);
assert.equal(applied.classification,"CURRENT_OPERATIONAL_REGISTRATION_APPLIED");
assert.equal(applied.decision,"OPERATIONAL_REGISTRATION_APPLIED_NO_DOWNSTREAM_AUTHORITY");
assert.equal(applied.operational_registration_applied,true);
assert.equal(applied.human_gate_required,false);
assert.equal(applied.approval_phrase,"APPROVE_MAWORLD_OPERATIONAL_PROJECT_REGISTRATION_R1");
assert.equal(applied.owner_authority_granted,false);
assert.equal(applied.implementation_ready,false);
assert.equal(applied.repair_authorized,false);
assert.equal(applied.execution_authority,"NONE");

const noAdoption = registration.buildOperationalRegistrationGate(control,agentControl,{schema:adoptions.schema,adoptions:[]},evidence); assert.equal(noAdoption.reason_code,"CURRENT_IDENTITY_ADOPTION_MISSING");
const wrongReturn = structuredClone(evidence); wrongReturn.current_return_registry.raw_sha256="wrong"; assert.equal(registration.buildOperationalRegistrationGate(control,agentControl,adoptions,wrongReturn).reason_code,"RETURN_REGISTRY_BINDING_MISMATCH");
const wrongIndependentHash = structuredClone(evidence); wrongIndependentHash.operational_observations[1].verified_return_sha256="different"; assert.equal(registration.buildOperationalRegistrationGate(control,agentControl,adoptions,wrongIndependentHash).reason_code,"INDEPENDENT_RETURN_BINDING_MISMATCH");
const staleGitGateRemoved = structuredClone(evidence); staleGitGateRemoved.repository_identity.fresh_readback_required_before_implementation=false; assert.equal(registration.buildOperationalRegistrationGate(control,agentControl,adoptions,staleGitGateRemoved).reason_code,"FRESH_GIT_BASELINE_GATE_MISSING");
const authorityAttack=structuredClone(evidence); authorityAttack.safety.repair_authorized=true; assert.throws(()=>registration.buildOperationalRegistrationGate(control,agentControl,adoptions,authorityAttack),/authority invariant mismatch:repair_authorized/);
const duplicateControl=structuredClone(control); duplicateControl.projects.push({id:"ma-world"}); assert.equal(registration.buildOperationalRegistrationGate(duplicateControl,agentControl,adoptions,evidence,registrations).reason_code,"PROJECT_ALREADY_OPERATIONALLY_REGISTERED");
const wrongApproval=structuredClone(registrations); wrongApproval.registrations[0].approval.phrase="WRONG"; assert.throws(()=>registration.buildOperationalRegistrationGate(control,agentControl,adoptions,evidence,wrongApproval),/approval mismatch/);
const ownerPromotion=structuredClone(registrations); ownerPromotion.registrations[0].operational_metadata.owner_authority_granted=true; assert.throws(()=>registration.buildOperationalRegistrationGate(control,agentControl,adoptions,evidence,ownerPromotion),/metadata authority mismatch/);
const repairPromotion=structuredClone(registrations); repairPromotion.safety.repair_authorized=true; assert.throws(()=>registration.buildOperationalRegistrationGate(control,agentControl,adoptions,evidence,repairPromotion),/downstream authority mismatch:repair_authorized/);
const bindingAttack=structuredClone(registrations); bindingAttack.base_binding.return_registry_raw_sha256="wrong"; assert.equal(registration.buildOperationalRegistrationGate(control,agentControl,adoptions,evidence,bindingAttack).reason_code,"APPLIED_REGISTRATION_BINDING_MISMATCH");

const policy={portfolio:{terminal_engine:{mode:"EXPLICIT_SIGNALS_ONLY",subject_source:"portfolio_arbiter.recommended_project",evidence_source:"portfolio_terminal_evidence.candidate.v1.json",provider_evidence_gate:"EXACT_AT_CAPTURE",allowed_classifications:["CONTINUE","HOLD","TERMINAL_CANDIDATE","SUNSET_CANDIDATE"],required_dod_dimensions:["technical_acceptance","operational_usability","commercial_validation","production_qualification"],terminal_pass_value:"EVIDENCED_PASS",infer_from_free_text:false,infer_from_project_state:false,auto_close:false,auto_sunset:false,auto_repair:false,execution_authority:"NONE"}},projects:{}};
const terminalEvidence={schema:"control_center.portfolio_terminal_evidence.v1",projection_kind:"CANDIDATE_NON_AUTHORITY_TERMINAL_EVIDENCE",projects:{},safety:{authority_granted:false,terminal_authority_granted:false,sunset_authority_granted:false}};
const arbiter={decision:"RECOMMEND_HUMAN_ATTENTION",recommended_project:"MAWorld"};
const withoutOverlay=terminal.buildTerminalClassification(control,policy,terminalEvidence,{status:"EXACT_AT_CAPTURE"},arbiter); assert.equal(withoutOverlay.reason_code,"UNREGISTERED_PROJECT");
const withOverlay=terminal.buildTerminalClassification(control,policy,terminalEvidence,{status:"EXACT_AT_CAPTURE"},arbiter,registrations);
assert.equal(withOverlay.reason_code,"POLICY_NOT_BOUND");
assert.equal(withOverlay.subject_project,"maworld");
assert.equal(withOverlay.project_registration_source,"HUMAN_OPERATIONAL_REGISTRATION_OVERLAY");
assert.equal(withOverlay.execution_authority,"NONE");

const repoRoot=path.resolve(__dirname,"..","..");
const files={control:path.join(repoRoot,"control_center","data","current_control_plane.generated.v1.json"),agent:path.join(repoRoot,"control_center","data","agent_control_plane.generated.v1.json"),adoption:path.join(repoRoot,"control_center","data","portfolio_identity_adoptions.current.v1.json"),evidence:path.join(repoRoot,"control_center","data","portfolio_operational_registration_evidence.candidate.v1.json"),registrations:path.join(repoRoot,"control_center","data","portfolio_operational_registrations.current.v1.json")};
if(Object.values(files).every(fs.existsSync)){
  const real=registration.buildOperationalRegistrationGate(JSON.parse(fs.readFileSync(files.control,"utf8")),JSON.parse(fs.readFileSync(files.agent,"utf8")),JSON.parse(fs.readFileSync(files.adoption,"utf8")),JSON.parse(fs.readFileSync(files.evidence,"utf8")),JSON.parse(fs.readFileSync(files.registrations,"utf8")));
  assert.equal(real.classification,"CURRENT_OPERATIONAL_REGISTRATION_APPLIED");
  assert.equal(real.owner_candidate,"CODEX-03");
  assert.equal(real.source_baseline_fresh_for_implementation,false);
  assert.equal(real.implementation_ready,false);
}
console.log("PORTFOLIO_REGISTRATION_APPLY_TEST_PASS");
