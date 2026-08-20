const WORK_LIFECYCLE_URL = "../data/work_order_lifecycle.generated.v1.json";

const lifeEsc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function lifeBadge(value) {
  const text = String(value ?? "UNKNOWN");
  const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="status status-${lifeEsc(key)}">${lifeEsc(text)}</span>`;
}

function lifeTable(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th>${lifeEsc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function renderLifecycle(data) {
  const summary = data.summary || {};
  const policy = data.global_policy || {};
  const rows = data.work_orders || [];
  const divergences = data.source_divergences || [];

  const summaryCards = [
    ["Work orders", summary.work_orders_total],
    ["Semantic accepted", summary.semantic_accepted],
    ["Applied", summary.applied],
    ["Source divergences", summary.source_divergences]
  ].map(([label, value]) => `
    <article class="card">
      <div class="card-top"><strong>${lifeEsc(label)}</strong></div>
      <h3>${lifeEsc(value)}</h3>
    </article>`).join("");

  const lifecycleRows = rows.map((row) => `<tr>
    <td><strong>${lifeEsc(row.work_order)}</strong><br><span class="muted">${lifeEsc(row.slot)}</span>${row.do_not_touch ? `<br><span class="muted">DO NOT TOUCH</span>` : ""}</td>
    <td>${lifeEsc(row.project)}</td>
    <td>${lifeBadge(row.lifecycle_stage)}</td>
    <td>${lifeBadge(row.transport_status)}</td>
    <td>${lifeBadge(row.semantic_status)}</td>
    <td>${lifeBadge(row.apply_status)}</td>
    <td>${lifeEsc(row.effect_gate)}</td>
    <td>${lifeEsc(row.readback_status)}</td>
  </tr>`);

  const divergenceRows = divergences.map((row) => `<tr>
    <td><strong>${lifeEsc(row.slot)}</strong></td>
    <td>${lifeBadge(row.kind)}</td>
    <td>${lifeEsc((row.work_orders || []).join(", "))}</td>
    <td>${lifeEsc(row.action)}</td>
  </tr>`);

  document.querySelector("#work-lifecycle-list").innerHTML = `
    <div class="callout">
      <strong>Lifecycle policy:</strong>
      auto-dispatch ${policy.auto_dispatch === false ? "DENY" : "UNKNOWN"} ·
      auto-accept ${policy.auto_accept === false ? "DENY" : "UNKNOWN"} ·
      auto-apply ${policy.auto_apply === false ? "DENY" : "UNKNOWN"}
      <p>Chain: ${lifeEsc((data.chain || []).join(" → "))}</p>
    </div>
    <div class="grid cards">${summaryCards}</div>
    <h3>Work-order lifecycle</h3>
    <div class="table-wrap">${lifeTable(["Work order / slot", "Project", "Stage", "Transport", "Semantic", "Apply", "Effect gate", "Readback"], lifecycleRows)}</div>
    <h3>Source/version divergences</h3>
    <div class="table-wrap">${lifeTable(["Slot", "Divergence", "Work orders", "Rule"], divergenceRows)}</div>
  `;
}

async function loadLifecycle() {
  const response = await fetch(WORK_LIFECYCLE_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`lifecycle fetch failed: ${response.status}`);
  renderLifecycle(await response.json());
}

loadLifecycle().catch((error) => {
  const target = document.querySelector("#work-lifecycle-list");
  if (target) target.innerHTML = `<div class="error">${lifeEsc(error.message)}</div>`;
  console.error(error);
});
