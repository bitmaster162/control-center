(() => {
  const snapshot = window.HANRI_SNAPSHOT;
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const toneClass = (tone) => ({ok:'badge-ok',warn:'badge-warn',danger:'badge-danger',info:'badge-info',neutral:'badge-neutral'}[tone] || 'badge-neutral');
  const operationalTone = (s) => ({OPERATIONAL:'ok',DEGRADED:'warn',HALTED:'danger',PLANNED:'info',MAINTENANCE:'warn',UNKNOWN:'neutral'}[s] || 'neutral');
  const evidenceTone = (state, freshness='CURRENT') => {
    if (state === 'CONFLICTED' || state === 'REJECTED') return 'danger';
    if (freshness === 'STALE') return 'warn';
    if (state === 'RECEIPTED' || state === 'HASH_VERIFIED') return freshness === 'CURRENT' ? 'ok' : 'warn';
    if (state === 'CLAIMED' || state === 'SOURCE_BACKED' || state === 'INFERRED') return 'warn';
    return 'neutral';
  };
  const securityTone = (status) => ({RECEIPTED_CLOSED:'ok',CLAIMED_NOT_RECEIPTED:'warn',OPEN:'danger',OPEN_REVERIFY:'danger',DEGRADED:'warn',UNKNOWN:'neutral'}[status] || 'neutral');
  const decisionTone = (status, evidence) => {
    if (status === 'REJECTED') return 'danger';
    if (status === 'DONE' || status === 'CLOSED' || status === 'ACTIVE') return evidenceTone(evidence);
    if (status === 'CLAIMED_NOT_RECEIPTED' || status === 'PENDING_CHANNEL' || status === 'STAGED') return 'warn';
    return 'neutral';
  };

  function evidenceBadge(state, freshness='CURRENT') {
    return `<span class="badge ${toneClass(evidenceTone(state, freshness))}">${esc(state)}${freshness === 'STALE' ? ' · STALE' : ''}</span>`;
  }

  function list(items) {
    return `<div class="list">${items.map(x => `<div class="list-item"><div class="card-top"><strong>${esc(x.title)}</strong>${x.evidence_state ? evidenceBadge(x.evidence_state) : ''}</div><span class="muted">${esc(x.text)}</span>${x.status ? `<div class="micro">${esc(x.status)}</div>` : ''}</div>`).join('')}</div>`;
  }

  function render() {
    const m = snapshot.meta;
    $('snapshot-subtitle').textContent = `${m.snapshot_id} · ${m.freshness.mode}/${m.freshness.state} · authority ${m.authority_generation} ${m.authority_status}`;
    $('contract-meta').textContent = `contract ${snapshot.contract.version}`;
    $('contract-meta').className = 'badge badge-info';
    $('global-mode').textContent = `${m.global_mode} · ${m.implementation_layer}`;
    $('global-mode').className = 'badge badge-info';
    $('kpis').innerHTML = snapshot.kpis.map(k => `<div class="kpi"><div class="value">${esc(k.value)}</div><div class="label">${esc(k.label)}</div><div class="kpi-badges"><span class="badge ${toneClass(k.tone)}">${esc(k.tone.toUpperCase())}</span>${evidenceBadge(k.evidence_state, k.freshness)}</div></div>`).join('');
    $('current-actions').innerHTML = list(snapshot.current_actions);
    $('blockers').innerHTML = list(snapshot.blockers);
    $('events').innerHTML = snapshot.events.map(e => `<div class="timeline-item"><div class="timeline-time">${esc(e.time)}</div><div><div class="card-top"><strong>${esc(e.title)}</strong>${evidenceBadge(e.evidence_state)}</div><div class="muted">${esc(e.text)}</div></div></div>`).join('');
    renderSystems();
    $('agents-table').innerHTML = table(['Слот','Роль','Статус','Канал','Память','Evidence'], snapshot.agents.map(a => [a.slot,a.role,a.status,a.channel,a.memory,`${a.evidence_state}/${a.freshness}`]));
    $('decisions-list').innerHTML = snapshot.decisions.map(d => `<div class="list-item"><div class="card-top"><strong>${esc(d.id)} · ${esc(d.action)}</strong><span class="badge ${toneClass(decisionTone(d.implementation_status, d.evidence_state))}">${esc(d.implementation_status)}</span></div><div class="muted">${esc(d.detail || '')}</div><div class="micro">${esc(d.verdict)} · ${esc(d.evidence_state)}</div></div>`).join('');
    $('memory-layers').innerHTML = snapshot.memory_layers.map(m => `<article class="memory-card"><div class="card-top"><h3>${esc(m.name)}</h3>${evidenceBadge(m.evidence_state)}</div><div class="card-tags"><span class="badge ${toneClass(m.status==='COMPLETE'?'ok':m.status==='DEGRADED'?'danger':'warn')}">${esc(m.status)}</span></div><p class="muted">${esc(m.description)}</p></article>`).join('');
    $('memory-contract').textContent = JSON.stringify(snapshot.memory_contract, null, 2);
    $('communications-flow').innerHTML = flow(snapshot.communication_flow);
    $('messages-table').innerHTML = table(['ID','От','Кому','Тип','Статус','Ref','Evidence'], snapshot.messages.map(m => [m.message_id,m.from,m.to,m.type,m.status,m.ref,m.evidence_state]));
    $('security-grid').innerHTML = snapshot.security.map(s => `<article class="security-card"><div class="card-top"><h3>${esc(s.id)} · ${esc(s.title)}</h3><span class="badge ${toneClass(securityTone(s.status))}">${esc(s.status)}</span></div><p class="muted">${esc(s.action)}</p><div class="micro">evidence: ${esc(s.evidence_state)}</div></article>`).join('');
    renderAudit();
    $('arbiter-summary').textContent = snapshot.arbiter_content.summary;
    $('arbiter-flow').innerHTML = flow(snapshot.arbiter_content.flow);
    $('arbiter-evidence').innerHTML = `<div class="list-item"><strong>${esc(snapshot.arbiter_content.evidence_status)}</strong><div class="muted">Источники: ${snapshot.arbiter_content.sources.map(esc).join(', ')}</div></div>`;
  }

  function renderSystems() {
    const q = ($('system-search')?.value || '').toLowerCase();
    const filter = $('system-status-filter')?.value || 'all';
    const filtered = snapshot.systems.filter(s => (filter === 'all' || s.operational === filter) && `${s.name} ${s.owner} ${s.next}`.toLowerCase().includes(q));
    $('systems-grid').innerHTML = filtered.map(s => `<article class="system-card"><div class="card-top"><h3>${esc(s.name)}</h3><span class="badge ${toneClass(operationalTone(s.operational))}">${esc(s.operational)}</span></div><div class="card-tags"><span class="badge badge-neutral">truth: ${esc(s.truth)}</span><span class="badge badge-neutral">mode: ${esc(s.execution)}</span>${evidenceBadge(s.evidence_state, s.freshness)}</div><p><strong>Owner:</strong> ${esc(s.owner)}</p><p><strong>Next:</strong> ${esc(s.next)}</p><p class="muted"><strong>Evidence refs:</strong> ${esc(s.evidence_refs.join(', '))}</p></article>`).join('') || '<div class="panel muted">Нет совпадений.</div>';
  }

  function renderAudit() {
    const a = snapshot.audit;
    $('audit-authority').innerHTML = objectCard(a.authority);
    $('audit-hanri').innerHTML = objectCard(a.hanri_decision_loop);
    $('audit-p0').innerHTML = table(['P0','Статус','Required evidence'], a.p0_receipts.map(p => [p.id,p.status,(p.required || []).join(', ')]));
    $('audit-defects').innerHTML = table(['Defect','Статус','Summary'], a.defects.map(d => [d.id,d.status,d.summary]));
    $('audit-acceptance').innerHTML = `<div class="list">${a.acceptance.map(x => `<div class="list-item"><div class="card-top"><strong>${esc(x.artifact)}</strong><span class="badge ${toneClass(x.status==='PASS'||x.status==='ACCEPTED'?'ok':'warn')}">${esc(x.status)}</span></div><div class="muted">${esc((x.checks || []).join(' · '))}</div>${x.sha256 ? `<div class="micro mono">${esc(x.sha256)}</div>` : ''}</div>`).join('')}</div>`;
    $('audit-invariants').innerHTML = a.invariants.map(v => `<span class="badge badge-neutral">${esc(v)}</span>`).join('');
  }

  function objectCard(obj) {
    return `<div class="kv-grid">${Object.entries(obj).map(([k,v]) => `<div class="kv"><span>${esc(k)}</span><strong>${esc(Array.isArray(v) ? v.join(', ') : typeof v === 'object' ? JSON.stringify(v) : v)}</strong></div>`).join('')}</div>`;
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
