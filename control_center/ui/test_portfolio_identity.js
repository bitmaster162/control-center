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
const repoCurrent = identity.buildIdentityReconciliation(repoControl, repoAgentControl, repoEvidence);
assert.equal(repoCurrent.classification, "DISTINCT_IDENTIFIER_CANDIDATE");
assert.equal(repoCurrent.decision, "HUMAN_ALIAS_OR_NEW_PROJECT_REGISTRY_GATE");
assert.equal(repoCurrent.reason_code, "REPEATED_PROVIDER_IDENTIFIER_NO_CANONICAL_REGISTRY_MATCH");
assert.equal(repoCurrent.subject_display_name, "MAWorld");
assert.equal(repoCurrent.canonical_candidate, "maworld");
assert.equal(repoCurrent.semantic_alias_status, "NOT_EVIDENCED");
assert.equal(repoCurrent.canonical_registry_match, null);
assert.equal(repoCurrent.provider_observation_count, 3);
assert.deepEqual(repoCurrent.provider_slots.sort(), ["ANTIGRAVITY_WO040", "ANTIGRAVITY_WO041", "CODEX-03"]);
assert.equal(repoCurrent.registry_gate_required, true);
assert.equal(repoCurrent.automatic_registration, false);
assert.equal(repoCurrent.identity_authority_granted, false);
assert.equal(repoCurrent.execution_authority, "NONE");

const control = {
  schema: "control_center.current_control_plane_projection.v1",
  projection_kind: "NON_AUTHORITY_PROJECTION",
  observed_at: "2026-08-12T03:45:00+07:00",
  projects: [
    { id: "control-center" },
    { id: "operator-sprint" },
    { id: "agent-authority-audit" },
    { id: "bitevo-public" },
    { id: "bitevo-core" },
    { id: "hanri" },
    { id: "p0-security" },
    { id: "return-plane-v2" },
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
    },
    {
      slot: "CODEX-03",
      project_hint: "MAWorld",
      reported_state: "RLS_TEST_FAIL",
      work_order: "CODEX03-R49B-MAWORLD-PHYSICAL-RLS-21OF21"
    },
    {
      slot: "CODEX-04",
      project_hint: "Arena",
      reported_state: "HUMAN_GATE_READY",
      work_order: null
    }
  ]
};

const observations = [
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
  },
  {
    slot: "CODEX-03",
    project_hint: "MAWorld",
    reported_state: "RLS_TEST_FAIL",
    work_order: "CODEX03-R49B-MAWORLD-PHYSICAL-RLS-21OF21"
  }
];

const evidence = {
  schema: "control_center.portfolio_project_identity_evidence.v1",
  projection_kind: "CANDIDATE_NON_AUTHORITY_PROJECT_IDENTITY_EVIDENCE",
  subject: { display_name: "MAWorld", canonical_candidate: "maworld" },
  source_binding: {
    control_observed_at: "2026-08-12T03:45:00+07:00",
    agent_control_observed_at: "2026-08-12T03:45:00+07:00"
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

const current = identity.buildIdentityReconciliation(control, agentControl, evidence);
assert.equal(current.classification, "DISTINCT_IDENTIFIER_CANDIDATE");
assert.equal(current.decision, "HUMAN_ALIAS_OR_NEW_PROJECT_REGISTRY_GATE");
assert.equal(current.reason_code, "REPEATED_PROVIDER_IDENTIFIER_NO_CANONICAL_REGISTRY_MATCH");
assert.equal(current.semantic_alias_status, "NOT_EVIDENCED");
assert.equal(current.canonical_registry_match, null);
assert.equal(current.provider_observation_count, 3);
assert.equal(current.registry_gate_required, true);
assert.equal(current.automatic_registration, false);
assert.equal(current.execution_authority, "NONE");

const collisionControl = {
  ...control,
  projects: [...control.projects, { id: "ma-world" }]
};
const collisionEvidence = {
  ...evidence,
  tracked_project_ids_at_capture: collisionControl.projects.map((project) => project.id),
  candidate_result: {
    classification: "MATCH_EXISTING_PROJECT",
    semantic_alias_status: "CANONICAL_IDENTIFIER_MATCH",
    decision: "REVIEW_EXISTING_PROJECT_MATCH",
    registry_gate_required: false
  }
};
const collision = identity.buildIdentityReconciliation(collisionControl, agentControl, collisionEvidence);
assert.equal(collision.classification, "MATCH_EXISTING_PROJECT");
assert.equal(collision.canonical_registry_match, "ma-world");
assert.equal(collision.semantic_alias_status, "CANONICAL_IDENTIFIER_MATCH");
assert.equal(collision.registry_gate_required, false);
assert.equal(collision.automatic_registration, false);

const insufficientEvidence = {
  ...evidence,
  provider_observations: [observations[0]]
};
const insufficient = identity.buildIdentityReconciliation(control, agentControl, insufficientEvidence);
assert.equal(insufficient.classification, "HOLD");
assert.equal(insufficient.reason_code, "IDENTITY_EVIDENCE_INSUFFICIENT");

const mismatchEvidence = {
  ...evidence,
  provider_observations: observations.map((item, index) =>
    index === 1 ? { ...item, work_order: "WRONG-WORK-ORDER" } : item
  )
};
const mismatch = identity.buildIdentityReconciliation(control, agentControl, mismatchEvidence);
assert.equal(mismatch.classification, "HOLD");
assert.equal(mismatch.reason_code, "PROVIDER_IDENTITY_EVIDENCE_MISMATCH");

const staleRegistryEvidence = {
  ...evidence,
  tracked_project_ids_at_capture: evidence.tracked_project_ids_at_capture.slice(0, -1)
};
const staleRegistry = identity.buildIdentityReconciliation(control, agentControl, staleRegistryEvidence);
assert.equal(staleRegistry.classification, "HOLD");
assert.equal(staleRegistry.reason_code, "REGISTRY_EVIDENCE_MISMATCH");

const staleEpochEvidence = {
  ...evidence,
  source_binding: { ...evidence.source_binding, agent_control_observed_at: "2026-08-11T00:00:00+07:00" }
};
const staleEpoch = identity.buildIdentityReconciliation(control, agentControl, staleEpochEvidence);
assert.equal(staleEpoch.classification, "HOLD");
assert.equal(staleEpoch.reason_code, "SOURCE_EPOCH_MISMATCH");

assert.throws(
  () => identity.validateIdentityEvidence({
    ...evidence,
    safety: { ...evidence.safety, automatic_registration: true }
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
