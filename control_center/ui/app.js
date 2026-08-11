const DATA_URL = "../data/current_control_plane.generated.v1.json";
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

function renderSafety(data) {
  const s = data.safety || {};
  document.querySelector("#safety").innerHTML = [
    `trade ${s.can_trade === false ? "DENY" : "UNKNOWN"}`,
    `capital ${s.capital_permission || "UNKNOWN"}`,
    `deploy ${s.deploy_permission || "UNKNOWN"}`,
    `self-apply ${s.self_application === false ? "DENY" : "UNKNOWN"}`
  ].map((x) => `<span class="pill">${esc(x)}</span>`).join("");
}

function renderNowPending() {
  document.querySelector("#now-cards").innerHTML = `<div class="empty">Loading ripe human gates from Decision / Effect Gate Ledger…</div>`;
}

function renderRipeNow(ledger) {
  const decisions = ledger.decisions || [];
  const byId = new Map(decisions.map((d) => [d.decision_id, d]));
  const ripe = (ledger.queues?.human_ripe || []).map((id) => byId.get(id)).filter(Boolean);
  document.querySelector("#now-cards").innerHTML = ripe.length
    ? ripe.map((d) => `
      <article class="card emphasis">
        <div class="card-top"><strong>${esc(d.work_order)}</strong>${badge(d.decision_state)}</div>
        <h3>${esc(d.project)}</h3>
        <p><b>Gate:</b> ${esc(d.gate)}</p>
        <p><b>Authority:</b> ${esc(d.authority_required)}</p>
        <p><b>Allowed:</b> ${esc((d.allowed_decisions || []).join(" / "))}</p>
        <p><b>Current:</b> semantic ${esc(d.semantic_status)} · apply ${esc(d.apply_status)} · execution ${d.execution_authorized === false ? "DENY" : "UNKNOWN"}</p>
      </article>`).join("")
    : `<div class="empty">No ripe human gates. Control Center and project-owner queues continue without escalating to Robert.</div>`;
}

window.addEventListener("control-center:decision-ledger", (event) => renderRipeNow(event.detail || {}));

function renderAgents(data) {
  const rows = (data.agents || []).map((a) => `<tr>
    <td><strong>${esc(a.id)}</strong></td>
    <td>${esc(a.role)}</td>
    <td>${badge(a.state)}</td>
    <td>${esc(a.current_assignment)}</td>
  </tr>`);
  document.querySelector("#agents-list").innerHTML = table(["Agent / owner", "Role", "State", "Current assignment"], rows);
}

function renderAgentControl(control) {
  const global = control.global_dispatch || {};
  const attention = (control.operator_attention || []).slice(0, 3);
  const pending = control.blocked_dispatch_queue || [];
  const slots = control.slots || [];

  const attentionCards = attention.length ? attention.map((item) => `
    <article class="card emphasis">
      <div class="card-top"><strong>#${esc(item.rank)} · ${esc(item.slot)}</strong>${badge(item.reported_state)}</div>
      <h3>${esc(item.project)}</h3>
      <p><b>Why now:</b> ${esc(item.reason)}</p>
      <p><b>Next:</b> ${esc(item.requested_next)}</p>
      <p><b>Gate:</b> ${esc(item.human_gate)}</p>
    </article>`).join("") : `<div class="empty">No bounded operator-attention items.</div>`;

  const pendingRows = pending.map((item) => `<tr>
    <td><strong>${esc(item.slot)}</strong></td>
    <td>${esc(item.project)}</td>
    <td>${badge(item.reported_state)}</td>
    <td>${esc(item.work_order)}</td>
    <td>${esc(item.blocker)}</td>
  </tr>`);

  const slotRows = slots.map((item) => `<tr>
    <td><strong>${esc(item.slot)}</strong>${item.do_not_touch ? `<br><span class="muted">DO NOT TOUCH</span>` : ""}</td>
    <td>${esc(item.project_hint)}</td>
    <td>${badge(item.reported_state)}</td>
    <td>${esc(item.operational_class)}</td>
    <td>${esc(item.work_order || "—")}</td>
    <td>${esc(item.reported_next || "—")}</td>
    <td>${item.dispatch_authorized === false ? badge("DENY") : badge("UNKNOWN")}</td>
  </tr>`);

  document.querySelector("#agent-control-list").innerHTML = `
    <div class="callout">
      <strong>Global dispatch:</strong> ${badge(global.state)}
      <p>${esc(global.note || "")}</p>
    </div>
    <h3>Operator attention · max 3</h3>
    <div class="grid cards">${attentionCards}</div>
    <h3>Pending but blocked</h3>
    <div class="table-wrap">${table(["Slot", "Project", "Reported state", "Work order", "Blocker"], pendingRows)}</div>
    <h3>Registry-backed fleet</h3>
    <div class="table-wrap">${table(["Slot", "Project hint", "Reported", "Operational class", "Work order", "Reported next", "Dispatch"], slotRows)}</div>
  `;
}

