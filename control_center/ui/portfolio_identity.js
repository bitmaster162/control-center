(function (root) {
  "use strict";

  const CONTROL_URL = "../data/current_control_plane.generated.v1.json";
  const AGENT_CONTROL_URL = "../data/agent_control_plane.generated.v1.json";
  const IDENTITY_EVIDENCE_URL = "../data/portfolio_project_identity.candidate.v1.json";

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function badge(value) {
    const text = String(value ?? "UNKNOWN");
    const key = text.toLowerCase().replaceAll(/[^a-z0-9]+/g, "-");
    return `<span class="status status-${esc(key)}">${esc(text)}</span>`;
  }

  function canonicalProjectId(value) {
    return String(value ?? "").toLowerCase().replaceAll(/[^a-z0-9]+/g, "");
  }

  function validateIdentityEvidence(evidence) {
    if (!evidence || evidence.schema !== "control_center.portfolio_project_identity_evidence.v1") {
      throw new Error("portfolio identity evidence schema mismatch");
    }
    if (evidence.projection_kind !== "CANDIDATE_NON_AUTHORITY_PROJECT_IDENTITY_EVIDENCE") {
      throw new Error("portfolio identity evidence projection mismatch");
    }
    const safety = evidence.safety || {};
    if (
      safety.authority_granted !== false
      || safety.identity_authority_granted !== false
      || safety.alias_authority_granted !== false
      || safety.automatic_registration !== false
      || safety.canonical_registry_write_authorized !== false
      || safety.dispatch_authorized !== false
      || safety.auto_fix_authorized !== false
      || safety.merge_authorized !== false
      || safety.deploy_authorized !== false
      || safety.self_application !== false
    ) {
      throw new Error("portfolio identity authority invariant mismatch");
    }
    if (safety.can_trade !== false || safety.capital_permission !== "DENY") {
      throw new Error("portfolio identity trading/capital invariant mismatch");
    }
    return evidence;
  }

  function hold(base, reasonCode, explanation) {
    return {
      ...base,
      classification: "HOLD",
      decision: "HOLD",
      reason_code: reasonCode,
      registry_gate_required: true,
      explanation
    };
  }

  function sortedProjectIds(control) {
    return (control.projects || []).map((project) => String(project.id || "")).sort();
  }

  function buildIdentityReconciliation(control, agentControl, evidence) {
    validateIdentityEvidence(evidence);
    if (!control || control.schema !== "control_center.current_control_plane_projection.v1" || control.projection_kind !== "NON_AUTHORITY_PROJECTION") {
      throw new Error("portfolio identity control projection mismatch");
    }
    if (!agentControl || agentControl.schema !== "control_center.agent_control_plane.v1" || agentControl.projection_kind !== "NON_AUTHORITY_PROJECTION") {
      throw new Error("portfolio identity agent-control projection mismatch");
    }

    const displayName = String(evidence.subject?.display_name || "").trim();
    const candidateId = String(evidence.subject?.canonical_candidate || "").trim();
    const base = {
      schema: "control_center.portfolio_project_identity_reconciliation.v1",
      projection_kind: "NON_AUTHORITY_IDENTITY_RECONCILIATION",
      subject_display_name: displayName || null,
      canonical_candidate: candidateId || null,
      classification: "HOLD",
      decision: "HOLD",
      reason_code: "UNSET",
      semantic_alias_status: "NOT_EVIDENCED",
      canonical_registry_match: null,
      provider_observation_count: 0,
      provider_slots: [],
      registry_gate_required: true,
      automatic_registration: false,
      identity_authority_granted: false,
      alias_authority_granted: false,
      canonical_registry_write_authorized: false,
      dispatch_authorized: false,
      auto_fix_authorized: false,
      merge_authorized: false,
      deploy_authorized: false,
      execution_authority: "NONE"
    };

    if (!displayName || !candidateId || canonicalProjectId(displayName) !== candidateId) {
      return hold(base, "SUBJECT_CANONICALIZATION_MISMATCH", [
        "Identity evidence subject is missing or its canonical candidate does not match deterministic normalization.",
        "No alias or registry decision is inferred."
      ]);
    }

    if (
      evidence.source_binding?.control_observed_at !== control.observed_at
      || evidence.source_binding?.agent_control_observed_at !== agentControl.observed_at
    ) {
      return hold(base, "SOURCE_EPOCH_MISMATCH", [
        "Identity evidence is not bound to the same captured control/agent-control epochs.",
        "Recapture identity evidence before making a registry recommendation."
      ]);
    }

    const actualProjectIds = sortedProjectIds(control);
    const evidencedProjectIds = Array.isArray(evidence.tracked_project_ids_at_capture)
      ? evidence.tracked_project_ids_at_capture.map(String).sort()
      : [];
    if (JSON.stringify(actualProjectIds) !== JSON.stringify(evidencedProjectIds)) {
      return hold(base, "REGISTRY_EVIDENCE_MISMATCH", [
        "Tracked project IDs differ from the identity evidence packet.",
        "The reconciliation layer will not reason from a stale or incomplete registry capture."
      ]);
    }

    const packetObservations = Array.isArray(evidence.provider_observations) ? evidence.provider_observations : [];
    const minimum = evidence.minimum_distinct_slot_observations;
    if (!Number.isInteger(minimum) || minimum < 2 || packetObservations.length < minimum) {
      return hold(base, "IDENTITY_EVIDENCE_INSUFFICIENT", [
        "Identity evidence does not contain the configured minimum number of distinct slot observations.",
        "A single label occurrence is insufficient to support a stable identifier candidate."
      ]);
    }

    const packetSlots = packetObservations.map((item) => item.slot);
    if (new Set(packetSlots).size !== packetSlots.length) {
      return hold(base, "IDENTITY_EVIDENCE_DUPLICATE_SLOT", [
        "Identity evidence repeats a slot and therefore does not provide independent slot observations."
      ]);
    }

    const sourceMatches = (agentControl.slots || []).filter(
      (slot) => canonicalProjectId(slot.project_hint) === candidateId
    );
    const sourceBySlot = new Map(sourceMatches.map((slot) => [slot.slot, slot]));
    const mismatch = packetObservations.find((observed) => {
      const source = sourceBySlot.get(observed.slot);
      return !source
        || source.project_hint !== observed.project_hint
        || source.reported_state !== observed.reported_state
        || source.work_order !== observed.work_order;
    });
    if (mismatch) {
      return hold({ ...base, provider_observation_count: sourceMatches.length, provider_slots: sourceMatches.map((slot) => slot.slot) }, "PROVIDER_IDENTITY_EVIDENCE_MISMATCH", [
        `Evidence for slot ${mismatch.slot || "UNKNOWN"} does not reproduce the captured agent-control observation.`,
        "The candidate is held rather than repaired or rebound automatically."
      ]);
    }

    const distinctSourceSlots = new Set(sourceMatches.map((slot) => slot.slot));
    if (distinctSourceSlots.size < minimum) {
      return hold({ ...base, provider_observation_count: distinctSourceSlots.size, provider_slots: Array.from(distinctSourceSlots) }, "INSUFFICIENT_PROVIDER_OBSERVATIONS", [
        `Only ${distinctSourceSlots.size} distinct provider slot observation(s) reproduce the candidate identifier; ${minimum} are required.`,
        "No project identity conclusion is emitted."
      ]);
    }

    const canonicalMatch = (control.projects || []).find(
      (project) => canonicalProjectId(project.id) === candidateId
    ) || null;
    if (canonicalMatch) {
      const result = {
        ...base,
        classification: "MATCH_EXISTING_PROJECT",
        decision: "REVIEW_EXISTING_PROJECT_MATCH",
        reason_code: "CANONICAL_PROJECT_ID_MATCH",
        semantic_alias_status: "CANONICAL_IDENTIFIER_MATCH",
        canonical_registry_match: canonicalMatch.id,
        provider_observation_count: distinctSourceSlots.size,
        provider_slots: Array.from(distinctSourceSlots),
        registry_gate_required: false,
        explanation: [
          `Canonical identifier ${candidateId} matches tracked project ${canonicalMatch.id}.`,
          "This reconciliation is descriptive only and does not mutate project metadata or grant execution authority."
        ]
      };
      if (evidence.candidate_result?.classification && evidence.candidate_result.classification !== result.classification) {
        return hold(result, "CANDIDATE_CLAIM_MISMATCH", [
          "Derived identity classification conflicts with the candidate evidence packet claim.",
          "Recapture the candidate packet before relying on the reconciliation."
        ]);
      }
      return result;
    }

    const result = {
      ...base,
      classification: "DISTINCT_IDENTIFIER_CANDIDATE",
      decision: "HUMAN_ALIAS_OR_NEW_PROJECT_REGISTRY_GATE",
      reason_code: "REPEATED_PROVIDER_IDENTIFIER_NO_CANONICAL_REGISTRY_MATCH",
      semantic_alias_status: "NOT_EVIDENCED",
      canonical_registry_match: null,
      provider_observation_count: distinctSourceSlots.size,
      provider_slots: Array.from(distinctSourceSlots),
      registry_gate_required: true,
      explanation: [
        `${distinctSourceSlots.size} distinct captured slots reproduce provider identifier ${displayName}.`,
        `No tracked project ID canonicalizes to ${candidateId}.`,
        "This establishes a stable unregistered identifier candidate only; semantic aliasing to an existing project is not evidenced.",
        "Human review must choose alias binding, a new project registry entry, or HOLD. No automatic registration occurs."
      ]
    };

    const claim = evidence.candidate_result || {};
    if (
      claim.classification !== result.classification
      || claim.semantic_alias_status !== result.semantic_alias_status
      || claim.decision !== result.decision
      || claim.registry_gate_required !== true
    ) {
      return hold(result, "CANDIDATE_CLAIM_MISMATCH", [
        "Derived identity classification does not match the candidate evidence packet claim.",
        "The layer fails closed instead of silently rewriting the packet."
      ]);
    }
    return result;
  }

  function renderIdentity(target, value) {
    const explanation = (value.explanation || []).map((item) => `<li>${esc(item)}</li>`).join("");
    target.innerHTML = `<div class="callout">
      <strong>Project Identity Reconciliation · ${badge(value.classification)}</strong>
      <p>Subject: <b>${esc(value.subject_display_name || "NONE")}</b> · canonical candidate: <b>${esc(value.canonical_candidate || "NONE")}</b> · provider observations: <b>${esc(value.provider_observation_count)}</b>.</p>
      <p>Registry match: <b>${esc(value.canonical_registry_match || "NONE")}</b> · semantic alias: ${badge(value.semantic_alias_status)} · decision: ${badge(value.decision)}.</p>
      <ul>${explanation}</ul>
      <p class="muted">Identity reconciliation is non-authority. It cannot register, rename, alias, repair, dispatch, merge, deploy, trade, allocate capital, or mutate canonical state.</p>
    </div>`;
    return value;
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`);
    return response.json();
  }

  async function boot() {
    const target = document.querySelector("#portfolio-identity-list");
    if (!target) return;
    try {
      const [control, agentControl, evidence] = await Promise.all([
        fetchJson(CONTROL_URL),
        fetchJson(AGENT_CONTROL_URL),
        fetchJson(IDENTITY_EVIDENCE_URL)
      ]);
      renderIdentity(target, buildIdentityReconciliation(control, agentControl, evidence));
    } catch (error) {
      target.innerHTML = `<div class="error">Portfolio identity reconciliation unavailable: ${esc(error.message)}</div>`;
      console.error(error);
    }
  }

  const api = { canonicalProjectId, validateIdentityEvidence, buildIdentityReconciliation, renderIdentity };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioIdentity = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
