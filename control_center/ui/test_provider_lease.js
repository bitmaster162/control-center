const assert = require("node:assert/strict");
const lease = require("./provider_lease.js");

const evidence = {
  schema: "control_center.provider_freshness_evidence.v1",
  freshness_status: "FRESH_AT_CAPTURE",
  continuous_freshness: false,
  observed_at: "2026-08-12T04:59:00+07:00",
  max_age_seconds: 21600
};

const statusBase = {
  schema: "control_center.provider_refresh_controller_status.v1",
  projection_kind: "NON_AUTHORITY_PROVIDER_REFRESH_DIAGNOSTIC",
  safety: { diagnostic_grants_authority: false }
};

const observed = Date.parse(evidence.observed_at);
const expires = observed + 21600 * 1000;

assert.equal(lease.classifyProviderLease(evidence, null, observed + 60 * 1000).state, "FRESH");
assert.equal(lease.classifyProviderLease(evidence, null, expires - 3601 * 1000).state, "FRESH");
assert.equal(lease.classifyProviderLease(evidence, null, expires - 3600 * 1000).state, "EXPIRING");
assert.equal(lease.classifyProviderLease(evidence, null, expires - 1).state, "EXPIRING");
assert.equal(lease.classifyProviderLease(evidence, null, expires).state, "EXPIRED");
assert.equal(lease.classifyProviderLease(evidence, null, expires + 60 * 1000).state, "EXPIRED");

const neutral = {
  ...statusBase,
  verdict: "NO_HOLD_DIAGNOSTIC_RECORDED",
  operator_state: "NO_HOLD_DIAGNOSTIC_RECORDED",
  hold_active: false,
  mismatches: []
};
assert.equal(lease.classifyProviderLease(evidence, neutral, observed + 60 * 1000).state, "FRESH");

const expiredHold = {
  ...statusBase,
  verdict: "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED",
  operator_state: "EXPIRED",
  hold_active: true,
  mismatches: []
};
assert.equal(lease.classifyProviderLease(evidence, expiredHold, observed + 60 * 1000).state, "EXPIRED");

const driftHold = {
  ...statusBase,
  verdict: "HOLD_PROVIDER_DRIFT_DETECTED",
  operator_state: "DRIFT_HOLD",
  hold_active: true,
  controller_errors: ["provider_drift:CURRENT_STATE.json:sha256"],
  mismatches: [{
    root: "CURRENT_STATE.json",
    field: "sha256",
    expected: "expected-sha",
    observed: "observed-sha"
  }]
};
const driftResult = lease.classifyProviderLease(evidence, driftHold, observed + 60 * 1000);
assert.equal(driftResult.state, "DRIFT_HOLD");
assert.equal(driftResult.reason, "HOLD_PROVIDER_DRIFT_DETECTED");

assert.throws(
  () => lease.classifyProviderLease(evidence, { ...statusBase, verdict: "HOLD_INVALID_OR_INCOMPLETE_CAPTURE", operator_state: "INVALID_CAPTURE_HOLD", hold_active: true }, observed + 60 * 1000),
  /unsupported provider hold diagnostic/
);
assert.throws(
  () => lease.classifyProviderLease(evidence, { ...driftHold, mismatches: [] }, observed + 60 * 1000),
  /mismatch evidence missing/
);
assert.throws(
  () => lease.classifyProviderLease(evidence, { ...driftHold, safety: { diagnostic_grants_authority: true } }, observed + 60 * 1000),
  /authority boundary invalid/
);
assert.throws(
  () => lease.classifyProviderLease(evidence, { ...neutral, schema: "wrong" }, observed + 60 * 1000),
  /diagnostic schema mismatch/
);

assert.equal(
  lease.classifyProviderLease(evidence, { ...statusBase, verdict: "REFRESH_EVIDENCE_ONLY_ALLOWED", operator_state: "NO_HOLD", hold_active: false, mismatches: [] }, observed + 60 * 1000).state,
  "FRESH"
);

assert.throws(
  () => lease.classifyProviderLease({ ...evidence, schema: "wrong" }, null, observed),
  /schema mismatch/
);
assert.throws(
  () => lease.classifyProviderLease({ ...evidence, continuous_freshness: true }, null, observed),
  /semantic mismatch/
);
assert.throws(
  () => lease.classifyProviderLease({ ...evidence, max_age_seconds: 0 }, null, observed),
  /lease fields invalid/
);

console.log("PROVIDER_LEASE_OPERATOR_PROJECTION_TEST_PASS");
