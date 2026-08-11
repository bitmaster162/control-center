const HUMAN_GATE_PACKETS_URL = "../data/human_gate_packets.generated.v1.json";

const hgpEsc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function hgpBadge(value) {
  const text = String(value ?? "UNKNOWN");
  const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="status status-${hgpEsc(key)}">${hgpEsc(text)}</span>`;
}

function hgpTable(headers, rows) {
  return `<table><thead><tr>${headers.map((h) => `<th>${hgpEsc(h)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function renderHumanGatePackets(data) {
  const packets = data.packets || [];
  const summary = data.summary || {};
  const policy = data.policy || {};

  const now = packets.length ? packets.map((packet) => {
    const scope = packet.effect_scope || {};
    const current = packet.current_state || {};
    return `
      <article class="card emphasis">
        <div class="card-top"><strong>${hgpEsc(packet.work_order)}</strong>${hgpBadge(packet.status)}</div>
        <h3>${hgpEsc(packet.project)}</h3>
        <p><b>Gate:</b> ${hgpEsc(packet.gate)}</p>
        <p><b>Allowed:</b> ${hgpEsc((packet.allowed_responses || []).map((x) => x.response).join(" / "))}</p>
        <p><b>Current:</b> semantic ${hgpEsc(current.semantic)} · apply ${hgpEsc(current.apply)} · effect ${current.effect_authorized === false ? "DENY" : "UNKNOWN"} · execution ${current.execution_authorized === false ? "DENY" : "UNKNOWN"}</p>
        <p><b>Execution-ready:</b> ${scope.execution_ready === false ? "NO" : "UNKNOWN"}</p>
        <p><b>Why not:</b> ${hgpEsc((scope.readiness_blockers || []).join(" · "))}</p>
        <p><b>Executor:</b> ${hgpEsc(packet.executor_binding?.state || "UNKNOWN")}</p>
      </article>`;
  }).join("") : `<div class="empty">No Human Gate Packets. Nothing is ripe for Robert.</div>`;

  const packetCards = packets.map((packet) => {
    const scope = packet.effect_scope || {};
    const authorize = (packet.allowed_responses || []).find((x) => x.response === "AUTHORIZE_APPLY") || {};
    return `
      <article class="card emphasis">
        <div class="card-top"><strong>${hgpEsc(packet.packet_id)}</strong>${hgpBadge(packet.status)}</div>
        <h3>${hgpEsc(packet.gate)}</h3>
        <p><b>Scope:</b> ${hgpEsc(scope.scope_statement)}</p>
        <p><b>Operation bound:</b> ${scope.operation_details_bound === false ? "NO" : "UNKNOWN"}</p>
        <p><b>Provider target bound:</b> ${scope.provider_target_bound === false ? "NO" : "UNKNOWN"}</p>
        <p><b>Executor:</b> ${hgpEsc(packet.executor_binding?.state)}</p>
        <p><b>AUTHORIZE_APPLY gives:</b> ${hgpEsc(authorize.effect_authority_result)}</p>
        <p><b>Execution authority:</b> ${hgpEsc(authorize.execution_authority_result)}</p>
        <p><b>Next required:</b> ${hgpEsc((authorize.next_required || []).join(" → "))}</p>
      </article>`;
  }).join("");

  const responseRows = packets.flatMap((packet) => (packet.allowed_responses || []).map((response) => `<tr>
    <td><strong>${hgpEsc(packet.work_order)}</strong></td>
    <td>${hgpBadge(response.response)}</td>
    <td>${hgpEsc(response.effect_authority_result)}</td>
    <td>${hgpEsc(response.execution_authority_result)}</td>
    <td>${hgpEsc(response.apply_state_result)}</td>
    <td>${hgpEsc((response.next_required || []).join(" → "))}</td>
  </tr>`));

  const evidenceRows = packets.flatMap((packet) => (packet.evidence_bindings || []).map((binding) => `<tr>
    <td><strong>${hgpEsc(binding.source)}</strong></td>
    <td>${hgpEsc(binding.identity)}</td>
    <td>${hgpEsc(binding.schema)}</td>
    <td>${hgpEsc((binding.claims || []).join(" · "))}</td>
  </tr>`));

  const target = document.querySelector("#human-gate-packets-list");
  if (target) {
    target.innerHTML = `
      <div class="callout">
        <strong>Human gate policy:</strong>
        packet grants authority ${policy.packet_grants_authority === false ? "NO" : "UNKNOWN"} ·
        generic continuation authorizes effect ${policy.generic_continuation_is_authorization === false ? "NO" : "UNKNOWN"} ·
        auto-execute ${policy.auto_execute === false ? "DENY" : "UNKNOWN"}
        <p>Current packets: ${hgpEsc(summary.packets_total)} · execution-ready: ${hgpEsc(summary.execution_ready_packets)}. A packet explains a gate; it does not execute it.</p>
      </div>
      <div class="grid cards">${packetCards || `<div class="empty">No open Human Gate Packets.</div>`}</div>
      <h3>Decision consequences</h3>
      <div class="table-wrap">${hgpTable(["Work order", "Response", "Effect authority", "Execution authority", "Apply", "Next required"], responseRows)}</div>
      <h3>Evidence bindings</h3>
      <div class="table-wrap">${hgpTable(["Source", "Identity", "Schema", "Bound claims"], evidenceRows)}</div>
    `;
  }

  const nowTarget = document.querySelector("#now-cards");
  if (nowTarget) nowTarget.innerHTML = now;
  window.__controlCenterHumanGatePackets = data;
  window.dispatchEvent(new CustomEvent("control-center:human-gate-packets", { detail: data }));
}

async function loadHumanGatePackets() {
  const response = await fetch(HUMAN_GATE_PACKETS_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`human gate packets fetch failed: ${response.status}`);
  renderHumanGatePackets(await response.json());
}

loadHumanGatePackets().catch((error) => {
  const target = document.querySelector("#human-gate-packets-list");
  if (target) target.innerHTML = `<div class="error">${hgpEsc(error.message)}</div>`;
  console.error(error);
});
