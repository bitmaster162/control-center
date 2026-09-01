(function (root) {
  "use strict";

  const POLICY_URL = "../data/portfolio_policy.candidate.v1.json";
  const REGISTRATIONS_URL = "../data/portfolio_operational_registrations.current.v1.json";
  const EVIDENCE_URL = "../data/portfolio_policy_binding_evidence.maworld.candidate.v1.json";
  const EXPECTED_REGISTRATION_APPROVAL = "APPROVE_MAWORLD_OPERATIONAL_PROJECT_REGISTRATION_R1";

  const esc = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  function badge(value) { const text = String(value ?? "UNKNOWN"); const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-"); return `<span class="status status-${esc(key)}">${esc(text)}</span>`; }
  function canonicalProjectId(value) { return String(value ?? "").toLowerCase().replaceAll(/[^a-z0-9]+/g, ""); }

  function validateEvidence(evidence) {
    if (!evidence || evidence.schema !== "control_center.portfolio_policy_binding_evidence.v1") throw new Error("portfolio policy-binding evidence schema mismatch");
    if (evidence.projection_kind !== "CANDIDATE_NON_AUTHORITY_POLICY_BINDING_EVIDENCE") throw new Error("portfolio policy-binding evidence kind mismatch");
    const safety = evidence.safety || {};
    for (const key of ["authority_granted","canonical_policy_adoption","policy_authority_granted","owner_authority_granted","implementation_authorized","repair_authorized","dispatch_authorized","auto_fix_authorized","merge_authorized","deploy_authorized","runtime_mutation_authorized","self_application"]) {
      if (safety[key] !== false) throw new Error(`portfolio policy-binding authority invariant mismatch:${key}`);
    }
    if (safety.can_trade !== false || safety.capital_permission !== "DENY") throw new Error("portfolio policy-binding trading/capital invariant mismatch");
    return evidence;
  }

  function validateRegistrations(registrations) {
    if (!registrations || registrations.schema !== "control_center.portfolio_operational_registrations.v1") throw new Error("portfolio policy-binding registrations schema mismatch");
    if (registrations.projection_kind !== "HUMAN_APPROVED_NON_EXECUTION_OPERATIONAL_REGISTRATION_OVERLAY") throw new Error("portfolio policy-binding registrations kind mismatch");
    if (registrations.safety?.downstream_authority_granted !== false || registrations.safety?.policy_authority_granted !== false || registrations.safety?.repair_authorized !== false) throw new Error("portfolio policy-binding registration authority mismatch");
    return registrations;
  }

  function hold(base, reasonCode, explanation) { return { ...base, classification: "HOLD", decision: "HOLD", reason_code: reasonCode, explanation }; }

  function buildPolicyBinding(policy, registrations, evidence) {
    validateEvidence(evidence);
    validateRegistrations(registrations);
    const candidateId = canonicalProjectId(evidence.subject?.canonical_id);
    const base = {
      schema: "control_center.portfolio_policy_binding_projection.v1",
      projection_kind: "NON_AUTHORITY_POLICY_BINDING_PROJECTION",
      subject_project: candidateId || null,
      classification: "HOLD",
      decision: "HOLD",
      reason_code: "UNSET",
      policy_state: null,
      portfolio_role: null,
      strategic_decision: null,
      operational_registration_bound: false,
      policy_authority_granted: false,
      owner_authority_granted: false,
      implementation_ready: false,
      repair_authorized: false,
      dispatch_authorized: false,
      execution_authority: "NONE",
      expected_terminal_reason_after_binding: evidence.binding_requirements?.expected_terminal_reason_after_binding || null
    };

    if (!candidateId || candidateId !== canonicalProjectId(evidence.subject?.display_name)) return hold(base, "SUBJECT_IDENTITY_MISMATCH", ["Policy-binding subject does not canonicalize to the current MAWorld identity."]);
    if (!policy || policy.schema !== "control_center.portfolio_policy.v1" || policy.policy_kind !== "CANDIDATE_NON_AUTHORITY_POLICY" || policy.approval_scope !== "AUTHORIZED_FOR_BRANCH_IMPLEMENTATION_ONLY") return hold(base, "CANDIDATE_POLICY_CONTRACT_MISMATCH", ["Policy file is missing the bounded candidate/non-authority contract."]);
    if (policy.safety?.authority_granted !== false || policy.safety?.source_of_truth_promoted !== false || policy.safety?.dispatch_authorized !== false || policy.safety?.auto_fix_authorized !== false || policy.safety?.merge_authorized !== false || policy.safety?.deploy_authorized !== false) throw new Error("portfolio policy-binding policy authority invariant mismatch");

    const registration = (registrations.registrations || []).find((item) => canonicalProjectId(item.canonical_id) === candidateId) || null;
    if (!registration) return hold(base, "OPERATIONAL_REGISTRATION_MISSING", ["MAWorld must be operationally registered before candidate policy binding."]);
    const regMeta = registration.operational_metadata || {};
    const regOk = registration.approval?.phrase === EXPECTED_REGISTRATION_APPROVAL
      && registration.approval?.scope === "CURRENT_PORTFOLIO_OPERATIONAL_REGISTRATION_ONLY"
      && registration.result?.current_operational_registration === "CURRENT_PORTFOLIO_OPERATIONALLY_REGISTERED"
      && regMeta.state === evidence.registration_binding?.expected_operational_state
      && regMeta.owner_candidate === evidence.registration_binding?.expected_owner_candidate
      && regMeta.owner_authority_granted === false
      && regMeta.implementation_ready === false
      && regMeta.repair_authorized === false;
    if (!regOk) return hold(base, "OPERATIONAL_REGISTRATION_BINDING_MISMATCH", ["Operational registration does not reproduce the bounded MAWorld state/owner-candidate/authority contract."]);

    const returnSource = evidence.source_evidence?.current_return_registry || {};
    if (registrations.base_binding?.return_registry_drive_file_id !== returnSource.drive_file_id || registrations.base_binding?.return_registry_raw_sha256 !== returnSource.raw_sha256) return hold(base, "RETURN_REGISTRY_PROVENANCE_MISMATCH", ["Policy-binding evidence is not hash-bound to the Return Registry provenance used for MAWorld operational registration."]);
    const research = evidence.source_evidence?.deep_research_decision || {};
    if (research.decision !== "KEEP_RESEARCH_INFRA" || research.implementation_status !== "PARTIAL_INTERNAL_EVIDENCE" || research.proof_gate !== "ONE_COMPLETE_RECEIPT_BUNDLE_ON_VERIFIABLE_GIT_BASELINE") return hold(base, "STRATEGIC_SOURCE_CONTRACT_MISMATCH", ["MAWorld strategic source does not support the narrow KEEP_RESEARCH_INFRA candidate policy."]);

    const entry = policy.projects?.[candidateId] || null;
    if (!entry) return hold(base, "POLICY_ENTRY_MISSING", ["MAWorld has operational registration but no candidate policy entry."]);
    const requirements = evidence.binding_requirements || {};
    if (entry.policy_state !== requirements.policy_state || entry.policy_binding_class !== requirements.policy_binding_class || entry.portfolio_role !== requirements.portfolio_role || entry.strategic_decision !== requirements.strategic_decision || entry.terminal_evidence_binding_required !== true || entry.implementation_ready !== false || entry.repair_authorized !== false || entry.execution_authority !== "NONE") return hold(base, "POLICY_ENTRY_BOUNDARY_MISMATCH", ["MAWorld candidate policy entry expands or drifts beyond the source-backed non-authority requirements."]);

    const dod = entry.definition_of_done || {};
    const requiredDimensions = ["technical_acceptance","operational_usability","commercial_validation","production_qualification"];
    if (requiredDimensions.some((key) => !Array.isArray(dod[key]) || dod[key].length === 0)) return hold(base, "DOD_DIMENSION_MISSING", ["Candidate MAWorld policy must preserve all four Portfolio Definition-of-Done dimensions."]);
    if (!Array.isArray(entry.kill_sunset_criteria) || entry.kill_sunset_criteria.length < 4) return hold(base, "KILL_SUNSET_CRITERIA_INCOMPLETE", ["Candidate MAWorld policy lacks bounded HOLD/REVISE/SUNSET criteria."]);
    if (entry.freshness_policy?.code_baseline_fresh_readback_required_before_implementation !== true || entry.freshness_policy?.external_research_continuous_freshness !== false) return hold(base, "FRESHNESS_POLICY_MISMATCH", ["MAWorld policy must require fresh Git readback and must not treat the external research cutoff as continuous freshness."]);

    return {
      ...base,
      classification: "CANDIDATE_POLICY_BOUND",
      decision: "MAWORLD_POLICY_BINDING_PRESENT_NON_AUTHORITY",
      reason_code: "OPERATIONAL_REGISTRATION_AND_SOURCE_BACKED_POLICY_CRITERIA_BOUND",
      policy_state: entry.policy_state,
      portfolio_role: entry.portfolio_role,
      strategic_decision: entry.strategic_decision,
      operational_registration_bound: true,
      explanation: [
        "MAWorld operational registration is present under the exact bounded human approval.",
        "Candidate policy is grounded in current failure evidence, the MAWorld internal gate, and the KEEP_RESEARCH_INFRA research decision.",
        "Policy remains branch-local candidate/non-authority; no owner, repair, implementation, dispatch, merge, deploy, runtime, trading, or capital authority is granted.",
        `Terminal Engine should now advance from POLICY_NOT_BOUND to ${requirements.expected_terminal_reason_after_binding || "the next evidence gate"}.`
      ]
    };
  }

  function renderBinding(target, value) {
    const explanation = (value.explanation || []).map((item) => `<li>${esc(item)}</li>`).join("");
    target.innerHTML = `<div class="callout"><strong>MAWorld Policy Binding · ${badge(value.classification)}</strong><p>Project: <b>${esc(value.subject_project || "NONE")}</b> · role: <b>${esc(value.portfolio_role || "UNBOUND")}</b> · strategic decision: <b>${esc(value.strategic_decision || "UNBOUND")}</b>.</p><p>Policy authority: ${badge(value.policy_authority_granted ? "GRANTED" : "NOT GRANTED")} · implementation ready: ${badge(value.implementation_ready ? "YES" : "NO")} · repair: ${badge(value.repair_authorized ? "AUTHORIZED" : "NOT AUTHORIZED")}.</p><ul>${explanation}</ul><p class="muted">Candidate policy binding is not canonical adoption and grants no execution authority.</p></div>`;
    return value;
  }

  async function fetchJson(url) { const response = await fetch(url, { cache: "no-store" }); if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`); return response.json(); }
  async function boot() { const target = document.querySelector("#portfolio-policy-binding-list"); if (!target) return; try { const [policy, registrations, evidence] = await Promise.all([fetchJson(POLICY_URL), fetchJson(REGISTRATIONS_URL), fetchJson(EVIDENCE_URL)]); renderBinding(target, buildPolicyBinding(policy, registrations, evidence)); } catch (error) { target.innerHTML = `<div class="error">Portfolio policy binding unavailable: ${esc(error.message)}</div>`; console.error(error); } }

  const api = { canonicalProjectId, validateEvidence, validateRegistrations, buildPolicyBinding, renderBinding };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioPolicyBinding = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
