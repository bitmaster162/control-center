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
  slots: [
    {
      slot: "ANTIGRAVITY_WO041",
      project_hint: "MAWorld",
      dispatch_authorized: false,
      do_not_touch: false
    },
    {
      slot: "CC-PORTFOLIO",
      project_hint: "Control Center",
      dispatch_authorized: false,
      do_not_touch: false
    }
  ],
  operator_attention: [
    {
      rank: 1,
      slot: "ANTIGRAVITY_WO041",
      project: "MAWorld",
      reported_state: "ACCEPTANCE_VERIFIED_FAIL_INITDB",
      reason: "FAILURE_DIAGNOSTIC",
      requested_next: "MAWORLD_INITDB_DIAGNOSTIC_REPAIR",
      human_gate: "EXPLICIT_BOUNDED_HUMAN_OR_OWNER_GATE",
      auto_dispatch: false
    },
    {
      rank: 2,
      slot: "CC-PORTFOLIO",
      project: "Control Center",
      reported_state: "ACTIVE",
      reason: "PORTFOLIO_GOVERNANCE",
      requested_next: "BUILD_NEXT_BOUNDED_SLICE",
      human_gate: "EXPLICIT_BOUNDED_HUMAN_OR_OWNER_GATE",
      auto_dispatch: false
    }
  ],
  invariants: { max_operator_attention: 3 }
};

const policy = {
  schema: "control_center.portfolio_policy.v1",
  policy_kind: "CANDIDATE_NON_AUTHORITY_POLICY",
  policy_version: "R3",
  portfolio: {
    max_active_lanes: 3,
    terminal_verdicts: ["PASS", "REJECT", "BLOCKED_EXTERNAL", "HOLD", "SUNSET"],
    arbiter: {
      mode: "PRESERVE_PROVIDER_OPERATOR_ATTENTION_ORDER",
      ordering_source: "agent_control_plane.generated.v1.json#operator_attention.rank",
      rescore: false,
      weighted_score: false,
      evidence_gate: "EXACT_AT_CAPTURE",
      ambiguous_rank_action: "HOLD_AMBIGUOUS_RANK",
      no_eligible_action: "HOLD_NO_ELIGIBLE_ATTENTION",
      eligibility: {
        exclude_do_not_touch: true,
        require_auto_dispatch_false: true,
        require_slot_dispatch_authorized_false: true,
        require_named_requested_next: true
      },
      execution_authority: "NONE"
    }
  },
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
assert.equal(projection.schema, "control_center.portfolio_governance_projection.v3");
assert.equal(projection.projection_kind, "NON_AUTHORITY_DERIVED_PROJECTION");
assert.equal(projection.summary.tracked_projects, 2);
assert.equal(projection.summary.blocked_projects, 1);
assert.equal(projection.summary.active_lanes, 2);
assert.equal(projection.summary.max_active_lanes, 3);
assert.equal(projection.summary.unregistered_attention, 1);
assert.equal(projection.summary.policy_bound_projects, 1);
assert.equal(projection.summary.policy_missing_projects, 1);
assert.equal(projection.rows[0].policy_bound, true);
assert.equal(projection.rows[1].policy_bound, false);
assert.equal(projection.provider_evidence_binding.status, "EXACT_AT_CAPTURE");
assert.equal(projection.arbiter.decision, "RECOMMEND_HUMAN_ATTENTION");
assert.equal(projection.arbiter.recommended_project, "MAWorld");
assert.equal(projection.arbiter.source_rank, 1);
assert.equal(projection.arbiter.registered_project, false);
assert.equal(projection.arbiter.registry_status, "UNREGISTERED_PROVIDER_ATTENTION");
assert.equal(projection.arbiter.requested_next, "MAWORLD_INITDB_DIAGNOSTIC_REPAIR");
assert.equal(projection.arbiter.rescore_performed, false);
assert.equal(projection.arbiter.weighted_score_used, false);
assert.equal(projection.arbiter.execution_authority, "NONE");
assert.equal(projection.invariants.authority_granted, false);
assert.equal(projection.invariants.auto_fix, false);
assert.equal(projection.invariants.priority_score_invented, false);
assert.equal(projection.invariants.current_freshness_verdict_invented, false);
assert.equal(projection.invariants.active_lane_policy_matches_provider_invariant, true);
assert.equal(projection.invariants.arbiter_rescore_performed, false);
assert.equal(projection.invariants.arbiter_execution_authority, "NONE");

const driftedFreshness = {
  ...freshness,
  stable_roots: {
    ...freshness.stable_roots,
    "CURRENT_STATE.json": { sha256: "drifted-sha" }
  }
};
const driftedProjection = portfolio.buildPortfolioProjection(control, agentControl, policy, driftedFreshness);
assert.equal(driftedProjection.provider_evidence_binding.status, "MISMATCH_HOLD");
assert.equal(driftedProjection.arbiter.decision, "HOLD_EVIDENCE_NOT_EXACT");
assert.equal(driftedProjection.arbiter.recommended_project, null);

const duplicateRank = {
  ...agentControl,
  operator_attention: [
    agentControl.operator_attention[0],
    { ...agentControl.operator_attention[1], rank: 1 }
  ]
};
const duplicateProjection = portfolio.buildPortfolioProjection(control, duplicateRank, policy, freshness);
assert.equal(duplicateProjection.arbiter.decision, "HOLD_AMBIGUOUS_RANK");
assert.equal(duplicateProjection.arbiter.recommended_project, null);

const topDoNotTouch = {
  ...agentControl,
  slots: agentControl.slots.map((slot) =>
    slot.slot === "ANTIGRAVITY_WO041" ? { ...slot, do_not_touch: true } : slot
  )
};
const skippedProjection = portfolio.buildPortfolioProjection(control, topDoNotTouch, policy, freshness);
assert.equal(skippedProjection.arbiter.decision, "RECOMMEND_HUMAN_ATTENTION");
assert.equal(skippedProjection.arbiter.recommended_project, "Control Center");
assert.equal(skippedProjection.arbiter.source_rank, 2);
assert.equal(skippedProjection.arbiter.considered[0].eligible, false);
assert.deepEqual(skippedProjection.arbiter.considered[0].rejection_reasons, ["do_not_touch"]);

assert.throws(
  () => portfolio.validateInputs({ ...control, projection_kind: "AUTHORITY" }, agentControl, policy, freshness),
  /authority invariant mismatch/
);
assert.throws(
  () => portfolio.validateInputs(control, agentControl, {
    ...policy,
    portfolio: { ...policy.portfolio, max_active_lanes: 4 }
  }, freshness),
  /active-lane policy mismatch/
);
assert.throws(
  () => portfolio.validateInputs(control, {
    ...agentControl,
    operator_attention: [...agentControl.operator_attention, { rank: 3 }, { rank: 4 }]
  }, policy, freshness),
  /operator-attention invariant exceeded/
);
assert.throws(
  () => portfolio.validateInputs(control, agentControl, {
    ...policy,
    portfolio: {
      ...policy.portfolio,
      arbiter: { ...policy.portfolio.arbiter, rescore: true }
    }
  }, freshness),
  /authority or scoring invariant mismatch/
);

console.log("PORTFOLIO_GOVERNANCE_UI_TEST_PASS");
