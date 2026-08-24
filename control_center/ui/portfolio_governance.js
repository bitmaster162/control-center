(function (root) {
  "use strict";

  const CONTROL_URL = "../data/current_control_plane.generated.v1.json";
  const AGENT_CONTROL_URL = "../data/agent_control_plane.generated.v1.json";

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

  function validateInputs(control, agentControl) {
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

    const attention = agentControl.operator_attention || [];
    const max = agentControl.invariants?.max_operator_attention;
    if (Number.isInteger(max) && attention.length > max) {
      throw new Error("portfolio operator-attention invariant exceeded");
    }
    return { control, agentControl };
  }

  function buildPortfolioProjection(control, agentControl) {
    validateInputs(control, agentControl);

    const attention = agentControl.operator_attention || [];
    const attentionByProject = new Map();
    for (const item of attention) {
      const key = canonicalProjectId(item.project);
      if (key && !attentionByProject.has(key)) attentionByProject.set(key, item);
    }

    const rows = (control.projects || []).map((project) => {
      const key = canonicalProjectId(project.id);
      const attentionItem = attentionByProject.get(key) || null;
      if (attentionItem) attentionByProject.delete(key);
      const blockers = Array.isArray(project.blocked_by) ? project.blocked_by : [];

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
        terminal_criteria: project.terminal_criteria ?? null,
        kill_criteria: project.kill_criteria ?? project.sunset_criteria ?? null,
        evidence_observed_at: control.observed_at || "UNKNOWN"
      };
    });

    const unregisteredAttention = attention.filter((item) =>
      attentionByProject.has(canonicalProjectId(item.project))
    );

    return {
      schema: "control_center.portfolio_governance_projection.v1",
      projection_kind: "NON_AUTHORITY_DERIVED_PROJECTION",
      observed_at: control.observed_at || "UNKNOWN",
      source_agent_control_observed_at: agentControl.observed_at || "UNKNOWN",
      rows,
      unregistered_attention: unregisteredAttention,
      summary: {
        tracked_projects: rows.length,
        blocked_projects: rows.filter((row) => row.blocker_count > 0).length,
        active_lanes: attention.length,
        unregistered_attention: unregisteredAttention.length,
        terminal_criteria_missing: rows.filter((row) => row.terminal_criteria == null).length,
        kill_criteria_missing: rows.filter((row) => row.kill_criteria == null).length
      },
      invariants: {
        authority_granted: false,
        source_of_truth: false,
        auto_dispatch: false,
        auto_fix: false,
        priority_score_invented: false
      }
    };
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
      <td>${row.terminal_criteria == null ? badge("MISSING / NOT EVIDENCED") : esc(row.terminal_criteria)}</td>
      <td>${row.kill_criteria == null ? badge("MISSING / NOT EVIDENCED") : esc(row.kill_criteria)}</td>
      <td>${esc(row.evidence_observed_at)}</td>
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
        <strong>Portfolio governance · read-only derived projection</strong>
        <p>Tracked projects: <b>${esc(s.tracked_projects)}</b> · blocked: <b>${esc(s.blocked_projects)}</b> · active attention lanes: <b>${esc(s.active_lanes)}</b>.</p>
        <p>Missing terminal criteria: <b>${esc(s.terminal_criteria_missing)}</b> · missing kill/sunset criteria: <b>${esc(s.kill_criteria_missing)}</b> · attention items not bound to the project registry: <b>${esc(s.unregistered_attention)}</b>.</p>
        <p class="muted">No priority score, freshness verdict, terminal state or kill decision is invented here. Missing evidence remains visibly missing. This projection grants no dispatch, repair, merge, deploy or effect authority.</p>
      </div>
      <div class="table-wrap">${table(["Project", "Owner", "State", "Portfolio lane", "Active blocker", "Definition of Done", "Kill / sunset", "Evidence observed"], tableRows)}</div>
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
      const [control, agentControl] = await Promise.all([
        fetchJson(CONTROL_URL),
        fetchJson(AGENT_CONTROL_URL)
      ]);
      renderProjection(target, buildPortfolioProjection(control, agentControl));
    } catch (error) {
      target.innerHTML = `<div class="error">Portfolio governance unavailable: ${esc(error.message)}</div>`;
      console.error(error);
    }
  }

  const api = { canonicalProjectId, validateInputs, buildPortfolioProjection, renderProjection };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioGovernance = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