function renderProjects(data) {
  document.querySelector("#projects-list").innerHTML = (data.projects || []).map((p) => `
    <article class="card">
      <div class="card-top"><strong>${esc(p.id)}</strong>${badge(p.state)}</div>
      <p><b>Owner:</b> ${esc(p.owner)}</p>
      <p><b>Next:</b> ${esc(p.next)}</p>
      <p class="muted"><b>Blocked by:</b> ${esc((p.blocked_by || []).join(", ") || "none")}</p>
    </article>`).join("");
}

function renderWork(data) {
  const rows = (data.work_items || []).map((w) => `<tr>
    <td><strong>${esc(w.id)}</strong></td>
    <td>${esc(w.project)}</td>
    <td>${esc(w.owner)}</td>
    <td>${badge(w.state)}</td>
    <td>${esc(w.effect_class)}</td>
    <td>${esc(w.human_gate)}</td>
    <td>${esc(w.next)}</td>
  </tr>`);
  document.querySelector("#work-list").innerHTML = table(["Work", "Project", "Owner", "State", "Effect", "Gate", "Next"], rows);
}

function renderReturns(data) {
  const rows = (data.returns || []).map((r) => `<tr>
    <td><strong>${esc(r.return_id)}</strong><br><span class="muted">${esc(r.project)}</span></td>
    <td>${badge(r.transport_status)}</td>
    <td>${badge(r.content_status)}</td>
    <td>${badge(r.apply_status)}</td>
    <td>${esc(r.note)}</td>
  </tr>`);
  const observations = (data.return_registry_observations || []).map((r) => `<tr>
    <td><strong>${esc(r.slot)}</strong></td>
    <td>${badge(r.reported_state)}</td>
    <td>${esc(r.work_order)}</td>
    <td>${esc(r.semantic_interpretation)}</td>
  </tr>`);
  const returnsTable = table(["Return", "Transport", "Semantic", "Apply", "Note"], rows);
  const registryTable = observations.length ? `<h3>Registry observations</h3>${table(["Slot", "Reported state", "Work order", "Authority"], observations)}` : "";
  document.querySelector("#returns-list").innerHTML = returnsTable + registryTable;
}

function renderDecisions(data) {
  document.querySelector("#decisions-list").innerHTML = (data.decisions || []).map((d) => `
    <article class="card">
      <div class="card-top"><strong>${esc(d.id)}</strong>${badge(d.state)}</div>
      <h3>${esc(d.decision)}</h3>
      <p><b>Owner:</b> ${esc(d.owner)}</p>
      <p><b>Effect:</b> ${esc(d.effect_state)}</p>
      <p><b>Readback:</b> ${esc(d.next_readback)}</p>
    </article>`).join("");
}

function renderCommercial(data) {
  const commercial = data.commercial || {};
  const cards = (commercial.active_sellable_lines || []).map((line) => `
    <article class="card">
      <div class="card-top"><strong>${esc(line.id)}</strong>${badge(line.state)}</div>
      <h3>$${esc(line.price_usd)}</h3>
    </article>`);
  const sprint = commercial.operator_sprint || {};
  cards.push(`
    <article class="card emphasis">
      <div class="card-top"><strong>Operator Sprint proof</strong>${badge(sprint.self_pilot_state)}</div>
      <p><b>External MVP:</b> ${esc(sprint.external_mvp_rule)}</p>
      <p><b>Self-pilot counts:</b> ${sprint.self_pilot_counts_toward_mvp === false ? "NO" : "UNKNOWN"}</p>
      <p><b>Roman:</b> ${esc(sprint.external_proof?.roman)}</p>
      <p><b>Payments:</b> ${esc(sprint.external_proof?.payments)}</p>
    </article>`);
  document.querySelector("#commercial-list").innerHTML = cards.join("");
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`);
  return response.json();
}

async function main() {
  const [data, agentControl] = await Promise.all([
    fetchJson(DATA_URL),
    fetchJson(AGENT_CONTROL_URL)
  ]);
  document.querySelector("#observed-at").textContent = `Observed ${data.observed_at} · ${data.projection_kind} · ${data.projection_source || "manual"}`;
  renderSafety(data);
  renderNowPending();
  renderAgents(data);
  renderAgentControl(agentControl);
  renderProjects(data);
  renderWork(data);
  renderReturns(data);
  renderDecisions(data);
  renderCommercial(data);
}

main().catch((error) => {
  document.querySelector("#now-cards").innerHTML = `<div class="error">${esc(error.message)}</div>`;
  console.error(error);
});
