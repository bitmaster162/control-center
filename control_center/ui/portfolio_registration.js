(function (root) {
  "use strict";

  const CONTROL_URL = "../data/current_control_plane.generated.v1.json";
  const AGENT_CONTROL_URL = "../data/agent_control_plane.generated.v1.json";
  const IDENTITY_ADOPTIONS_URL = "../data/portfolio_identity_adoptions.current.v1.json";
  const REGISTRATION_EVIDENCE_URL = "../data/portfolio_operational_registration_evidence.candidate.v1.json";
  const EXPECTED_IDENTITY_APPROVAL = "APPROVE_MAWORLD_CURRENT_PORTFOLIO_IDENTITY_ADOPTION_R1";
  const PROPOSED_REGISTRATION_APPROVAL = "APPROVE_MAWORLD_OPERATIONAL_PROJECT_REGISTRATION_R1";

  const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  function badge(value) { const text = String(value ?? "UNKNOWN"); const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-"); return `<span class="status status-${esc(key)}">${esc(text)}</span>`; }
  function canonicalProjectId(value) { return String(value ?? "").toLowerCase().replaceAll(/[^a-z0-9]+/g, ""); }

  function validateEvidence(evidence) {
    if (!evidence || evidence.schema !== "control_center.portfolio_operational_registration_evidence.v1") throw new Error("portfolio operational-registration evidence schema mismatch");
    if (evidence.projection_kind !== "CANDIDATE_NON_AUTHORITY_OPERATIONAL_REGISTRATION_EVIDENCE") throw new Error("portfolio operational-registration evidence kind mismatch");
    const safety = evidence.safety || {};
    for (const key of ["authority_granted","operational_registration_authorized","owner_authority_granted","state_authority_granted","policy_binding_authorized","repair_authorized","dispatch_authorized","auto_fix_authorized","merge_authorized","deploy_authorized","runtime_mutation_authorized","self_application"]) {
      if (safety[key] !== false) throw new Error(`portfolio registration authority invariant mismatch:${key}`);
    }
    if (safety.can_trade !== false || safety.capital_permission !== "DENY") throw new Error("portfolio registration trading/capital invariant mismatch");
    return evidence;
  }

  function validateInputs(control, agentControl, identityAdoptions, evidence) {
    validateEvidence(evidence);
    if (!control || control.schema !== "control_center.current_control_plane_projection.v1" || control.projection_kind !== "NON_AUTHORITY_PROJECTION") throw new Error("portfolio registration control projection mismatch");
    if (!agentControl || agentControl.schema !== "control_center.agent_control_plane.v1" || agentControl.projection_kind !== "NON_AUTHORITY_PROJECTION") throw new Error("portfolio registration agent-control projection mismatch");
    if (!identityAdoptions || identityAdoptions.schema !== "control_center.portfolio_identity_adoptions.v1") throw new Error("portfolio registration identity-adoption schema mismatch");
    return { control, agentControl, identityAdoptions, evidence };
  }

  function hold(base, reasonCode, explanation) { return { ...base, classification: "HOLD", decision: "HOLD", reason_code: reasonCode, human_gate_required: true, explanation }; }

  function buildOperationalRegistrationGate(control, agentControl, identityAdoptions, evidence) {
    validateInputs(control, agentControl, identityAdoptions, evidence);
    const subject = evidence.subject || {}; const candidateId = canonicalProjectId(subject.canonical_id);
    const base = { schema: "control_center.portfolio_operational_registration_gate.v1", projection_kind: "NON_AUTHORITY_OPERATIONAL_REGISTRATION_GATE", subject_project: candidateId || null, display_name: subject.display_name || null, classification: "HOLD", decision: "HOLD", reason_code: "UNSET", owner_candidate: null, owner_authority_granted: false, proposed_state: null, proposed_blockers: [], proposed_next: null, source_baseline: null, source_baseline_fresh_for_implementation: false, current_return_bytes_bound: false, implementation_ready: false, repair_authorized: false, dispatch_authorized: false, operational_registration_authorized: false, execution_authority: "NONE", proposed_human_approval: PROPOSED_REGISTRATION_APPROVAL, human_gate_required: true };
    if (!candidateId || candidateId !== canonicalProjectId(subject.display_name)) return hold(base, "SUBJECT_IDENTITY_MISMATCH", ["Operational-registration subject does not canonicalize to the adopted project identity."]);
    if ((control.projects || []).some((project) => canonicalProjectId(project.id) === candidateId)) return hold(base, "PROJECT_ALREADY_OPERATIONALLY_REGISTERED", ["Current control projection already contains this operational project ID; duplicate registration is forbidden."]);
    if (evidence.source_binding?.control_observed_at !== control.observed_at || evidence.source_binding?.agent_control_observed_at !== agentControl.observed_at || evidence.source_binding?.canonical_generation !== control.canonical_current?.generation) return hold(base, "SOURCE_EPOCH_MISMATCH", ["Registration evidence is not bound to the exact captured control/agent-control epoch."]);
    const adoption = (identityAdoptions.adoptions || []).find((item) => canonicalProjectId(item.canonical_id) === candidateId) || null;
    if (!adoption) return hold(base, "CURRENT_IDENTITY_ADOPTION_MISSING", ["No current Portfolio identity adoption exists for the operational-registration subject."]);
    if (adoption.approval?.phrase !== EXPECTED_IDENTITY_APPROVAL || adoption.approval?.scope !== "CURRENT_PORTFOLIO_IDENTITY_ONLY" || adoption.result?.current_identity_state !== "CURRENT_PORTFOLIO_IDENTITY_ADOPTED" || adoption.result?.operational_project_registration !== "NOT_GRANTED") return hold(base, "CURRENT_IDENTITY_ADOPTION_INVALID", ["Identity adoption exists but does not preserve the bounded identity-only authority contract."]);
    const returnSource = evidence.current_return_registry || {}; const provenance = agentControl.source_provenance?.return_registry || {};
    if (returnSource.drive_file_id !== provenance.drive_file_id || returnSource.raw_sha256 !== provenance.raw_sha256 || returnSource.generation_label !== provenance.generation_label || returnSource.provider_modified_time !== provenance.provider_modified_time || returnSource.fetch_class !== "CURRENT_PROVIDER_BYTES") return hold(base, "RETURN_REGISTRY_BINDING_MISMATCH", ["Registration packet does not bind to the exact current Return Registry provider identity used by agent-control."]);
    const requiredSlots = evidence.operational_observations || [];
    if (requiredSlots.length < 2) return hold(base, "CURRENT_OPERATIONAL_EVIDENCE_INSUFFICIENT", ["At least two bounded MAWorld operational observations are required."]);
    const sourceSlots = new Map((agentControl.slots || []).map((slot) => [slot.slot, slot]));
    const observationMismatch = requiredSlots.find((row) => { const slot = sourceSlots.get(row.slot); return !slot || canonicalProjectId(slot.project_hint) !== candidateId || slot.reported_state !== row.reported_state || slot.work_order !== row.work_order || slot.reported_next !== row.reported_next || slot.dispatch_authorized !== false; });
    if (observationMismatch) return hold(base, "OPERATIONAL_OBSERVATION_MISMATCH", [`Operational observation ${observationMismatch.slot || "UNKNOWN"} does not reproduce current agent-control.`]);
    const codex = requiredSlots.find((row) => row.slot === "CODEX-03"); const reviewer = requiredSlots.find((row) => row.slot === "ANTIGRAVITY_WO041");
    if (!codex || !reviewer || codex.return_sha256 !== reviewer.verified_return_sha256) return hold(base, "INDEPENDENT_RETURN_BINDING_MISMATCH", ["CODEX-03 failure receipt is not hash-bound to the independent ANTIGRAVITY_WO041 acceptance observation."]);
    if (codex.reported_state !== "RLS_TEST_FAIL" || codex.harness_error_code !== "INITDB_FAILED" || codex.source_mutation !== false || codex.teardown !== "CLEAN" || reviewer.reported_state !== "ACCEPTANCE_VERIFIED_FAIL_INITDB" || reviewer.rerun_executed !== false) return hold(base, "CURRENT_FAILURE_EVIDENCE_INVALID", ["Current MAWorld failure evidence does not satisfy the bounded no-effect failure contract."]);
    const owner = evidence.owner_candidate || {}; const ownerSlot = sourceSlots.get(owner.id);
    if (owner.id !== "CODEX-03" || owner.authority_granted !== false || !Array.isArray(owner.evidence_sources) || owner.evidence_sources.length < 2 || !ownerSlot || canonicalProjectId(ownerSlot.project_hint) !== candidateId) return hold(base, "OWNER_CANDIDATE_NOT_EVIDENCED", ["A current owner candidate must be evidenced without promoting owner authority."]);
    const source = evidence.repository_identity || {};
    const exactBaseline = source.local_root === "C:\\PROJECTS\\MAWorld" && source.branch === "main" && source.head === "f82b9ccf880a9b781dac3273834a4d13a9062fc3" && source.tree === "1069056c9088f4b0b2db4822cd89dc118cc6a6da" && source.clean === true && source.github_repository === null && source.github_repository_status === "NOT_EVIDENCED";
    if (!exactBaseline) return hold(base, "REPOSITORY_IDENTITY_NOT_EXACT", ["Known MAWorld local Git baseline identity is incomplete or changed inside the registration packet."]);
    if (source.fresh_readback_required_before_implementation !== true) return hold(base, "FRESH_GIT_BASELINE_GATE_MISSING", ["Registration packet must preserve the fresh Git readback requirement before any persistent implementation."]);
    const proposal = evidence.registration_candidate || {}; const expectedBlockers = ["INITDB_FAILED_ROOT_CAUSE_UNRESOLVED","FRESH_GIT_BASELINE_READBACK_REQUIRED_BEFORE_IMPLEMENTATION"];
    if (proposal.state !== "FAILURE_DIAGNOSTIC_REQUIRED" || proposal.next !== "MAWORLD_INITDB_DIAGNOSTIC_REPAIR" || JSON.stringify(proposal.blocked_by) !== JSON.stringify(expectedBlockers) || proposal.owner_candidate !== "CODEX-03" || proposal.owner_authority_granted !== false || proposal.operational_registration_authorized !== false || proposal.implementation_ready !== false) return hold(base, "REGISTRATION_CANDIDATE_BOUNDARY_MISMATCH", ["Proposed operational row expands beyond the evidenced state/blocker/authority boundary."]);
    return { ...base, classification: "READY_FOR_HUMAN_OPERATIONAL_REGISTRATION", decision: "HUMAN_OPERATIONAL_REGISTRATION_GATE_READY", reason_code: "IDENTITY_CURRENT_RETURN_OWNER_CANDIDATE_AND_SOURCE_BASELINE_EVIDENCED", owner_candidate: owner.id, owner_authority_granted: false, proposed_state: proposal.state, proposed_blockers: proposal.blocked_by.slice(), proposed_next: proposal.next, source_baseline: `${source.local_root} @ ${source.branch} ${source.head}`, source_baseline_fresh_for_implementation: false, current_return_bytes_bound: true, implementation_ready: false, operational_registration_authorized: false, explanation: ["Current Portfolio identity adoption is present and remains identity-only.","Current Return Registry provider identity is hash-bound to agent-control and reproduces CODEX-03 plus independent ANTIGRAVITY_WO041 failure observations.","CODEX-03 is evidenced as the owner candidate, but current owner authority is not promoted by this gate.","Known local Git baseline is exact and clean at the last evidence capture, but it is not fresh enough to authorize implementation now.","Human approval may register the operational project metadata only; repair/implementation still requires a fresh Git baseline and a separate bounded action gate."] };
  }

  function renderGate(target, value) {
    const explanation = (value.explanation || []).map((item) => `<li>${esc(item)}</li>`).join(""); const blockers = (value.proposed_blockers || []).map((item) => `<li>${esc(item)}</li>`).join("");
    target.innerHTML = `<div class="callout"><strong>Operational Registration Gate · ${badge(value.classification)}</strong><p>Project: <b>${esc(value.subject_project)}</b> · owner candidate: <b>${esc(value.owner_candidate || "UNRESOLVED")}</b> · owner authority: ${badge(value.owner_authority_granted ? "GRANTED" : "NOT GRANTED")}.</p><p>Proposed state: <b>${esc(value.proposed_state || "HOLD")}</b> · next: <b>${esc(value.proposed_next || "NONE")}</b>.</p>${blockers ? `<p>Proposed blockers:</p><ul>${blockers}</ul>` : ""}<p>Git baseline fresh for implementation: ${badge(value.source_baseline_fresh_for_implementation ? "YES" : "NO")}. Implementation ready: ${badge(value.implementation_ready ? "YES" : "NO")}.</p><ul>${explanation}</ul><p class="muted">Candidate registration does not authorize owner authority, repair, dispatch, implementation, merge, deploy, runtime mutation, trading or capital use.</p></div>`;
    return value;
  }
  async function fetchJson(url) { const response = await fetch(url, { cache: "no-store" }); if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`); return response.json(); }
  async function boot() { const target = document.querySelector("#portfolio-registration-list"); if (!target) return; try { const [control, agentControl, identityAdoptions, evidence] = await Promise.all([fetchJson(CONTROL_URL),fetchJson(AGENT_CONTROL_URL),fetchJson(IDENTITY_ADOPTIONS_URL),fetchJson(REGISTRATION_EVIDENCE_URL)]); renderGate(target, buildOperationalRegistrationGate(control, agentControl, identityAdoptions, evidence)); } catch (error) { target.innerHTML = `<div class="error">Operational registration gate unavailable: ${esc(error.message)}</div>`; console.error(error); } }
  const api = { canonicalProjectId, validateEvidence, validateInputs, buildOperationalRegistrationGate, renderGate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioRegistration = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
