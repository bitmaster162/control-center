(function (root) {
  "use strict";

  const CONTROL_URL = "../data/current_control_plane.generated.v1.json";
  const AGENT_CONTROL_URL = "../data/agent_control_plane.generated.v1.json";
  const POLICY_URL = "../data/portfolio_policy.candidate.v1.json";
  const FRESHNESS_URL = "../data/provider_freshness_evidence.current.v1.json";
  const TERMINAL_EVIDENCE_URL = "../data/portfolio_terminal_evidence.candidate.v1.json";

  let governance = root.PortfolioGovernance;
  if (!governance && typeof require !== "undefined") governance = require("./portfolio_governance.js");

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

  function validateTerminalInputs(policy, terminalEvidence) {
    const engine = policy?.portfolio?.terminal_engine;
    if (!engine || engine.mode !== "EXPLICIT_SIGNALS_ONLY") {
      throw new Error("portfolio terminal-engine mode mismatch");
    }
    if (
      engine.infer_from_free_text !== false
      || engine.infer_from_project_state !== false
      || engine.auto_close !== false
      || engine.auto_sunset !== false
      || engine.auto_repair !== false
      || engine.execution_authority !== "NONE"
    ) {
      throw new Error("portfolio terminal-engine authority invariant mismatch");
    }
    if (!Array.isArray(engine.allowed_classifications) || !engine.allowed_classifications.includes("HOLD")) {
      throw new Error("portfolio terminal-engine classifications invalid");
    }
    if (!terminalEvidence || terminalEvidence.schema !== "control_center.portfolio_terminal_evidence.v1") {
      throw new Error("portfolio terminal evidence schema mismatch");
    }
    if (
      terminalEvidence.projection_kind !== "CANDIDATE_NON_AUTHORITY_TERMINAL_EVIDENCE"
      || terminalEvidence.safety?.authority_granted !== false
      || terminalEvidence.safety?.terminal_authority_granted !== false
      || terminalEvidence.safety?.sunset_authority_granted !== false
    ) {
      throw new Error("portfolio terminal evidence authority invariant mismatch");
    }
    return { engine, terminalEvidence };
  }

  function hold(base, reasonCode, explanation) {
    return {
      ...base,
      classification: "HOLD",
      reason_code: reasonCode,
      terminal_verdict: "HOLD",
      explanation
    };
  }

  function buildTerminalClassification(control, policy, terminalEvidence, evidenceBinding, arbiter) {
    const { engine } = validateTerminalInputs(policy, terminalEvidence);
    const base = {
      schema: "control_center.portfolio_terminal_classification.v1",
      projection_kind: "NON_AUTHORITY_TERMINAL_CLASSIFICATION",
      policy_mode: engine.mode,
      subject_source: engine.subject_source,
      evidence_source: engine.evidence_source,
      subject_project: arbiter?.recommended_project ?? null,
      provider_evidence_status: evidenceBinding?.status ?? "UNKNOWN",
      classification: "HOLD",
      reason_code: "UNSET",
      terminal_verdict: "HOLD",
      auto_close_authorized: false,
      auto_sunset_authorized: false,
      auto_repair_authorized: false,
      dispatch_authorized: false,
      merge_authorized: false,
      deploy_authorized: false,
      execution_authority: "NONE"
    };

    if (evidenceBinding?.status !== engine.provider_evidence_gate) {
      return hold(base, "PROVIDER_EVIDENCE_NOT_EXACT", [
        `Terminal engine requires ${engine.provider_evidence_gate}.`,
        `Observed provider evidence status is ${evidenceBinding?.status ?? "UNKNOWN"}.`,
        "No terminal, sunset, continue, or close action is inferred from non-exact provider evidence."
      ]);
    }

    if (arbiter?.decision !== "RECOMMEND_HUMAN_ATTENTION" || !String(arbiter.recommended_project || "").trim()) {
      return hold(base, "NO_ARBITER_SUBJECT", [
        "The Portfolio Arbiter did not emit one eligible human-attention subject.",
        "The terminal engine does not choose a substitute project."
      ]);
    }

    const subjectKey = canonicalProjectId(arbiter.recommended_project);
    const project = (control.projects || []).find((item) => canonicalProjectId(item.id) === subjectKey) || null;
    if (!project) {
      return hold(base, "UNREGISTERED_PROJECT", [
        `Arbiter subject ${arbiter.recommended_project} is not bound to the tracked project registry.`,
        "Terminal/kill/sunset classification stops at HOLD; the engine does not auto-register provider attention."
      ]);
    }

    const policyEntry = policy.projects?.[project.id] || null;
    if (!policyEntry) {
      return hold({ ...base, subject_project: project.id }, "POLICY_NOT_BOUND", [
        `Project ${project.id} is registered but has no bound terminal policy entry.`,
        "Free-text project state is not interpreted as terminal evidence."
      ]);
    }

    const evidenceEntry = terminalEvidence.projects?.[project.id] || null;
    if (!evidenceEntry) {
      return hold({ ...base, subject_project: project.id }, "TERMINAL_EVIDENCE_MISSING", [
        `Project ${project.id} has policy but no machine-readable terminal evidence entry.`,
        "Missing evidence remains missing; no terminal or sunset state is invented."
      ]);
    }

    if (
      ("human_sunset_requested" in evidenceEntry && typeof evidenceEntry.human_sunset_requested !== "boolean")
      || ("proof_obligation_open" in evidenceEntry && typeof evidenceEntry.proof_obligation_open !== "boolean")
      || ("explicit_terminal_verdict_evidenced" in evidenceEntry && typeof evidenceEntry.explicit_terminal_verdict_evidenced !== "boolean")
    ) {
      return hold({ ...base, subject_project: project.id }, "TERMINAL_EVIDENCE_INVALID", [
        "Terminal evidence contains non-boolean control signals.",
        "The engine fails closed instead of coercing or guessing values."
      ]);
    }

    if (evidenceEntry.human_sunset_requested === true) {
      return {
        ...base,
        subject_project: project.id,
        classification: "SUNSET_CANDIDATE",
        reason_code: "EXPLICIT_HUMAN_SUNSET_SIGNAL",
        terminal_verdict: "SUNSET",
        explanation: [
          "An explicit machine-readable human sunset signal is present.",
          "This is a candidate classification only; no project state is closed, deleted, archived, or mutated."
        ]
      };
    }

    if (evidenceEntry.explicit_terminal_verdict_evidenced === true) {
      const verdict = evidenceEntry.explicit_terminal_verdict;
      const allowedTerminal = new Set(["PASS", "REJECT", "BLOCKED_EXTERNAL"]);
      if (!allowedTerminal.has(verdict)) {
        return hold({ ...base, subject_project: project.id }, "EXPLICIT_TERMINAL_VERDICT_INVALID", [
          "An explicit terminal verdict was marked evidenced but is outside the bounded terminal set.",
          "The engine fails closed."
        ]);
      }
      return {
        ...base,
        subject_project: project.id,
        classification: "TERMINAL_CANDIDATE",
        reason_code: "EXPLICIT_TERMINAL_VERDICT_EVIDENCED",
        terminal_verdict: verdict,
        explanation: [
          `Explicit terminal evidence supports ${verdict}.`,
          "Candidate classification does not auto-close, apply, merge, deploy, or mutate canonical state."
        ]
      };
    }

    const requiredDimensions = Array.isArray(engine.required_dod_dimensions) ? engine.required_dod_dimensions : [];
    const dod = evidenceEntry.dod_dimensions || {};
    const allDodPass = requiredDimensions.length > 0
      && requiredDimensions.every((dimension) => dod[dimension] === engine.terminal_pass_value);
    const blockers = Array.isArray(project.blocked_by) ? project.blocked_by : [];

    if (allDodPass && evidenceEntry.proof_obligation_open === false && blockers.length === 0) {
      return {
        ...base,
        subject_project: project.id,
        classification: "TERMINAL_CANDIDATE",
        reason_code: "ALL_REQUIRED_DOD_EVIDENCED_PASS",
        terminal_verdict: "PASS",
        explanation: [
          "All required Definition-of-Done dimensions are explicitly EVIDENCED_PASS.",
          "No named project blocker remains and terminal evidence marks the proof obligation closed.",
          "This remains a candidate until the appropriate human/authority gate accepts it."
        ]
      };
    }

    if (evidenceEntry.proof_obligation_open === true || blockers.length > 0) {
      const reasons = [];
      if (evidenceEntry.proof_obligation_open === true) reasons.push("machine-readable terminal evidence says a proof obligation remains open");
      if (blockers.length > 0) reasons.push(`project registry reports ${blockers.length} blocker(s)`);
      return {
        ...base,
        subject_project: project.id,
        classification: "CONTINUE",
        reason_code: "OPEN_PROOF_OR_BLOCKER",
        terminal_verdict: null,
        explanation: [
          ...reasons,
          "CONTINUE means the lane still has evidenced work; it grants no dispatch or execution authority."
        ]
      };
    }

    return hold({ ...base, subject_project: project.id }, "INSUFFICIENT_TERMINAL_EVIDENCE", [
      "The project is registered and policy-bound, but evidence does not justify CONTINUE, TERMINAL_CANDIDATE, or SUNSET_CANDIDATE.",
      "The engine does not parse free-text DoD/kill criteria or infer from project state."
    ]);
  }

  function renderTerminal(target, value) {
    const explanation = (value.explanation || []).map((item) => `<li>${esc(item)}</li>`).join("");
    target.innerHTML = `<div class="callout">
      <strong>Terminal / Kill / Sunset Engine · ${badge(value.classification)}</strong>
      <p>Subject: <b>${esc(value.subject_project || "NONE")}</b> · reason: <b>${esc(value.reason_code)}</b>${value.terminal_verdict ? ` · terminal verdict: <b>${esc(value.terminal_verdict)}</b>` : ""}.</p>
      <ul>${explanation}</ul>
      <p class="muted">Classification is non-authority. No auto-close, auto-sunset, repair, dispatch, merge, deploy, deletion, archive, trading, capital, or canonical-state mutation is authorized.</p>
    </div>`;
    return value;
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`${url} fetch failed: ${response.status}`);
    return response.json();
  }

  async function boot() {
    const target = document.querySelector("#portfolio-terminal-list");
    if (!target || !governance) return;
    try {
      const [control, agentControl, policy, freshness, terminalEvidence] = await Promise.all([
        fetchJson(CONTROL_URL),
        fetchJson(AGENT_CONTROL_URL),
        fetchJson(POLICY_URL),
        fetchJson(FRESHNESS_URL),
        fetchJson(TERMINAL_EVIDENCE_URL)
      ]);
      governance.validateInputs(control, agentControl, policy, freshness);
      const evidenceBinding = governance.computeEvidenceBinding(control, freshness);
      const arbiter = governance.buildArbiterRecommendation(control, agentControl, policy, evidenceBinding);
      renderTerminal(target, buildTerminalClassification(control, policy, terminalEvidence, evidenceBinding, arbiter));
    } catch (error) {
      target.innerHTML = `<div class="error">Portfolio terminal engine unavailable: ${esc(error.message)}</div>`;
      console.error(error);
    }
  }

  const api = { canonicalProjectId, validateTerminalInputs, buildTerminalClassification, renderTerminal };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.PortfolioTerminal = api;
  if (typeof document !== "undefined") boot();
})(typeof globalThis !== "undefined" ? globalThis : this);
