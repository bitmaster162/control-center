const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const identity = require("./portfolio_identity.js");

function readRepoJson(name) {
  return JSON.parse(fs.readFileSync(path.join(__dirname, "..", "data", name), "utf8"));
}

const repoControl = readRepoJson("current_control_plane.generated.v1.json");
const repoAgentControl = readRepoJson("agent_control_plane.generated.v1.json");
const repoEvidence = readRepoJson("portfolio_project_identity.candidate.v1.json");
const repoAdoptions = readRepoJson("portfolio_identity_adoptions.current.v1.json");

const repoCurrent = identity.buildIdentityReconciliation(
  repoControl,
  repoAgentControl,
  repoEvidence,
  repoAdoptions
);
assert.equal(repoCurrent.schema, "control_center.portfolio_project_identity_reconciliation.v3");
assert.equal(repoCurrent.classification, "CURRENT_PORTFOLIO_IDENTITY_ADOPTED");
assert.equal(repoCurrent.decision, "IDENTITY_ADOPTION_APPLIED_OPERATIONAL_REGISTRATION_NOT_GRANTED");
assert.equal(repoCurrent.reason_code, "EXACT_HUMAN_IDENTITY_ADOPTION_OVERLAY");
assert.equal(repoCurrent.subject_display_name, "MAWorld");
assert.equal(repoCurrent.canonical_candidate, "maworld");
assert.equal(repoCurrent.current_identity_adopted, true);
assert.equal(repoCurrent.operational_project_registered, false);
assert.equal(repoCurrent.registry_gate_required, false);
assert.equal(repoCurrent.operational_registry_gate_required, true);
assert.equal(repoCurrent.approval_phrase, "APPROVE_MAWORLD_CURRENT_PORTFOLIO_IDENTITY_ADOPTION_R1");
assert.equal(repoCurrent.execution_authority, "NONE");

const historicalOnly = identity.buildIdentityReconciliation(
  repoControl,
  repoAgentControl,
  repoEvidence,
  null
);
assert.equal(historicalOnly.classification, "HISTORICAL_PROJECT_IDENTITY_EVIDENCED");
assert.equal(historicalOnly.decision, "HUMAN_CURRENT_REGISTRY_ADOPTION_GATE");
assert.equal(historicalOnly.current_identity_adopted, false);

const control = {
  schema: "control_center.current_control_plane_projection.v1",
  projection_kind: "NON_AUTHORITY_PROJECTION",
  observed_at: "2026-08-12T03:45:00+07:00",
  canonical_current: { generation: "R64" },
  projects: [
    { id: "control-center" },
    { id: "tradingos" }
  ]
};

const agentControl = {
  schema: "control_center.agent_control_plane.v1",
  projection_kind: "NON_AUTHORITY_PROJECTION",
  observed_at: "2026-08-12T03:45:00+07:00",
  slots: [
    {
      slot: "ANTIGRAVITY_WO040",
      project_hint: "MAWorld",
      reported_state: "MAWORLD_TARGET_QUALIFICATION_READY",
      work_order: "ANTIGRAVITY-WO040-MAWORLD-TARGET-QUALIFICATION"
    },
    {
      slot: "ANTIGRAVITY_WO041",
      project_hint: "MAWorld",
      reported_state: "ACCEPTANCE_VERIFIED_FAIL_INITDB",
      work_order: "ANTIGRAVITY-WO041-MAWORLD-POST-RUN-ACCEPTANCE"
    }
  ]
};

const observations = agentControl.slots.map((x) => ({ ...x }));

