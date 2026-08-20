const EXECUTION_SCOPE_URL = "../data/execution_scope_binder.generated.v1.json";

const esEsc = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function esBadge(value) {
  const text = String(value ?? "UNKNOWN");
  const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
  return `<span class="status status-${esEsc(key)}">${esEsc(text)}</span>`;
}

function renderExecutionScope(data) {
  const runtime = data.canonical_runtime || {};
  const binding = data.binding || {};
  const divergences = data.source_divergences || [];
  const blockers = binding.blockers || [];
  document.querySelector("#execution-scope-list").innerHTML = `
    <div class="callout">
      <strong>Verdict:</strong> ${esBadge(data.verdict)}
      <p>Canonical snapshot: broker ${esEsc(runtime.broker_status)} · watcher ${esEsc(runtime.watcher_generation)} · fresh liveness ${esEsc(runtime.runtime_liveness_current)}</p>
    </div>
    <div class="grid cards">
      <article class="card"><strong>Human gates</strong><h3>${esEsc(binding.current_human_gate_count)}</h3></article>
      <article class="card"><strong>Effect candidates</strong><h3>${esEsc(binding.current_effect_candidate_count)}</h3></article>
      <article class="card"><strong>Execution scope</strong><h3>${binding.execution_scope_bound === false ? "UNBOUND" : "UNKNOWN"}</h3></article>
      <article class="card"><strong>Execution authority</strong><h3>${binding.execution_authorized === false ? "DENY" : "UNKNOWN"}</h3></article>
    </div>
    <h3>Fail-closed blockers</h3>
    <div class="callout">${blockers.map((x) => `<span class="pill">${esEsc(x)}</span>`).join(" ")}</div>
    <h3>Source divergence</h3>
    ${divergences.length ? divergences.map((d) => `<article class="card"><strong>${esEsc(d.id)}</strong><p><b>Historical:</b> ${esEsc(d.historical_claim)}</p><p><b>Canonical:</b> ${esEsc(d.canonical_claim)}</p><p><b>Rule:</b> ${esEsc(d.routing_rule)}</p></article>`).join("") : `<div class="empty">No source divergence.</div>`}
    <h3>Next read-only action</h3>
    <div class="callout"><strong>${esEsc(data.next_read_only_action)}</strong><p>This is evidence collection only; it grants no execution authority.</p></div>
  `;
}

async function loadExecutionScope() {
  const response = await fetch(EXECUTION_SCOPE_URL, { cache: "no-store" });
  if (!response.ok) throw new Error(`execution scope fetch failed: ${response.status}`);
  renderExecutionScope(await response.json());
}

loadExecutionScope().catch((error) => {
  const target = document.querySelector("#execution-scope-list");
  if (target) target.innerHTML = `<div class="error">${esEsc(error.message)}</div>`;
  console.error(error);
});
