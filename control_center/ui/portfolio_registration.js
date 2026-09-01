(function (root) {
  "use strict";

  const CONTROL_URL = "../data/current_control_plane.generated.v1.json";
  const AGENT_CONTROL_URL = "../data/agent_control_plane.generated.v1.json";
  const IDENTITY_ADOPTIONS_URL = "../data/portfolio_identity_adoptions.current.v1.json";
  const REGISTRATION_EVIDENCE_URL = "../data/portfolio_operational_registration_evidence.candidate.v1.json";
  const REGISTRATIONS_URL = "../data/portfolio_operational_registrations.current.v1.json";
  const EXPECTED_IDENTITY_APPROVAL = "APPROVE_MAWORLD_CURRENT_PORTFOLIO_IDENTITY_ADOPTION_R1";
  const EXPECTED_REGISTRATION_APPROVAL = "APPROVE_MAWORLD_OPERATIONAL_PROJECT_REGISTRATION_R1";

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

  function validateRegistrations(registrations) {
    if (!registrations || registrations.schema !== "control_center.portfolio_operational_registrations.v1") throw new Error("portfolio operational registrations schema mismatch");
    if (registrations.projection_kind !== "HUMAN_APPROVED_NON_EXECUTION_OPERATIONAL_REGISTRATION_OVERLAY") throw new Error("portfolio operational registrations kind mismatch");
    const safety = registrations.safety || {};
    if (safety.approval_authority_consumed_for_metadata_write !== true || safety.downstream_authority_granted !== false) throw new Error("portfolio operational registration approval boundary mismatch");
    for (const key of ["owner_authority_granted","policy_authority_granted","repair_authorized","dispatch_authorized","auto_fix_authorized","merge_authorized","deploy_authorized","runtime_mutation_authorized","self_application"]) {
      if (safety[key] !== false) throw new Error(`portfolio operational registration downstream authority mismatch:${key}`);
    }
    if (safety.can_trade !== false || safety.capital_permission !== "DENY") throw new Error("portfolio operational registration trading/capital invariant mismatch");
    for (const item of registrations.registrations || []) {
      if (item.approval?.phrase !== EXPECTED_REGISTRATION_APPROVAL || item.approval?.scope !== "CURRENT_PORTFOLIO_OPERATIONAL_REGISTRATION_ONLY") throw new Error("portfolio operational registration approval mismatch");
      if (item.identity_binding?.approval_phrase !== EXPECTED_IDENTITY_APPROVAL || item.identity_binding?.current_identity_state !== "CURRENT_PORTFOLIO_IDENTITY_ADOPTED") throw new Error("portfolio operational registration identity binding mismatch");
      if (item.result?.current_operational_registration !== "CURRENT_PORTFOLIO_OPERATIONALLY_REGISTERED" || item.result?.owner_authority !== "NOT_GRANTED" || item.result?.policy_binding_authority !== "NOT_GRANTED" || item.result?.implementation_authority !== "NOT_GRANTED" || item.result?.repair_authority !== "NOT_GRANTED" || item.result?.execution_authority !== "NONE") throw new Error("portfolio operational registration result boundary mismatch");
      const metadata = item.operational_metadata || {};
      if (metadata.owner_authority_granted !== false || metadata.policy_bound !== false || metadata.source_baseline_fresh_for_implementation !== false || metadata.implementation_ready !== false || metadata.repair_authorized !== false) throw new Error("portfolio operational registration metadata authority mismatch");
    }
    return registrations;
  }

  function validateInputs(control, agentControl, identityAdoptions, evidence) {
    validateEvidence(evidence);
    if (!control || control.schema !== "control_center.current_control_plane_projection.v1" || control.projection_kind !== "NON_AUTHORITY_PROJECTION") throw new Error("portfolio registration control projection mismatch");
    if (!agentControl || agentControl.schema !== "control_center.agent_control_plane.v1" || agentControl.projection_kind !== "NON_AUTHORITY_PROJECTION") throw new Error("portfolio registration agent-control projection mismatch");
    if (!identityAdoptions || identityAdoptions.schema !== "control_center.portfolio_identity_adoptions.v1") throw new Error("portfolio registration identity-adoption schema mismatch");
    return { control, agentControl, identityAdoptions, evidence };
  }

  function hold(base, reasonCode, explanation) { return { ...base, classification: "HOLD", decision: "HOLD", reason_code: reasonCode, human_gate_required: true, explanation }; }
  function findRegistration(registrations, candidateId) { if (!registrations) return null; validateRegistrations(registrations); return (registrations.registrations || []).find((item) => canonicalProjectId(item.canonical_id) === candidateId) || null; }

  function buildOperationalRegistrationGate(control, agentControl, identityAdoptions, evidence, registrations = null) {
    validateInputs(control, agentControl, identityAdoptions, evidence);
    const subject = evidence.subject || {}; const candidateId = canonicalProjectId(subject.canonical_id);
    const base = { schema: "control_center.portfolio_operational_registration_gate.v2", projection_kind: "NON_AUTHORITY_OPERATIONAL_REGISTRATION_GATE", subject_project: candidateId || null, display_name: subject.display_name || null, classification: "HOLD", decision: "HOLD", reason_code: "UNSET", owner_candidate: null, owner_authority_granted: false, proposed_state: null, proposed_blockers: [], proposed_next: null, source_baseline: null, source_baseline_fresh_for_implementation: false, current_return_bytes_bound: false, implementation_ready: false, repair_authorized: false, dispatch_authorized: false, operational_registration_authorized: false, operational_registration_applied: false, execution_authority: "NONE", proposed_human_approval: EXPECTED_REGISTRATION_APPROVAL, human_gate_required: true };
    if (!candidateId || candidateId !== canonicalProjectId(subject.display_name)) return hold(base, "SUBJECT_IDENTITY_MISMATCH", ["Operational-registration subject does not canonicalize to the adopted project identity."]);
    if ((control.projects || []).some((project) => canonicalProjectId(project.id) === candidateId)) return hold(base, "PROJECT_ALREADY_OPERATIONALLY_REGISTERED", ["Current provider control projection already contains this project ID; duplicate overlay registration is forbidden."]);
    if (evidence.source_binding?.control_observed_at !== control.observed_at || evidence.source_binding?.agent_control_observed_at !== agentControl.observed_at || evidence.source_binding?.canonical_generation !== control.canonical_current?.generation) return hold(base, "SOURCE_EPOCH_MISMATCH", ["Registration evidence is not bound to the exact captured control/agent-control epoch."]);
    const adoption = (identityAdoptions.adoptions || []).find((item) => canonicalProjectId(item.canonical_id) === candidateId) || null;
    if (!adoption) return hold(base, "CURRENT_IDENTITY_ADOPTION_MISSING", ["No current Portfolio identity adoption exists for the operational-registration subject."]);
    if (adoption.approval?.phrase !== EXPECTED_IDENTITY_APPROVAL || adoption.approval?.scope !== "CURRENT_PORTFOLIO_IDENTITY_ONLY" || adoption.result?.current_identity_state !== "CURRENT_PORTFOLIO_IDENTITY_ADOPTED") return hold(base, "CURRENT_IDENTITY_ADOPTION_INVALID", ["Identity adoption does not preserve the bounded identity contract."]);
    const returnSource = evidence.current_return_registry || {}; const provenance = agentControl.source_provenance?.return_registry || {};
    if (returnSource.drive_file_id !== provenance.drive_file_id || returnSource.raw_sha256 !== provenance.raw_sha256 || returnSource.generation_label !== provenance.generation_label || returnSource.provider_modified_time !== provenance.provider_modified_time || returnSource.fetch_class !== "CURRENT_PROVIDER_BYTES") return hold(base, "RETURN_REGISTRY_BINDING_MISMATCH", ["Registration packet does not bind to the exact current Return Registry provider identity used by agent-control."]);
    const requiredSlots = evidence.operational_observations || [];
    if (requiredSlots.length < 2) return hold(base, "CURRENT_OPERATIONAL_EVIDENCE_INSUFFICIENT", ["At least two bounded MAWorld operational observations are required."]);
    const sourceSlots = new Map((agentControl.slots || []).map((slot) => [slot.slot, slot]));
    const observationMismatch = requiredSlots.find((row) => { const slot = sourceSlots.get(row.slot); return !slot || canonicalProjectId(slot.project_hint) !== candidateId || slot.reported_state !== row.reported_state || slot.work_order !== row.work_order || slot.reported_next !== row.reported_next || slot.dispatch_authorized !== false; });
    if (observationMismatch) return hold(base, "OPERATIONAL_OBSERVATION_MISMATCH", [`Operational observation ${observationMismatch.slot || "UNKNOWN"} does not reproduce current agent-control.`]);
    const codex = requiredSlots.find((row) => row.slot === "CODEX-03"); const reviewer = requiredSlots.find((row) => row.slot === "ANTIGRAVITY_WO041");
    if (!codex || !reviewer || codex.return_sha256 !== reviewer.verified_return_sha256) return hold(base, "INDEPENDENT_RETURN_BINDING_MISMATCH", ["CODEX-03 failure receipt is not hash-bound to the independent ANTIGRAVITY_WO041 observation."]);
    if (codex.reported_state !== "RLS_TEST_FAIL" || codex.harness_error_code !== "INITDB_FAILED" || codex.source_mutation !== false || codex.teardown !== "CLEAN" || reviewer.reported_state !== "ACCEPTANCE_VERIFIED_FAIL_INITDB" || reviewer.rerun_executed !== false) return hold(base, "CURRENT_FAILURE_EVIDENCE_INVALID", ["Current MAWorld failure evidence violates the bounded no-effect failure contract."]);
    const owner = evidence.owner_candidate || {}; const ownerSlot = sourceSlots.get(owner.id);
    if (owner.id !== "CODEX-03" || owner.authority_granted !== false || !Array.isArray(owner.evidence_sources) || owner.evidence_sources.length < 2 || !ownerSlot || canonicalProjectId(ownerSlot.project_hint) !== candidateId) return hold(base, "OWNER_CANDIDATE_NOT_EVIDENCED", ["A current owner candidate must be evidenced without promoting owner authority."]);
    const source = evidence.repository_identity || {};
    const exactBaseline = source.local_root === "C:\\PROJECTS\\MAWorld" && source.branch === "main" && source.head === "f82b9ccf880a9b781dac3273834a4d13a9062fc3" && source.tree === "1069056c9088f4b0b2db4822cd89dc118cc6a6da" && source.clean === true && source.github_repository === null && source.github_repository_status === "NOT_EVIDENCED";
    if (!exactBaseline) return hold(base, "REPOSITORY_IDENTITY_NOT_EXACT", ["Known MAWorld local Git baseline identity is incomplete or changed inside the registration packet."]);
    if (source.fresh_readback_required_before_implementation !== true) return hold(base, "FRESH_GIT_BASELINE_GATE_MISSING", ["Registration packet must preserve the fresh Git readback requirement before implementation."]);
    const proposal = evidence.registration_candidate || {}; const expectedBlockers = ["INITDB_FAILED_ROOT_CAUSE_UNRESOLVED","FRESH_GIT_BASELINE_READBACK_REQUIRED_BEFORE_IMPLEMENTATION"];
    if (proposal.state !== "FAILURE_DIAGNOSTIC_REQUIRED" || proposal.next !== "MAWORLD_INITDB_DIAGNOSTIC_REPAIR" || JSON.stringify(proposal.blocked_by) !== JSON.stringify(expectedBlockers) || proposal.owner_candidate !== "CODEX-03" || proposal.owner_authority_granted !== false || proposal.operational_registration_authorized !== false || proposal.implementation_ready !== false || proposal.repair_authorized !== false) return hold(base, "REGISTRATION_CANDIDATE_BOUNDARY_MISMATCH", ["Proposed operational row expands beyond the evidenced state/blocker/authority boundary."]);

    const ready = { ...base, classification: "READY_FOR_HUMAN_OPERATIONAL_REGISTRATION", decision: "HUMAN_OPERATIONAL_REGISTRATION_GATE_READY", reason_code: "IDENTITY_CURRENT_RETURN_OWNER_CANDIDATE_AND_SOURCE_BASELINE_EVIDENCED", owner_candidate: owner.id, proposed_state: proposal.state, proposed_blockers: proposal.blocked_by.slice(), proposed_next: proposal.next, source_baseline: `${source.local_root} @ ${source.branch} ${source.head}`, current_return_bytes_bound: true, explanation: ["Current Portfolio identity adoption is present and remains identity-only.","Current Return Registry is hash-bound to CODEX-03 plus independent ANTIGRAVITY_WO041 failure observations.","CODEX-03 is evidenced as owner candidate; owner authority is not promoted.","Known local Git baseline is exact at the last evidence capture but is not fresh enough for implementation.","Human approval may register operational metadata only; repair remains separately gated."] };
    const applied = findRegistration(registrations, candidateId);
    if (!applied) return ready;
    const meta = applied.operational_metadata || {}; const binding = registrations.base_binding || {};
    const bindingValid = binding.control_observed_at === control.observed_at && binding.canonical_generation === control.canonical_current?.generation && binding.return_registry_drive_file_id === returnSource.drive_file_id && binding.return_registry_raw_sha256 === returnSource.raw_sha256 && applied.evidence_binding?.codex03_return_sha256 === codex.return_sha256 && applied.evidence_binding?.independent_verifier_slot === reviewer.slot;
    const metadataValid = meta.owner_candidate === ready.owner_candidate && meta.owner_authority_granted === false && meta.state === ready.proposed_state && JSON.stringify(meta.blocked_by) === JSON.stringify(ready.proposed_blockers) && meta.next === ready.proposed_next && meta.policy_bound === false && meta.source_baseline_fresh_for_implementation === false && meta.implementation_ready === false && meta.repair_authorized === false;
    if (!bindingValid || !metadataValid) return hold(ready, "APPLIED_REGISTRATION_BINDING_MISMATCH", ["Human-approved operational registration overlay does not reproduce the exact evidence-bound registration candidate."]);
    return { ...ready, classification: "CURRENT_OPERATIONAL_REGISTRATION_APPLIED", decision: "OPERATIONAL_REGISTRATION_APPLIED_NO_DOWNSTREAM_AUTHORITY", reason_code: "EXACT_HUMAN_OPERATIONAL_REGISTRATION_OVERLAY", operational_registration_applied: true, human_gate_required: false, approval_phrase: applied.approval.phrase, approved_at: applied.approval.approved_at, explanation: ["Human approval registered MAWorld operational metadata in the current Portfolio overlay.","Provider-generated R64 current_control_plane bytes were not modified.","Owner authority, policy binding, repair, implementation, dispatch, merge, deploy and runtime mutation remain NOT GRANTED.","Fresh local Git baseline readback remains mandatory before any persistent MAWorld software work."] };
  }

  function renderGate(target, value) {
    const explanation = (value.explanation || []).map((item) => `<li>${esc(item)}</li>`).join(""); const blockers = (value.proposed_blockers || []).map((item) => `<li>${esc(item)}</li>`).join("");
    target.innerHTML = `<div class="callout"><strong>Operational Registration Gate · ${badge(value.classification)}</strong><p>Project: <b>${esc(value.subject_project)}</b> · owner candidate: <b>${esc(value.owner_candidate || "UNRESOLVED")}</b> · owner authority: ${badge(value.owner_authority_granted ? "GRANTED" : "NOT GRANTED")}.</p><p>Registered metadata state: <b>${esc(value.proposed_state || "HOLD")}</b> · next: <b>${esc(value.proposed_next || "NONE")}</b>.</p>${blockers ? `<p>Blockers:</p><ul>${blockers}</ul>` : ""}<p>Operational registration applied: ${badge(value.operational_registration_applied ? "YES" : "NO")} · Git baseline fresh for implementation: ${badge(value.source_baseline_fresh_for_implementation ? "YES" : "NO")} · implementation ready: ${badge(value.implementation_ready ? "YES" : "NO")}.</p><ul>${explanation}</ul><p class="muted">Registration is metadata only. It does not authorize owner authority, repair, dispatch, implementation, merge, deploy, runtime mutation, trading or capital use.</p></div>`;
    return value;
  }
  async function fetchJson(url) { const response = await fetch(url, { cache: "no-store" }); if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`); return response.json(); }
  async function boot() { const target = document.querySelector("#portfolio-registration-list"); if (!target) return; try { const [control, agentControl, identityAdoptions, evidence, registrations] = await Promise.all([fetchJson(CONTROL_URL),fetchJson(AGENT_CONTROL_URL),fetchJson(IDENTITY_ADOPTIONS_URL),fetchJson(REGISTRATION_EVIDENCE_URL),fetchJson(REGISTRATIONS_URL)]); renderGate(target, buildOperationalRegistrationGate(control,agentControl,identityAdoptions,evidence,registrations)); } catch (error) { target.innerHTML = `<div class="error">Operational registration gate unavailable: ${esc(error.message)}</div>`; console.error(error); } }
  const api = { canonicalProjectId, validateEvidence, validateRegistrations, validateInputs, findRegistration, buildOperationalRegistrationGate, renderGate };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioRegistration = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
