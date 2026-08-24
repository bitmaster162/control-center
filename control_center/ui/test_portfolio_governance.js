const assert = require("node:assert/strict");
const portfolio = require("./portfolio_governance.js");

const control = {
  schema: "control_center.current_control_plane_projection.v1",
  projection_kind: "NON_AUTHORITY_PROJECTION",
  observed_at: "2026-08-24T00:00:00+07:00",
  canonical_current: {
    accepted_manifest_sha256: "manifest-sha",
    pointer: { sha256: "pointer-sha" },
    root_hashes: {
      "CURRENT_STATE.json": "current-state-sha",
      "ROLE_INDEX.json": "role-index-sha",
      "ROLE_VIEWS.json": "role-views-sha"
    }
  },
  projects: [
    {
      id: "control-center",
      owner: "CONTROL_CENTER",
      state: "ACTIVE",
      next: "Build portfolio dashboard",
      blocked_by: []
    },
    {
      id: "bitevo-core",
      owner: "FUTURE_RUNTIME_OWNER",
      state: "PLANNED",
      next: "Bind runtime source",
      blocked_by: ["runtime-source-binding"]
    }
  ]
};

const agentControl = {
  schema: "control_center.agent_control_plane.v1",
  projection_kind: "NON_AUTHORITY_PROJECTION",
  observed_at: "2026-08-24T00:00:00+07:00",
  operator_attention: [
    {
      rank: 1,
      project: "Control Center",
      reported_state: "ACTIVE",
      reason: "PORTFOLIO_GOVERNANCE",
      requested_next: "Build dashboard"
    },
    {
      rank: 2,
      project: "Unregistered Project",
      reported_state: "HUMAN_GATE_READY",
      reason: "ROBERT_DECISION",
      requested_next: "Review"
    }
  ],
  invariants: { max_operator_attention: 3 }
};

const policy = {
  schema: "control_center.portfolio_policy.v1",
  policy_kind: "CANDIDATE_NON_AUTHORITY_POLICY",
  policy_version: "R2",
  portfolio: { max_active_lanes: 3 },
  projects: {
    "control-center": {
      policy_state: "CANDIDATE_BOUND",
      definition_of_done: {
        technical_acceptance: ["UI test passes"],
        operational_usability: ["Provider-backed dashboard renders"]
      },
      kill_sunset_criteria: ["STOP when no proof obligation remains"],
      freshness_policy: { source: "provider_freshness_evidence.current.v1.json" }
    }
  },
  safety: { authority_granted: false }
};

const freshness = {
  schema: "control_center.provider_freshness_evidence.v1",
  projection_kind: "NON_AUTHORITY_PROVIDER_READBACK_EVIDENCE",
  observed_at: "2026-08-24T00:05:00+07:00",
  freshness_status: "FRESH_AT_CAPTURE",
  continuous_freshness: false,
  max_age_seconds: 21600,
  stable_roots: {
    "CURRENT_STATE.json": { sha256: "current-state-sha" },
    "ROLE_INDEX.json": { sha256: "role-index-sha" },
    "ROLE_VIEWS.json": { sha256: "role-views-sha" },
    "MANIFEST.json": { sha256: "manifest-sha" },
    "CURRENT_POINTER.json": { sha256: "pointer-sha" }
  },
  readback_result: {
    all_five_exact_at_capture: true,
    pointer_last_by_provider_modified_time: true,
    authority_critical_snapshot_match: true
  },
  safety: { evidence_grants_authority: false }
};

const projection = portfolio.buildPortfolioProjection(control, agentControl, policy, freshness);
assert.equal(projection.schema, "control_center.portfolio_governance_projection.v2");
assert.equal(projection.projection_kind, "NON_AUTHORITY_DERIVED_PROJECTION");
assert.equal(projection.summary.tracked_projects, 2);
assert.equal(projection.summary.blocked_projects, 1);
assert.equal(projection.summary.active_lanes, 2);
assert.equal(projection.summary.max_active_lanes, 3);
assert.equal(projection.summary.unregistered_attention, 1);
assert.equal(projection.summary.policy_bound_projects, 1);
assert.equal(projection.summary.policy_missing_projects, 1);
assert.equal(projection.summary.terminal_criteria_missing, 1);
assert.equal(projection.summary.kill_criteria_missing, 1);
assert.equal(projection.rows[0].active_lane, true);
assert.equal(projection.rows[0].active_lane_rank, 1);
assert.equal(projection.rows[0].policy_bound, true);
assert.ok(projection.rows[0].definition_of_done);
assert.equal(projection.rows[1].policy_bound, false);
assert.equal(projection.rows[1].blocker, "runtime-source-binding");
assert.equal(projection.provider_evidence_binding.status, "EXACT_AT_CAPTURE");
assert.equal(projection.invariants.authority_granted, false);
assert.equal(projection.invariants.auto_fix, false);
assert.equal(projection.invariants.priority_score_invented, false);
assert.equal(projection.invariants.current_freshness_verdict_invented, false);
assert.equal(projection.invariants.active_lane_policy_matches_provider_invariant, true);

const driftedFreshness = {
  ...freshness,
  stable_roots: {
    ...freshness.stable_roots,
    "CURRENT_STATE.json": { sha256: "drifted-sha" }
  }
};
assert.equal(
  portfolio.computeEvidenceBinding(control, driftedFreshness).status,
  "MISMATCH_HOLD"
);

assert.throws(
  () => portfolio.validateInputs({ ...control, projection_kind: "AUTHORITY" }, agentControl, policy, freshness),
  /authority invariant mismatch/
);
assert.throws(
  () => portfolio.validateInputs(control, agentControl, {
    ...policy,
    portfolio: { max_active_lanes: 4 }
  }, freshness),
  /active-lane policy mismatch/
);
assert.throws(
  () => portfolio.validateInputs(control, {
    ...agentControl,
    operator_attention: [...agentControl.operator_attention, {}, {}]
  }, policy, freshness),
  /operator-attention invariant exceeded/
);

console.log("PORTFOLIO_GOVERNANCE_UI_TEST_PASS");
