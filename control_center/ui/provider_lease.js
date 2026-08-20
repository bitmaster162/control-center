(function (root) {
  "use strict";

  const EVIDENCE_URL = "../data/provider_freshness_evidence.current.v1.json";
  const HOLD_URL = "../data/provider_refresh_controller_status.current.v1.json";
  const EXPIRING_THRESHOLD_SECONDS = 3600;
  const EXPIRED_HOLD = "HOLD_FRESHNESS_EXPIRED_RECAPTURE_REQUIRED";
  const DRIFT_HOLD_VERDICT = "HOLD_PROVIDER_DRIFT_DETECTED";
  const STATUS_SCHEMA = "control_center.provider_refresh_controller_status.v1";

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function badge(value) {
    const text = String(value ?? "UNKNOWN");
    const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
    return `<span class="status status-${esc(key)}">${esc(text)}</span>`;
  }

  function parseEvidence(evidence) {
    if (!evidence || evidence.schema !== "control_center.provider_freshness_evidence.v1") {
      throw new Error("provider freshness evidence schema mismatch");
    }
    if (evidence.freshness_status !== "FRESH_AT_CAPTURE" || evidence.continuous_freshness !== false) {
      throw new Error("provider freshness evidence semantic mismatch");
    }
    const observedAtMs = Date.parse(evidence.observed_at);
    const maxAgeSeconds = Number(evidence.max_age_seconds);
    if (!Number.isFinite(observedAtMs) || !Number.isFinite(maxAgeSeconds) || maxAgeSeconds <= 0) {
      throw new Error("provider freshness evidence lease fields invalid");
    }
    return {
      observedAtMs,
      maxAgeSeconds,
      expiresAtMs: observedAtMs + maxAgeSeconds * 1000
    };
  }

  function holdVerdict(holdDiagnostic) {
    if (!holdDiagnostic) return "";
    if (holdDiagnostic.schema !== STATUS_SCHEMA) {
      throw new Error("provider refresh diagnostic schema mismatch");
    }
    return String(holdDiagnostic.verdict || "");
  }

  function validateDriftDiagnostic(holdDiagnostic) {
    if (holdDiagnostic.operator_state !== "DRIFT_HOLD" || holdDiagnostic.hold_active !== true) {
      throw new Error("provider drift diagnostic semantic mismatch");
    }
    if (!Array.isArray(holdDiagnostic.mismatches) || holdDiagnostic.mismatches.length === 0) {
      throw new Error("provider drift diagnostic mismatch evidence missing");
    }
    if (holdDiagnostic.safety?.diagnostic_grants_authority !== false) {
      throw new Error("provider drift diagnostic authority boundary invalid");
    }
  }

  function classifyProviderLease(evidence, holdDiagnostic, nowMs = Date.now()) {
    const lease = parseEvidence(evidence);
    const explicitHold = holdVerdict(holdDiagnostic);
    const remainingSeconds = Math.floor((lease.expiresAtMs - nowMs) / 1000);

    if (explicitHold === DRIFT_HOLD_VERDICT) {
      validateDriftDiagnostic(holdDiagnostic);
      return {
        state: "DRIFT_HOLD",
        reason: explicitHold,
        remainingSeconds,
        ...lease
      };
    }
    if (explicitHold === EXPIRED_HOLD || nowMs >= lease.expiresAtMs) {
      return {
        state: "EXPIRED",
        reason: explicitHold || "LEASE_CLOCK_EXPIRED",
        remainingSeconds,
        ...lease
      };
    }
    if (explicitHold.startsWith("HOLD_")) {
      throw new Error(`unsupported provider hold diagnostic: ${explicitHold}`);
    }
    if (remainingSeconds <= EXPIRING_THRESHOLD_SECONDS) {
      return {
        state: "EXPIRING",
        reason: "WITHIN_ONE_HOUR_OF_EXPIRY",
        remainingSeconds,
        ...lease
      };
    }
    return {
      state: "FRESH",
      reason: "BOUNDED_LEASE_ACTIVE",
      remainingSeconds,
      ...lease
    };
  }

  function formatBangkok(ms) {
    const parts = new Intl.DateTimeFormat("sv-SE", {
      timeZone: "Asia/Bangkok",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    }).format(new Date(ms));
    return `${parts.replace(" ", "T")}+07:00`;
  }

  function formatRemaining(seconds) {
    const safe = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(safe / 3600);
    const minutes = Math.floor((safe % 3600) / 60);
    const secs = safe % 60;
    return `${hours}h ${String(minutes).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  }

  function renderDriftDetails(holdDiagnostic) {
    if (!holdDiagnostic || holdDiagnostic.verdict !== DRIFT_HOLD_VERDICT) return "";
    const rows = (holdDiagnostic.mismatches || []).map((item) => `
      <tr>
        <td>${esc(item.root)}</td>
        <td>${esc(item.field)}</td>
        <td><code>${esc(item.expected)}</code></td>
        <td><code>${esc(item.observed)}</code></td>
      </tr>`).join("");
    const codes = (holdDiagnostic.controller_errors || []).map((code) => `<code>${esc(code)}</code>`).join("<br>");
    return `
      <article class="card">
        <div class="card-top"><strong>Bounded drift diagnostic</strong><span class="pill">no auto-fix</span></div>
        <p><b>Controller errors:</b><br>${codes || "none"}</p>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Root</th><th>Field</th><th>Expected</th><th>Observed</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <p><b>Remediation:</b> not authorized. Separate investigation/effect gate required for any write.</p>
      </article>`;
  }

  function renderProviderLease(target, evidence, holdDiagnostic, nowMs = Date.now()) {
    const state = classifyProviderLease(evidence, holdDiagnostic, nowMs);
    const observed = parseEvidence(evidence).observedAtMs;
    const remaining = state.state === "EXPIRED" ? "expired" : formatRemaining(state.remainingSeconds);
    target.innerHTML = `
      <div class="grid cards">
        <article class="card emphasis">
          <div class="card-top"><strong>Provider freshness lease</strong>${badge(state.state)}</div>
          <p><b>Observed:</b> ${esc(formatBangkok(observed))}</p>
          <p><b>Expires:</b> ${esc(formatBangkok(state.expiresAtMs))}</p>
          <p><b>Remaining:</b> ${esc(remaining)}</p>
          <p><b>Lease:</b> ${esc(evidence.max_age_seconds)} seconds</p>
          <p><b>Reason:</b> ${esc(state.reason)}</p>
        </article>
        <article class="card">
          <div class="card-top"><strong>Semantics</strong><span class="pill">projection only</span></div>
          <p><b>Freshness:</b> FRESH_AT_CAPTURE, not continuous.</p>
          <p><b>Auto refresh:</b> DENY. Browser clock updates presentation only.</p>
          <p><b>Provider calls:</b> none from Cockpit.</p>
          <p><b>Authority:</b> none. Lease state cannot dispatch, apply, execute, write roots, deploy, trade, or grant capital authority.</p>
        </article>
        ${renderDriftDetails(holdDiagnostic)}
      </div>`;
    return state;
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`);
    return response.json();
  }

  async function fetchOptionalJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`);
    return response.json();
  }

  async function boot() {
    const target = document.querySelector("#provider-lease-list");
    if (!target) return;
    try {
      const [evidence, holdDiagnostic] = await Promise.all([
        fetchJson(EVIDENCE_URL),
        fetchOptionalJson(HOLD_URL)
      ]);
      const rerender = () => renderProviderLease(target, evidence, holdDiagnostic, Date.now());
      rerender();
      root.setInterval(rerender, 30000);
    } catch (error) {
      target.innerHTML = `<div class="error">Provider lease unavailable: ${esc(error.message)}</div>`;
      console.error(error);
    }
  }

  const api = {
    EXPIRING_THRESHOLD_SECONDS,
    DRIFT_HOLD_VERDICT,
    classifyProviderLease,
    parseEvidence,
    formatRemaining
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.ProviderLease = api;

  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
