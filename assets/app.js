(() => {
  const snapshot = window.HANRI_SNAPSHOT;
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const toneClass = (tone) => ({ok:'badge-ok',warn:'badge-warn',danger:'badge-danger',info:'badge-info'}[tone] || 'badge-neutral');
  const operationalTone = (s) => ({operational:'ok',degraded:'warn',halted:'danger',planned:'info',maintenance:'warn',unknown:'neutral'}[s] || 'neutral');

  function list(items) {
    return `<div class="list">${items.map(x => `<div class="list-item"><strong>${esc(x.title)}</strong><span class="muted">${esc(x.text)}</span></div>`).join('')}</div>`;
  }

  function render() {
    $('snapshot-subtitle').textContent = `${snapshot.meta.snapshot_id} · ${snapshot.meta.freshness} · ${snapshot.meta.current_generation_verification}`;
    $('global-mode').textContent = snapshot.meta.global_mode;
    $('global-mode').className = 'badge badge-info';
    $('kpis').innerHTML = snapshot.kpis.map(k => `<div class="kpi"><div class="value">${esc(k.value)}</div><div class="label">${esc(k.label)}</div><span class="badge ${toneClass(k.tone)}">${esc(k.tone.toUpperCase())}</span></div>`).join('');
    $('current-actions').innerHTML = list(snapshot.current_actions);
    $('blockers').innerHTML = list(snapshot.blockers);
    $('events').innerHTML = snapshot.events.map(e => `<div class="timeline-item"><div class="timeline-time">${esc(e.time)}</div><div><strong>${esc(e.title)}</strong><div class="muted">${esc(e.text)}</div></div></div>`).join('');
    renderSystems();
    $('agents-table').innerHTML = table(['Слот','Роль','Статус','Канал','Память'], snapshot.agents.map(a => [a.slot,a.role,a.status,a.channel,a.memory]));
    $('decisions-list').innerHTML = snapshot.decisions.map(d => `<div class="list-item"><div class="card-top"><strong>${esc(d.id)} · ${esc(d.action)}</strong><span class="badge badge-ok">${esc(d.verdict)}</span></div><div class="muted">${esc(d.implementation)}</div></div>`).join('');
    $('memory-layers').innerHTML = snapshot.memory_layers.map(m => `<article class="memory-card"><div class="card-top"><h3>${esc(m.name)}</h3><span class="badge ${m.status==='evidenced'?'badge-ok':'badge-warn'}">${esc(m.status)}</span></div><p class="muted">${esc(m.description)}</p></article>`).join('');
    $('memory-contract').textContent = JSON.stringify(snapshot.memory_contract, null, 2);
    $('communications-flow').innerHTML = flow(snapshot.communication_flow);
    $('messages-table').innerHTML = table(['От','Кому','Тип','Статус','Ref'], snapshot.messages.map(m => [m.from,m.to,m.type,m.status,m.ref]));
    $('security-grid').innerHTML = snapshot.security.map(s => `<article class="security-card"><div class="card-top"><h3>${esc(s.id)} · ${esc(s.title)}</h3><span class="badge badge-danger">${esc(s.status)}</span></div><p class="muted">${esc(s.action)}</p></article>`).join('');
    $('arbiter-summary').textContent = snapshot.arbiter_content.summary;
    $('arbiter-flow').innerHTML = flow(snapshot.arbiter_content.flow);
    $('arbiter-evidence').innerHTML = `<div class="list-item"><strong>${esc(snapshot.arbiter_content.evidence_status)}</strong><div class="muted">Источники: ${snapshot.arbiter_content.sources.map(esc).join(', ')}</div></div>`;
  }

  function renderSystems() {
    const q = ($('system-search')?.value || '').toLowerCase();
    const filter = $('system-status-filter')?.value || 'all';
    const filtered = snapshot.systems.filter(s => (filter === 'all' || s.operational === filter) && `${s.name} ${s.owner} ${s.next}`.toLowerCase().includes(q));
    $('systems-grid').innerHTML = filtered.map(s => `<article class="system-card"><div class="card-top"><h3>${esc(s.name)}</h3><span class="badge ${toneClass(operationalTone(s.operational))}">${esc(s.operational)}</span></div><div class="card-tags"><span class="badge badge-neutral">truth: ${esc(s.truth)}</span><span class="badge badge-neutral">mode: ${esc(s.execution)}</span></div><p><strong>Owner:</strong> ${esc(s.owner)}</p><p><strong>Next:</strong> ${esc(s.next)}</p><p class="muted"><strong>Evidence:</strong> ${esc(s.evidence)}</p></article>`).join('') || '<div class="panel muted">Нет совпадений.</div>';
  }

  function table(headers, rows) {
    return `<table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }

  function flow(items) {
    return items.map((v, i) => `<div class="flow-node">${esc(v)}</div>${i < items.length - 1 ? '<div class="flow-arrow">→</div>' : ''}`).join('');
  }

  document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.view').forEach(x => x.classList.remove('active'));
    btn.classList.add('active');
    $(`view-${btn.dataset.view}`).classList.add('active');
  }));
  $('system-search').addEventListener('input', renderSystems);
  $('system-status-filter').addEventListener('change', renderSystems);
  $('refresh-btn').addEventListener('click', () => location.reload());
  render();
})();
