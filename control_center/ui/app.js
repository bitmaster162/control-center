const DATA_URL = "../data/current_control_plane.seed.v1.json";

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

function renderNow(data) {
  const decisions = (data.decisions || []).slice(0, 3);
  document.querySelector("#now-cards").innerHTML = decisions.length
    ? decisions.map((d) => `
      <article class="card emphasis">
        <div class="card-top"><strong>${esc(d.id)}</strong>${badge(d.state)}</div>
        <h3>${esc(d.decision)}</h3>
        <p><b>Effect:</b> ${esc(d.effect_state)}</p>
        <p><b>Readback:</b> ${esc(d.next_readback)}</p>
      </article>`).join("")
    : `<div class="empty">No current human decisions.</div>`;
}

function renderAgents(data) {
  const rows = (data.agents || []).map((a) => `<tr>
    <td><strong>${esc(a.id)}</strong></td>
    <td>${esc(a.role)}</td>
    <td>${badge(a.state)}</td>
    <td>${esc(a.current_assignment)}</td>
  </tr>`);
  document.querySelector("#agents-list").innerHTML = table(["Agent / owner", "Role", "State", "Current assignment"], rows);
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
  document.querySelector("#returns-list").innerHTML = table(["Return", "Transport", "Semantic", "Apply", "Note"], rows);
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

async function main() {
  const response = await fetch(DATA_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`projection fetch failed: ${response.status}`);
  const data = await response.json();
  document.querySelector("#observed-at").textContent = `Observed ${data.observed_at} · ${data.projection_kind}`;
  renderSafety(data);
  renderNow(data);
  renderAgents(data);
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