const evidence = {
  schema: "control_center.portfolio_project_identity_evidence.v1",
  projection_kind: "CANDIDATE_NON_AUTHORITY_PROJECT_IDENTITY_EVIDENCE",
  subject: { display_name: "MAWorld", canonical_candidate: "maworld" },
  source_binding: {
    control_observed_at: control.observed_at,
    agent_control_observed_at: agentControl.observed_at
  },
  minimum_distinct_slot_observations: 2,
  provider_observations: observations,
  tracked_project_ids_at_capture: control.projects.map((project) => project.id),
  candidate_result: {
    classification: "DISTINCT_IDENTIFIER_CANDIDATE",
    semantic_alias_status: "NOT_EVIDENCED",
    decision: "HUMAN_ALIAS_OR_NEW_PROJECT_REGISTRY_GATE",
    registry_gate_required: true
  },
  safety: {
    authority_granted: false,
    identity_authority_granted: false,
    alias_authority_granted: false,
    automatic_registration: false,
    canonical_registry_write_authorized: false,
    dispatch_authorized: false,
    auto_fix_authorized: false,
    merge_authorized: false,
    deploy_authorized: false,
    can_trade: false,
    capital_permission: "DENY",
    self_application: false
  }
};

const distinct = identity.buildIdentityReconciliation(control, agentControl, evidence);
assert.equal(distinct.classification, "DISTINCT_IDENTIFIER_CANDIDATE");
assert.equal(distinct.reason_code, "REPEATED_PROVIDER_IDENTIFIER_NO_CANONICAL_REGISTRY_MATCH");

const historicalEvidence = {
  ...evidence,
  historical_identity_evidence: {
    source_kind: "GOOGLE_DRIVE_BOUNDED_EVIDENCE_DOSSIER",
    drive_file_id: "drive-maworld-dossier",
    historical_generation: "R58",
    historical_evidence_class_claim: "EXACT_LOCAL_R58_ROW",
    historical_record: { id: "maworld", name: "MAWorld", owner: "CODEX-03" },
    primary_registry_locator: {
      name: "R58_CANONICAL_PROJECT_REGISTRY.json",
      bytes_embedded_in_dossier: false
    },
    currentity_ceiling: "HISTORICAL_R58_IDENTITY_ONLY_NOT_CURRENT_R64_AUTHORITY",
    semantic_identity_supported: true,
    current_registry_adoption_supported: false
  }
};

const adoption = {
  schema: "control_center.portfolio_identity_adoptions.v1",
  projection_kind: "HUMAN_APPROVED_NON_EXECUTION_IDENTITY_OVERLAY",
  base_binding: {
    control_observed_at: control.observed_at,
    canonical_generation: "R64"
  },
  adoptions: [{
    canonical_id: "maworld",
    display_name: "MAWorld",
    identity_source: {
      historical_generation: "R58",
      historical_evidence_class: "EXACT_LOCAL_R58_ROW",
      drive_file_id: "drive-maworld-dossier"
    },
    approval: {
      phrase: "APPROVE_MAWORLD_CURRENT_PORTFOLIO_IDENTITY_ADOPTION_R1",
      approved_at: "2026-08-24T08:09:00+07:00",
      scope: "CURRENT_PORTFOLIO_IDENTITY_ONLY"
    },
    result: {
      current_identity_state: "CURRENT_PORTFOLIO_IDENTITY_ADOPTED",
      operational_project_registration: "NOT_GRANTED",
      current_owner_authority: "NOT_GRANTED",
      current_state_authority: "NOT_GRANTED",
      policy_binding_authority: "NOT_GRANTED"
    }
  }],
  safety: {
    authority_granted: false,
    operational_registration_authorized: false,
    owner_authority_granted: false,
    state_authority_granted: false,
    policy_authority_granted: false,
    dispatch_authorized: false,
    auto_fix_authorized: false,
    merge_authorized: false,
    deploy_authorized: false,
    runtime_mutation_authorized: false,
    can_trade: false,
    capital_permission: "DENY",
    self_application: false
  }
};

const adopted = identity.buildIdentityReconciliation(control, agentControl, historicalEvidence, adoption);
assert.equal(adopted.classification, "CURRENT_PORTFOLIO_IDENTITY_ADOPTED");
assert.equal(adopted.current_identity_adopted, true);
assert.equal(adopted.operational_project_registered, false);

