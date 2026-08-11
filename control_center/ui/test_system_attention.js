const assert = require("node:assert/strict");
const bridge = require("./system_attention.js");

const neutral = {
  schema: "control_center.provider_system_attention.v1",
  projection_kind: "NON_AUTHORITY_OPERATOR_ATTENTION_PROJECTION",
  source_status_verdict: "NO_HOLD_DIAGNOSTIC_RECORDED",
  summary: {
    system_attention_count: 0,
    human_now_before: 0,
    human_now_after: 0,
    effect_candidates_before: 0,
    effect_candidates_after: 0
  },
  system_attention: []
};
assert.equal(bridge.validateProjection(neutral), neutral);

const drift = {
  ...neutral,
  source_status_verdict: "HOLD_PROVIDER_DRIFT_DETECTED",
  summary: {
    system_attention_count: 1,
    human_now_before: 0,
    human_now_after: 0,
    effect_candidates_before: 0,
    effect_candidates_after: 0
  },
  system_attention: [{
    id: "SYSATTN::PROVIDER_DRIFT_HOLD",
    state: "DRIFT_HOLD",
    owner: "CONTROL_CENTER",
    requested_action: "READ_ONLY_PROVIDER_DRIFT_INVESTIGATION",
    human_now: false,
    human_gate: false,
    effect_candidate: false,
    auto_fix: false,
    controller_errors: ["provider_drift:CURRENT_STATE.json:sha256"],
    mismatches: [{root:"CURRENT_STATE.json", field:"sha256", expected:"a", observed:"b"}]
  }]
};
assert.equal(bridge.validateProjection(drift), drift);

assert.throws(
  () => bridge.validateProjection({...neutral, schema: "wrong"}),
  /schema mismatch/
);
assert.throws(
  () => bridge.validateProjection({
    ...neutral,
    summary: {...neutral.summary, human_now_after: 1}
  }),
  /HUMAN_NOW invariant mismatch/
);
assert.throws(
  () => bridge.validateProjection({
    ...neutral,
    summary: {...neutral.summary, effect_candidates_after: 1}
  }),
  /effect-candidate invariant mismatch/
);

console.log("PROVIDER_SYSTEM_ATTENTION_UI_TEST_PASS");
