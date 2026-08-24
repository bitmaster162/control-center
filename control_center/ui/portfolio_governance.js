(function (root) {
  "use strict";

  const CONTROL_URL = "../data/current_control_plane.generated.v1.json";
  const AGENT_CONTROL_URL = "../data/agent_control_plane.generated.v1.json";
  const POLICY_URL = "../data/portfolio_policy.candidate.v1.json";
  const FRESHNESS_URL = "../data/provider_freshness_evidence.current.v1.json";

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

  function table(headers, rows) {
    return `<table><thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
  }

  function canonicalProjectId(value) {
    return String(value ?? "").toLowerCase().replaceAll(/[^a-z0-9]+/g, "");
  }

  function validateInputs(control, agentControl, policy, freshness) {
    if (!control || control.schema !== "control_center.current_control_plane_projection.v1") {
      throw new Error("portfolio control-plane schema mismatch");
    }
    if (control.projection_kind !== "NON_AUTHORITY_PROJECTION") {
      throw new Error("portfolio control-plane authority invariant mismatch");
    }
    if (!agentControl || agentControl.schema !== "control_center.agent_control_plane.v1") {
      throw new Error("portfolio agent-control schema mismatch");
    }
    if (agentControl.projection_kind !== "NON_AUTHORITY_PROJECTION") {
      throw new Error("portfolio agent-control authority invariant mismatch");
    }
    if (!policy || policy.schema !== "control_center.portfolio_policy.v1") {
      throw new Error("portfolio policy schema mismatch");
    }
    if (policy.policy_kind !== "CANDIDATE_NON_AUTHORITY_POLICY" || policy.safety?.authority_granted !== false) {
      throw new Error("portfolio policy authority invariant mismatch");
    }
    if (!freshness || freshness.schema !== "control_center.provider_freshness_evidence.v1") {
      throw new Error("portfolio freshness schema mismatch");
    }
    if (freshness.projection_kind !== "NON_AUTHORITY_PROVIDER_READBACK_EVIDENCE" || freshness.safety?.evidence_grants_authority !== false) {
      throw new Error("portfolio freshness authority invariant mismatch");
    }

    const attention = agentControl.operator_attention || [];
    const agentMax = agentControl.invariants?.max_operator_attention;
    const policyMax = policy.portfolio?.max_active_lanes;
    if (!Number.isInteger(agentMax) || !Number.isInteger(policyMax) || agentMax !== policyMax) {
      throw new Error("portfolio active-lane policy mismatch");
    }
    if (attention.length > policyMax) {
      throw new Error("portfolio operator-attention invariant exceeded");
    }
    return { control, agentControl, policy, freshness };
  }

  function computeEvidenceBinding(control, freshness) {
    const expected = {
      "CURRENT_STATE.json": control.canonical_current?.root_hashes?.["CURRENT_STATE.json"],
      "ROLE_INDEX.json": control.canonical_current?.root_hashes?.["ROLE_INDEX.json"],
      "ROLE_VIEWS.json": control.canonical_current?.root_hashes?.["ROLE_VIEWS.json"],
      "MANIFEST.json": control.canonical_current?.accepted_manifest_sha256,
      "CURRENT_POINTER.json": control.canonical_current?.pointer?.sha256
    };
    const observed = {};
    for (const key of Object.keys(expected)) observed[key] = freshness.stable_roots?.[key]?.sha256;

    const incomplete = Object.keys(expected).filter((key) => !expected[key] || !observed[key]);
    const mismatches = Object.keys(expected).filter((key) => expected[key] && observed[key] && expected[key] !== observed[key]);
    const readback = freshness.readback_result || {};
    const readbackExact = readback.all_five_exact_at_capture === true
      && readback.pointer_last_by_provider_modified_time === true
      && readback.authority_critical_snapshot_match === true;

    let status = "EXACT_AT_CAPTURE";
    if (incomplete.length) status = "INCOMPLETE_HOLD";
    else if (mismatches.length) status = "MISMATCH_HOLD";
    else if (!readbackExact) status = "READBACK_HOLD";

    return {
      status,
      incomplete,
      mismatches,
      observed_at: freshness.observed_at || "UNKNOWN",
      freshness_status: freshness.freshness_status || "UNKNOWN",
      max_age_seconds: freshness.max_age_seconds ?? null,
      continuous_freshness: freshness.continuous_freshness === true,
      current_freshness_verdict_invented: false
    };
  }

  function buildPortfolioProjection(control, agentControl, policy, freshness) {
    validateInputs(control, agentControl, policy, freshness);

    const attention = agentControl.operator_attention || [];
    const attentionByProject = new Map();
    for (const item of attention) {
      const key = canonicalProjectId(item.project);
      if (key && !attentionByProject.has(key)) attentionByProject.set(key, item);
    }

    const evidenceBinding = computeEvidenceBinding(control, freshness);
    const policyProjects = policy.projects || {};
    const rows = (control.projects || []).map((project) => {
      const key = canonicalProjectId(project.id);
      const attentionItem = attentionByProject.get(key) || null;
      if (attentionItem) attentionByProject.delete(key);
      const blockers = Array.isArray(project.blocked_by) ? project.blocked_by : [];
      const policyEntry = Object.prototype.hasOwnProperty.call(policyProjects, project.id)
        ? policyProjects[project.id]
        : null;

      return {
        id: project.id,
        owner: project.owner || "UNKNOWN",
        state: project.state || "UNKNOWN",
        next: project.next || "UNKNOWN",
        active_lane: Boolean(attentionItem),
        active_lane_rank: attentionItem?.rank ?? null,
        active_lane_reason: attentionItem?.reason ?? null,
        blocker: blockers[0] || null,
        blocker_count: blockers.length,
        policy_bound: Boolean(policyEntry),
        policy_state: policyEntry?.policy_state ?? null,
        definition_of_done: policyEntry?.definition_of_done ?? null,
        kill_sunset_criteria: policyEntry?.kill_sunset_criteria ?? null,
        freshness_policy: policyEntry?.freshness_policy ?? null,
        evidence_binding: evidenceBinding
      };
    });

    const unregisteredAttention = attention.filter((item) =>
      attentionByProject.has(canonicalProjectId(item.project))
    );

    return {
      schema: "control_center.portfolio_governance_projection.v2",
      projection_kind: "NON_AUTHORITY_DERIVED_PROJECTION",
      observed_at: control.observed_at || "UNKNOWN",
      source_agent_control_observed_at: agentControl.observed_at || "UNKNOWN",
      policy_version: policy.policy_version || "UNKNOWN",
      policy_kind: policy.policy_kind,
      provider_evidence_binding: evidenceBinding,
      rows,
      unregistered_attention: unregisteredAttention,
      summary: {
        tracked_projects: rows.length,
        blocked_projects: rows.filter((row) => row.blocker_count > 0).length,
        active_lanes: attention.length,
        max_active_lanes: policy.portfolio.max_active_lanes,
        unregistered_attention: unregisteredAttention.length,
        policy_bound_projects: rows.filter((row) => row.policy_bound).length,
        policy_missing_projects: rows.filter((row) => !row.policy_bound).length,
        terminal_criteria_missing: rows.filter((row) => row.definition_of_done == null).length,
        kill_criteria_missing: rows.filter((row) => row.kill_sunset_criteria == null).length
      },
      invariants: {
        authority_granted: false,
        source_of_truth: false,
        auto_dispatch: false,
        auto_fix: false,
        priority_score_invented: false,
        current_freshness_verdict_invented: false,
        active_lane_policy_matches_provider_invariant: true
      }
    };
  }

  function renderDefinitionOfDone(value, policyState) {
    if (!value) return badge("MISSING / NOT EVIDENCED");
    const parts = Object.entries(value).map(([dimension, criteria]) => {
      const items = Array.isArray(criteria) ? criteria : [criteria];
      return `<div><strong>${esc(dimension.replaceAll("_", " "))}</strong><ul>${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul></div>`;
    });
    return `${badge(policyState || "BOUND")} ${parts.join("")}`;
  }

  function renderKillCriteria(value) {
    if (!Array.isArray(value) || !value.length) return badge("MISSING / NOT EVIDENCED");
    return `<ul>${value.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
  }

  function renderEvidence(value) {
    const details = [];
    details.push(`captured: ${value.observed_at}`);
    details.push(`source status: ${value.freshness_status}`);
    if (value.max_age_seconds != null) details.push(`lease max age: ${value.max_age_seconds}s`);
    details.push(`continuous freshness: ${value.continuous_freshness ? "true" : "false"}`);
    if (value.mismatches?.length) details.push(`mismatch: ${value.mismatches.join(", ")}`);
    if (value.incomplete?.length) details.push(`incomplete: ${value.incomplete.join(", ")}`);
    return `${badge(value.status)}<br><span class="muted">${details.map(esc).join(" · ")}</span>`;
  }

  function renderProjection(target, projection) {
    const rows = projection.rows || [];
    const s = projection.summary || {};

    const tableRows = rows.map((row) => `<tr>
      <td><strong>${esc(row.id)}</strong><br><span class="muted">${esc(row.next)}</span></td>
      <td>${esc(row.owner)}</td>
      <td>${badge(row.state)}</td>
      <td>${row.active_lane ? badge(`ACTIVE #${row.active_lane_rank ?? "?"}`) : badge("QUEUE / TRACKED")}${row.active_lane_reason ? `<br><span class="muted">${esc(row.active_lane_reason)}</span>` : ""}</td>
      <td>${row.blocker ? `<strong>${esc(row.blocker)}</strong>${row.blocker_count > 1 ? `<br><span class="muted">+${row.blocker_count - 1} more</span>` : ""}` : "none evidenced"}</td>
      <td>${renderDefinitionOfDone(row.definition_of_done, row.policy_state)}</td>
      <td>${renderKillCriteria(row.kill_sunset_criteria)}</td>
      <td>${renderEvidence(row.evidence_binding)}</td>
    </tr>`);

    const unregistered = (projection.unregistered_attention || []).map((item) => `<tr>
      <td><strong>#${esc(item.rank)}</strong></td>
      <td>${esc(item.project)}</td>
      <td>${badge(item.reported_state)}</td>
      <td>${esc(item.reason)}</td>
      <td>${esc(item.requested_next)}</td>
    </tr>`);

    target.innerHTML = `
      <div class="callout">
        <strong>Portfolio governance · R2 policy binding · read-only derived projection</strong>
        <p>Tracked projects: <b>${esc(s.tracked_projects)}</b> · blocked: <b>${esc(s.blocked_projects)}</b> · active attention lanes: <b>${esc(s.active_lanes)}</b> / <b>${esc(s.max_active_lanes)}</b>.</p>
        <p>Policy bound: <b>${esc(s.policy_bound_projects)}</b> · policy missing: <b>${esc(s.policy_missing_projects)}</b> · attention items not bound to the project registry: <b>${esc(s.unregistered_attention)}</b>.</p>
        <p>Provider evidence binding: <b>${esc(projection.provider_evidence_binding?.status)}</b> · capture: <b>${esc(projection.provider_evidence_binding?.observed_at)}</b>.</p>
        <p class="muted">Policy is candidate/non-authority. Provider lease metadata is shown, but no live freshness verdict, priority score, terminal state, kill decision, dispatch, repair, merge, deploy or effect authority is invented here.</p>
      </div>
      <div class="table-wrap">${table(["Project", "Owner", "State", "Portfolio lane", "Active blocker", "Definition of Done", "Kill / sunset", "Evidence binding"], tableRows)}</div>
      ${unregistered.length ? `
        <h3>Attention not bound to tracked project registry</h3>
        <div class="table-wrap">${table(["Rank", "Observed project", "State", "Reason", "Requested next"], unregistered)}</div>
        <p class="muted">These are provider observations, not automatic project registrations.</p>` : ""}
    `;
    return projection;
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`);
    return response.json();
  }

  async function boot() {
    const target = document.querySelector("#portfolio-governance-list");
    if (!target) return;
    try {
      const [control, agentControl, policy, freshness] = await Promise.all([
        fetchJson(CONTROL_URL),
        fetchJson(AGENT_CONTROL_URL),
        fetchJson(POLICY_URL),
        fetchJson(FRESHNESS_URL)
      ]);
      renderProjection(target, buildPortfolioProjection(control, agentControl, policy, freshness));
    } catch (error) {
      target.innerHTML = `<div class="error">Portfolio governance unavailable: ${esc(error.message)}</div>`;
      console.error(error);
    }
  }

  const api = { canonicalProjectId, validateInputs, computeEvidenceBinding, buildPortfolioProjection, renderProjection };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioGovernance = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