const collisionControl = {
  ...control,
  projects: [...control.projects, { id: "ma-world" }]
};
const collisionEvidence = {
  ...historicalEvidence,
  tracked_project_ids_at_capture: collisionControl.projects.map((project) => project.id)
};
const collision = identity.buildIdentityReconciliation(collisionControl, agentControl, collisionEvidence);
assert.equal(collision.classification, "MATCH_EXISTING_PROJECT");
assert.equal(collision.canonical_registry_match, "ma-world");
assert.equal(collision.operational_project_registered, true);
assert.equal(collision.operational_registry_gate_required, false);

const insufficient = identity.buildIdentityReconciliation(
  control,
  agentControl,
  { ...evidence, provider_observations: [observations[0]] }
);
assert.equal(insufficient.classification, "HOLD");
assert.equal(insufficient.reason_code, "IDENTITY_EVIDENCE_INSUFFICIENT");

const mismatchEvidence = {
  ...evidence,
  provider_observations: observations.map((item, index) =>
    index === 1 ? { ...item, work_order: "WRONG-WORK-ORDER" } : item
  )
};
const mismatch = identity.buildIdentityReconciliation(control, agentControl, mismatchEvidence);
assert.equal(mismatch.reason_code, "PROVIDER_IDENTITY_EVIDENCE_MISMATCH");

const staleRegistryEvidence = {
  ...evidence,
  tracked_project_ids_at_capture: ["control-center"]
};
const staleRegistry = identity.buildIdentityReconciliation(control, agentControl, staleRegistryEvidence);
assert.equal(staleRegistry.reason_code, "REGISTRY_EVIDENCE_MISMATCH");

const staleEpochEvidence = {
  ...evidence,
  source_binding: { ...evidence.source_binding, agent_control_observed_at: "2026-08-11T00:00:00+07:00" }
};
const staleEpoch = identity.buildIdentityReconciliation(control, agentControl, staleEpochEvidence);
assert.equal(staleEpoch.reason_code, "SOURCE_EPOCH_MISMATCH");

const brokenHistorical = {
  ...historicalEvidence,
  historical_identity_evidence: {
    ...historicalEvidence.historical_identity_evidence,
    current_registry_adoption_supported: true
  }
};
const brokenHistoricalResult = identity.buildIdentityReconciliation(control, agentControl, brokenHistorical);
assert.equal(brokenHistoricalResult.reason_code, "HISTORICAL_IDENTITY_EVIDENCE_INVALID");

const wrongBinding = {
  ...adoption,
  base_binding: { ...adoption.base_binding, control_observed_at: "2026-08-11T00:00:00+07:00" }
};
const wrongBindingResult = identity.buildIdentityReconciliation(control, agentControl, historicalEvidence, wrongBinding);
assert.equal(wrongBindingResult.reason_code, "CURRENT_IDENTITY_ADOPTION_BINDING_MISMATCH");

assert.throws(
  () => identity.validateIdentityAdoptions({
    ...adoption,
    adoptions: adoption.adoptions.map((item) => ({
      ...item,
      approval: { ...item.approval, phrase: "WRONG" }
    }))
  }),
  /approval phrase mismatch/
);

assert.throws(
  () => identity.validateIdentityAdoptions({
    ...adoption,
    safety: { ...adoption.safety, operational_registration_authorized: true }
  }),
  /authority invariant mismatch/
);

assert.throws(
  () => identity.validateIdentityEvidence({
    ...evidence,
    safety: { ...evidence.safety, identity_authority_granted: true }
  }),
  /authority invariant mismatch/
);

assert.throws(
  () => identity.validateIdentityEvidence({
    ...evidence,
    safety: { ...evidence.safety, can_trade: true }
  }),
  /trading\/capital invariant mismatch/
);

console.log("PORTFOLIO_IDENTITY_TEST_PASS");
