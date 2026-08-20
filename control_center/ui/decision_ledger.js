const DECISION_LEDGER_URL = "../data/decision_effect_ledger.generated.v1.json";

const decEsc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function decBadge(value) {
  const text = String(value ?? "UNKNOWN");
  const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="status status-${decEsc(key)}">${decEsc(text)}</span>`;
}

function decTable(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th>${decEsc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function renderDecisionLedger(data) {
  const summary = data.summary || {};
  const decisions = data.decisions || [];
  const attention = data.compressed_operator_attention || [];
  const byId = new Map(decisions.map((d) => [d.decision_id, d]));
  const ripeIds = data.queues?.human_ripe || [];
  const ripe = ripeIds.map((id) => byId.get(id)).filter(Boolean);

  const summaryCards = [
    ["Ripe human gates", summary.human_ripe_count],
    ["Control Center semantic queue", summary.control_center_semantic_queue_count],
    ["Owner-only queue", summary.project_owner_queue_count],
    ["Effects authorized", summary.effects_authorized]
  ].map(([label, value]) => `
    <article class="card">
      <div class="card-top"><strong>${decEsc(label)}</strong></div>
      <h3>${decEsc(value)}</h3>
    </article>`).join("");

  const ripeCards = ripe.length ? ripe.map((d) => `
    <article class="card emphasis">
      <div class="card-top"><strong>${decEsc(d.work_order)}</strong>${decBadge(d.decision_state)}</div>
      <h3>${decEsc(d.project)}</h3>
      <p><b>Gate:</b> ${decEsc(d.gate)}</p>
      <p><b>Authority:</b> ${decEsc(d.authority_required)}</p>
      <p><b>Allowed:</b> ${decEsc((d.allowed_decisions || []).join(" / "))}</p>
      <p><b>Current:</b> semantic ${decEsc(d.semantic_status)} · apply ${decEsc(d.apply_status)}</p>
      <p><b>Execution:</b> ${d.execution_authorized === false ? "DENY" : "UNKNOWN"}</p>
    </article>`).join("") : `<div class="empty">No ripe human gates.</div>`;

  const attentionRows = attention.map((a) => `<tr>
    <td>${decEsc(a.rank)}</td>
    <td><strong>${decEsc(a.work_order)}</strong><br><span class="muted">${decEsc(a.slot)}</span></td>
    <td>${decEsc(a.project)}</td>
    <td>${decBadge(a.route)}</td>
    <td>${a.human_ripe ? decBadge("RIPE") : decBadge("ROUTED")}</td>
    <td>${decEsc(a.reason)}</td>
  </tr>`);

  const decisionRows = decisions.map((d) => `<tr>
    <td><strong>${decEsc(d.work_order)}</strong><br><span class="muted">${decEsc(d.slot)}</span>${d.do_not_touch ? `<br><span class="muted">DO NOT TOUCH</span>` : ""}</td>
    <td>${decEsc(d.project)}</td>
    <td>${decBadge(d.decision_class)}</td>
    <td>${decBadge(d.decision_state)}</td>
    <td>${decEsc(d.owner)}</td>
    <td>${decEsc(d.authority_required)}</td>
    <td>${decEsc((d.allowed_decisions || []).join(" / "))}</td>
    <td>${decBadge(d.semantic_status)}</td>
    <td>${decBadge(d.apply_status)}</td>
    <td>${decEsc(d.gate)}</td>
  </tr>`);

  const policy = data.policy || {};
  document.querySelector("#decision-gates-list").innerHTML = `
    <div class="callout">
      <strong>Decision policy:</strong>
      auto-dispatch ${policy.auto_dispatch === false ? "DENY" : "UNKNOWN"} ·
      auto-accept ${policy.auto_accept === false ? "DENY" : "UNKNOWN"} ·
      auto-apply ${policy.auto_apply === false ? "DENY" : "UNKNOWN"} ·
      self-approval ${policy.self_approval === false ? "DENY" : "UNKNOWN"}
      <p>Semantic ACCEPT never authorizes an effect. Effect authorization never executes the effect. Any effect requires post-effect readback.</p>
    </div>
    <div class="grid cards">${summaryCards}</div>
    <h3>Ripe human gates</h3>
    <div class="grid cards">${ripeCards}</div>
    <h3>Attention routing</h3>
    <div class="table-wrap">${decTable(["Rank", "Work order / slot", "Project", "Route", "Human", "Reason"], attentionRows)}</div>
    <h3>Decision objects</h3>
    <div class="table-wrap">${decTable(["Work order / slot", "Project", "Class", "State", "Owner", "Authority", "Allowed", "Semantic", "Apply", "Gate"], decisionRows)}</div>
  `;

  window.dispatchEvent(new CustomEvent("control-center:decision-ledger", { detail: data }));
}

async function loadDecisionLedger() {
  const response = await fetch(DECISION_LEDGER_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`decision ledger fetch failed: ${response.status}`);
  renderDecisionLedger(await response.json());
}

loadDecisionLedger().catch((error) => {
  const target = document.querySelector("#decision-gates-list");
  if (target) target.innerHTML = `<div class="error">${decEsc(error.message)}</div>`;
  console.error(error);
});
