const assert = require("node:assert/strict");
const portfolio = require("./portfolio_governance.js");

const control = {
  schema: "control_center.current_control_plane_projection.v1",
  projection_kind: "NON_AUTHORITY_PROJECTION",
  observed_at: "2026-08-24T00:00:00+07:00",
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

const projection = portfolio.buildPortfolioProjection(control, agentControl);
assert.equal(projection.schema, "control_center.portfolio_governance_projection.v1");
assert.equal(projection.projection_kind, "NON_AUTHORITY_DERIVED_PROJECTION");
assert.equal(projection.summary.tracked_projects, 2);
assert.equal(projection.summary.blocked_projects, 1);
assert.equal(projection.summary.active_lanes, 2);
assert.equal(projection.summary.unregistered_attention, 1);
assert.equal(projection.summary.terminal_criteria_missing, 2);
assert.equal(projection.summary.kill_criteria_missing, 2);
assert.equal(projection.rows[0].active_lane, true);
assert.equal(projection.rows[0].active_lane_rank, 1);
assert.equal(projection.rows[1].blocker, "runtime-source-binding");
assert.equal(projection.invariants.authority_granted, false);
assert.equal(projection.invariants.auto_fix, false);
assert.equal(projection.invariants.priority_score_invented, false);

assert.throws(
  () => portfolio.validateInputs({...control, projection_kind: "AUTHORITY"}, agentControl),
  /authority invariant mismatch/
);
assert.throws(
  () => portfolio.validateInputs(control, {
    ...agentControl,
    operator_attention: [...agentControl.operator_attention, {}, {}]
  }),
  /operator-attention invariant exceeded/
);

console.log("PORTFOLIO_GOVERNANCE_UI_TEST_PASS");
