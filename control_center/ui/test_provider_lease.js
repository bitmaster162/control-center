const assert = require("node:assert/strict");
const lease = require("./provider_lease.js");

const evidence = {
  schema: "control_center.provider_freshness_evidence.v1",
  freshness_status: "FRESH_AT_CAPTURE",
  continuous_freshness: false,
  observed_at: "2026-08-12T04:59:00+07:00",
  max_age_seconds: 21600
};

const observed = Date.parse(evidence.observed_at);
const expires = observed + 21600 * 1000;

assert.equal(lease.classifyProviderLease(evidence, null, observed + 60 * 1000).state, "FRESH");
assert.equal(lease.classifyProviderLease(evidence, null, expires - 3601 * 1000).state, "FRESH");
assert.equal(lease.classifyProviderLease(evidence, null, expires - 3600 * 1000).state, "EXPIRING");
assert.equal(lease.classifyProviderLease(evidence, null, expires - 1).state, "EXPIRING");
assert.equal(lease.classifyProviderLease(evidence, null, expires).state, "EXPIRED");
assert.equal(lease.classifyProviderLease(evidence, null, expires + 60 * 1000).state, "EXPIRED");

const expiredHold = { verdict: "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED" };
assert.equal(lease.classifyProviderLease(evidence, expiredHold, observed + 60 * 1000).state, "EXPIRED");

for (const verdict of [
  "HOLD_PROVIDER_DRIFT_DETECTED",
  "HOLD_INVALID_OR_INCOMPLETE_CAPTURE"
]) {
  const result = lease.classifyProviderLease(evidence, { verdict }, observed + 60 * 1000);
  assert.equal(result.state, "DRIFT_HOLD");
  assert.equal(result.reason, verdict);
}

assert.equal(
  lease.classifyProviderLease(evidence, { verdict: "REFRESH_EVIDENCE_ONLY_ALLOWED" }, observed + 60 * 1000).state,
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
