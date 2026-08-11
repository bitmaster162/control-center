const COMMAND_QUEUE_URL = "../data/command_queue.generated.v1.json";

const cqEsc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function cqBadge(value) {
  const text = String(value ?? "UNKNOWN");
  const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="status status-${cqEsc(key)}">${cqEsc(text)}</span>`;
}

function cqTable(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th>${cqEsc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function workFromCommand(commandId) {
  return String(commandId || "").replace(/^CMD::/, "");
}

function renderCommandQueue(data) {
  const summary = data.summary || {};
  const queues = data.queues || {};
  const policy = data.policy || {};
  const attention = data.attention_routing || [];
  const divergences = data.provenance_divergences || [];

  const summaryCards = [
    ["Human NOW", summary.human_now],
    ["Control Center", summary.control_center_queue],
    ["Owner-only", summary.project_owner_queue],
    ["Blocked", summary.blocked_queue]
  ].map(([label, value]) => `
    <article class="card">
      <div class="card-top"><strong>${cqEsc(label)}</strong></div>
      <h3>${cqEsc(value)}</h3>
    </article>`).join("");

  const queueRows = ["HUMAN_NOW", "CONTROL_CENTER_QUEUE", "PROJECT_OWNER_QUEUE", "BLOCKED_QUEUE"]
    .flatMap((queue) => (queues[queue] || []).map((commandId, index) => `<tr>
      <td>${cqEsc(index + 1)}</td>
      <td>${cqBadge(queue)}</td>
      <td><strong>${cqEsc(workFromCommand(commandId))}</strong></td>
      <td>${cqEsc(commandId)}</td>
    </tr>`));

  const attentionRows = attention.map((item) => `<tr>
    <td>${cqEsc(item.rank)}</td>
    <td><strong>${cqEsc(item.work_order)}</strong></td>
    <td>${cqBadge(item.queue)}</td>
    <td>${cqEsc(item.reason)}</td>
  </tr>`);

  const divergenceRows = divergences.map((item) => `<tr>
    <td><strong>${cqEsc(item.work_order)}</strong><br><span class="muted">${cqEsc(item.slot)}</span></td>
    <td>${cqEsc(item.lifecycle_reported_state)}</td>
    <td>${cqEsc(item.slot_reported_state_observation)}</td>
    <td>${cqEsc(item.action)}</td>
  </tr>`);

  document.querySelector("#command-queue-list").innerHTML = `
    <div class="callout">
      <strong>Routing only:</strong>
      queue grants authority ${policy.queue_grants_authority === false ? "NO" : "UNKNOWN"} ·
      auto-dispatch ${policy.auto_dispatch === false ? "DENY" : "UNKNOWN"} ·
      auto-apply ${policy.auto_apply === false ? "DENY" : "UNKNOWN"} ·
      auto-execute ${policy.auto_execute === false ? "DENY" : "UNKNOWN"}
      <p>Priority controls what is surfaced or routed. It never authorizes execution.</p>
    </div>
    <div class="grid cards">${summaryCards}</div>
    <h3>Unified routing order</h3>
    <div class="table-wrap">${cqTable(["Queue rank", "Queue", "Work order", "Command ID"], queueRows)}</div>
    <h3>Compressed attention routing</h3>
    <div class="table-wrap">${cqTable(["Rank", "Work order", "Route", "Reason"], attentionRows)}</div>
    <h3>Preserved provenance divergence</h3>
    <div class="table-wrap">${cqTable(["Work order / slot", "Lifecycle state", "Slot observation", "Rule"], divergenceRows)}</div>
  `;

  window.__controlCenterCommandQueue = data;
  window.dispatchEvent(new CustomEvent("control-center:command-queue", { detail: data }));
}

async function loadCommandQueue() {
  const response = await fetch(COMMAND_QUEUE_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`command queue fetch failed: ${response.status}`);
  renderCommandQueue(await response.json());
}

loadCommandQueue().catch((error) => {
  const target = document.querySelector("#command-queue-list");
  if (target) target.innerHTML = `<div class="error">${cqEsc(error.message)}</div>`;
  console.error(error);
});
