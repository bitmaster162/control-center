const EFFECT_READBACK_URL = "../data/effect_readback_plane.generated.v1.json";

const effEsc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function effBadge(value) {
  const text = String(value ?? "UNKNOWN");
  const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="status status-${effEsc(key)}">${effEsc(text)}</span>`;
}

function effTable(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th>${effEsc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function renderEffectReadback(data) {
  const summary = data.summary || {};
  const candidates = data.effect_candidates || [];
  const executionReceipts = data.execution_receipts || [];
  const readbackReceipts = data.readback_receipts || [];

  const summaryCards = [
    ["Effect candidates", summary.effect_candidates_total],
    ["Effects authorized", summary.effects_authorized],
    ["Execution receipts", summary.execution_receipts],
    ["Closed after readback", summary.closed_after_readback]
  ].map(([label, value]) => `
    <article class="card">
      <div class="card-top"><strong>${effEsc(label)}</strong></div>
      <h3>${effEsc(value)}</h3>
    </article>`).join("");

  const candidateRows = candidates.map((c) => `<tr>
    <td><strong>${effEsc(c.work_order)}</strong><br><span class="muted">${effEsc(c.slot)}</span></td>
    <td>${effEsc(c.project)}</td>
    <td>${effBadge(c.stage)}</td>
    <td>${effEsc(c.gate)}</td>
    <td>${c.effect_authorized ? effBadge("YES") : effBadge("DENY")}</td>
    <td>${c.execution_authorized ? effBadge("YES") : effBadge("DENY")}</td>
    <td>${effEsc(c.execution_receipt_id || "—")}</td>
    <td>${effEsc(c.readback_receipt_id || "—")}</td>
    <td>${effBadge(c.apply_status)}</td>
  </tr>`);

  const executionRows = executionReceipts.map((r) => `<tr>
    <td><strong>${effEsc(r.receipt_id)}</strong></td>
    <td>${effEsc(r.decision_id)}</td>
    <td>${effEsc(r.work_order)}</td>
    <td>${effEsc(r.executed_at || r.observed_at || "—")}</td>
  </tr>`);

  const readbackRows = readbackReceipts.map((r) => `<tr>
    <td><strong>${effEsc(r.receipt_id)}</strong></td>
    <td>${effEsc(r.execution_receipt_id)}</td>
    <td>${effEsc(r.decision_id)}</td>
    <td>${effEsc(r.readback_at || r.observed_at || "—")}</td>
  </tr>`);

  const policy = data.policy || {};
  document.querySelector("#effect-readback-list").innerHTML = `
    <div class="callout">
      <strong>Receipt policy:</strong>
      receipt grants authority ${policy.receipt_never_grants_authority ? "NEVER" : "UNKNOWN"} ·
      auto-apply ${policy.auto_apply === false ? "DENY" : "UNKNOWN"} ·
      self-application ${policy.self_application === false ? "DENY" : "UNKNOWN"}
      <p>Execution requires prior explicit authority and its own receipt. Closure requires a separate post-effect readback receipt.</p>
    </div>
    <div class="grid cards">${summaryCards}</div>
    <h3>Effect candidates</h3>
    <div class="table-wrap">${effTable(["Work order / slot", "Project", "Stage", "Gate", "Effect auth", "Execution auth", "Execution receipt", "Readback receipt", "Apply"], candidateRows)}</div>
    <h3>Execution receipts</h3>
    <div class="table-wrap">${executionRows.length ? effTable(["Receipt", "Decision", "Work order", "Observed"], executionRows) : `<div class="empty">No execution receipts observed.</div>`}</div>
    <h3>Post-effect readbacks</h3>
    <div class="table-wrap">${readbackRows.length ? effTable(["Receipt", "Execution receipt", "Decision", "Observed"], readbackRows) : `<div class="empty">No post-effect readback receipts observed.</div>`}</div>
  `;
}

async function loadEffectReadback() {
  const response = await fetch(EFFECT_READBACK_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`effect/readback fetch failed: ${response.status}`);
  renderEffectReadback(await response.json());
}

loadEffectReadback().catch((error) => {
  const target = document.querySelector("#effect-readback-list");
  if (target) target.innerHTML = `<div class="error">${effEsc(error.message)}</div>`;
  console.error(error);
});
