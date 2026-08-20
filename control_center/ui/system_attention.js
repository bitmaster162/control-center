(function (root) {
  "use strict";

  const DATA_URL = "../data/provider_system_attention.generated.v1.json";

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

  function validateProjection(data) {
    if (!data || data.schema !== "control_center.provider_system_attention.v1") {
      throw new Error("provider system-attention schema mismatch");
    }
    if (data.projection_kind !== "NON_AUTHORITY_OPERATOR_ATTENTION_PROJECTION") {
      throw new Error("provider system-attention projection kind mismatch");
    }
    const summary = data.summary || {};
    if (summary.human_now_before !== summary.human_now_after) {
      throw new Error("provider system-attention HUMAN_NOW invariant mismatch");
    }
    if (summary.effect_candidates_before !== summary.effect_candidates_after) {
      throw new Error("provider system-attention effect-candidate invariant mismatch");
    }
    return data;
  }

  function renderProjection(target, raw) {
    const data = validateProjection(raw);
    const items = data.system_attention || [];

    if (!items.length) {
      target.innerHTML = `
        <div class="callout">
          <strong>No verified provider-drift system attention.</strong>
          <p>Source verdict: ${esc(data.source_status_verdict)}.</p>
          <p class="muted">This is not proof that provider drift is absent. A fresh read-only provider capture is required to establish a new diagnostic state.</p>
          <p class="muted">SYSTEM ATTENTION is separate from HUMAN_NOW and grants no effect authority.</p>
        </div>`;
      return data;
    }

    const cards = items.map((item) => {
      const mismatchRows = (item.mismatches || []).map((row) => `<tr>
        <td>${esc(row.root || row.file || "—")}</td>
        <td>${esc(row.field || "—")}</td>
        <td>${esc(row.expected ?? "—")}</td>
        <td>${esc(row.observed ?? "—")}</td>
      </tr>`);
      const mismatches = mismatchRows.length
        ? `<div class="table-wrap">${table(["Root", "Field", "Expected", "Observed"], mismatchRows)}</div>`
        : `<div class="empty">No bounded mismatch rows attached.</div>`;
      return `
        <article class="card emphasis">
          <div class="card-top"><strong>${esc(item.id)}</strong>${badge(item.state)}</div>
          <h3>${esc(item.requested_action)}</h3>
          <p><b>Owner:</b> ${esc(item.owner)}</p>
          <p><b>Severity:</b> ${esc(item.severity)}</p>
          <p><b>Controller errors:</b> ${esc((item.controller_errors || []).join(" · ") || "none")}</p>
          <p><b>HUMAN_NOW:</b> ${item.human_now === false ? "NO" : "INVALID"}</p>
          <p><b>Human gate:</b> ${item.human_gate === false ? "NO" : "INVALID"}</p>
          <p><b>Effect candidate:</b> ${item.effect_candidate === false ? "NO" : "INVALID"}</p>
          <p><b>Auto-fix:</b> ${item.auto_fix === false ? "DENY" : "INVALID"}</p>
          <p class="muted">${esc(item.note || "")}</p>
          ${mismatches}
        </article>`;
    }).join("");

    target.innerHTML = `
      <div class="callout">
        <strong>SYSTEM ATTENTION · provider drift</strong>
        <p>This lane is read-only operator attention. It does not create HUMAN_NOW, an effect candidate, a command, or execution authority.</p>
      </div>
      <div class="grid cards">${cards}</div>`;
    return data;
  }

  async function boot() {
    const target = document.querySelector("#system-attention-list");
    if (!target) return;
    try {
      const response = await fetch(DATA_URL, { cache: "no-store" });
      if (!response.ok) throw new Error(`${DATA_URL} fetch failed: ${response.status}`);
      renderProjection(target, await response.json());
    } catch (error) {
      target.innerHTML = `<div class="error">System attention unavailable: ${esc(error.message)}</div>`;
      console.error(error);
    }
  }

  const api = { validateProjection, renderProjection };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.ProviderSystemAttention = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
