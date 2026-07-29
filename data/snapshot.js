window.HANRI_SNAPSHOT = {
  meta: {
    snapshot_id: "R64-IMPLEMENTATION-SNAPSHOT-20260730",
    authority_generation: "R63",
    control_generation_created: false,
    generated_at: "2026-07-30T00:00:00+07:00",
    freshness: "SNAPSHOT / NOT LIVE",
    current_generation_claim: "R63",
    current_generation_verification: "USER_REPORTED + FABLE PROVIDER READBACK CLAIM; exact R63 bundle not controller-replayed here",
    global_mode: "READ_ONLY / PROPOSAL_FIRST",
    can_trade: false,
    capital_permission: "DENY"
  },
  kpis: [
    {label:"Текущая контрольная генерация", value:"R63", tone:"info"},
    {label:"Решения D1–D5", value:"5/5", tone:"ok"},
    {label:"P0 риски", value:"3", tone:"danger"},
    {label:"Прямой live-chat агентов", value:"НЕТ", tone:"warn"},
    {label:"Общая память", value:"ФРАГМЕНТ.", tone:"warn"}
  ],
  current_actions: [
    {title:"D1", text:"Зарегистрировать постоянный слот CLAUDE-BITUNIX."},
    {title:"D2", text:"Установить и проверить починку HANRI decision-intake loop."},
    {title:"D3", text:"Ввести CONTROL_FREEZE: не более одного control-generation в неделю, кроме P0/сломанных указателей."},
    {title:"D4", text:"Закрыть три P0 security gaps с проверкой доступа и без публикации секретов."},
    {title:"D5", text:"Письмо Роману утверждено к отправке; канал отправки отсутствует в этом runtime."}
  ],
  blockers: [
    {title:"Decision loop", text:"Принятые HANRI решения повторно появляются как pending."},
    {title:"Dashboard integration", text:"Источники и код cockpit существуют, но нет доказанного единого live dashboard receipt."},
    {title:"Common memory projection", text:"ContinuityOS, Control canter, return registry и proof ledger не собраны в один читаемый snapshot."},
    {title:"P0 security", text:"Postgres exposure, bearer token and remote-admin credential require controlled closure."}
  ],
  events: [
    {time:"2026-07-30", title:"R63 claimed published", text:"Fable reports pointer/state/role/lineage repair and provider readback."},
    {time:"2026-07-30", title:"D1–D5 approved", text:"Robert approved slot registration, HANRI repair, control freeze, security window and Roman outreach."},
    {time:"2026-07-24", title:"HANRI R28 handoff", text:"Supervisor/collector/remote bridge/spine feeder documented; status requires freshness re-verification."}
  ],
  systems: [
    {id:"control-center", name:"Control Center", operational:"degraded", truth:"evidenced", execution:"read_only", owner:"GPT + Antigravity + Robert", next:"R63 acceptance + unified snapshot", evidence:"CURRENT_POINTER / CURRENT_STATE / ROLE_INDEX"},
    {id:"hanri", name:"HANRI", operational:"degraded", truth:"verified", execution:"approval_required", owner:"Robert", next:"Decision-loop repair + P0 closure", evidence:"HANRI R28 + R63 claim"},
    {id:"continuity-os", name:"ContinuityOS", operational:"degraded", truth:"verified", execution:"halted", owner:"CODEX-01", next:"Runtime preflight + common memory adapter", evidence:"checkpoints / proof ledger / canonical state"},
    {id:"archive-os", name:"ArchiveOS", operational:"maintenance", truth:"evidenced", execution:"read_only", owner:"Archive line", next:"Source vault + semantic coverage", evidence:"archive registries"},
    {id:"executor-network", name:"Executor Network", operational:"degraded", truth:"evidenced", execution:"approval_required", owner:"Codex / Fable / Claude / Work / Antigravity", next:"Permanent slots + deterministic return intake", evidence:"Return Broker / CURRENT_RETURN_REGISTRY"},
    {id:"trading-os", name:"TradingOS", operational:"degraded", truth:"contradicted", execution:"read_only", owner:"CODEX-05", next:"Measurement repair + forward evidence", evidence:"CODEX-02 findings"},
    {id:"sovereign-arena", name:"Sovereign Arena", operational:"degraded", truth:"evidenced", execution:"proposal_only", owner:"CODEX-04", next:"Preview smoke; no production promotion", evidence:"R51 candidate"},
    {id:"visionassist", name:"VisionAssist", operational:"maintenance", truth:"evidenced", execution:"read_only", owner:"CODEX-06", next:"First real evidence freeze + human prior", evidence:"75 frozen cases"},
    {id:"parasite-killer", name:"Parasite-Killer", operational:"unknown", truth:"claimed", execution:"read_only", owner:"CODEX-08", next:"Accept exact current return", evidence:"R59/R62 return pending intake"},
    {id:"maworld", name:"MAWorld", operational:"halted", truth:"verified", execution:"isolated_only", owner:"CODEX-03", next:"Postgres sandbox + RLS 21/21", evidence:"INITDB failure receipts"},
    {id:"knowledge-lab", name:"Knowledge Lab", operational:"maintenance", truth:"evidenced", execution:"read_only", owner:"Claude / ArchiveOS", next:"Semantic archive sweep", evidence:"coverage ledgers"},
    {id:"universe-hub", name:"Universe Hub", operational:"planned", truth:"evidenced", execution:"read_only", owner:"CODEX-01", next:"Connect verified adapters", evidence:"Master Architecture V1"}
  ],
  agents: [
    {slot:"GPT", role:"controller / arbiter", status:"active", channel:"chat + artifacts", memory:"current conversation + Control snapshot"},
    {slot:"Antigravity", role:"physical verifier / operator", status:"unknown freshness", channel:"work order → Drive return", memory:"ContinuityOS + host state"},
    {slot:"CODEX-01", role:"ContinuityOS / dashboard", status:"assigned", channel:"Return Broker", memory:"worktree + bounded package"},
    {slot:"CODEX-02", role:"edge research", status:"assigned", channel:"Return Broker", memory:"research package"},
    {slot:"CODEX-03", role:"MAWorld", status:"assigned", channel:"Return Broker", memory:"worktree + receipts"},
    {slot:"CODEX-04", role:"Arena", status:"assigned", channel:"Return Broker", memory:"source candidate"},
    {slot:"CODEX-05", role:"TradingOS", status:"assigned", channel:"Return Broker", memory:"TradingOS evidence"},
    {slot:"CODEX-06", role:"VisionAssist", status:"assigned", channel:"Return Broker", memory:"case store"},
    {slot:"CODEX-07", role:"transport / event bus", status:"assigned", channel:"Return Broker", memory:"registry + broker"},
    {slot:"CODEX-08", role:"Parasite-Killer", status:"assigned", channel:"Return Broker", memory:"market scan store"},
    {slot:"Work", role:"human proof / pilots", status:"assigned", channel:"Drive + CRM", memory:"operator CRM"},
    {slot:"Claude", role:"archive / Bitunix evidence", status:"active reported", channel:"Cowork + Drive", memory:"Cowork session + Drive"},
    {slot:"Fable 5", role:"independent oversight", status:"completed R63 reported", channel:"Drive docs", memory:"sealed input packet only"}
  ],
  decisions: [
    {id:"D1", verdict:"ACCEPT", action:"Permanent CLAUDE-BITUNIX slot", implementation:"pending strict R64 receipt"},
    {id:"D2", verdict:"ACCEPT", action:"HANRI decision-intake repair", implementation:"authorized; baseline and tests required"},
    {id:"D3", verdict:"ACCEPT", action:"CONTROL_FREEZE policy", implementation:"authorized; emergency exceptions only"},
    {id:"D4", verdict:"ACCEPT", action:"P0 security closure", implementation:"authorized; compensatable steps + access validation"},
    {id:"D5", verdict:"ACCEPT", action:"Roman pilot outreach", implementation:"send approved; not sent from this runtime"}
  ],
  memory_layers: [
    {name:"Hot / Current", status:"partial", description:"CURRENT_POINTER, CURRENT_STATE, ROLE_INDEX, ROLE_VIEWS, active work orders."},
    {name:"Warm / Episodic", status:"partial", description:"checkpoints.jsonl, proof_ledger.jsonl, decision ledger, run journals, returns."},
    {name:"Cold / Source", status:"evidenced", description:"ArchiveOS source vault, Drive archives, content-addressed files and manifests."},
    {name:"Semantic / Claims", status:"partial", description:"entities, claims, evidence pointers, conflicts, supersession and confidence."},
    {name:"Procedural", status:"partial", description:"work-order templates, verification recipes, security playbooks and rollback procedures."}
  ],
  memory_contract: {
    required_before_work:["CURRENT_POINTER","CURRENT_STATE","ROLE_INDEX","CURRENT_RETURN_REGISTRY","slot work order"],
    shared_state:["Plan","Tasks","Findings","EvidencePointers","Contradictions","Budget","RunStatus"],
    append_only:["events","decisions","proofs","returns","checkpoints"],
    truth_rule:"No claim becomes current truth without source, freshness, verification and scope.",
    missing_rule:"Missing discovery never authorizes rerun."
  },
  communication_flow:[
    "Operator intent",
    "Control Center work order",
    "Agent isolated worktree/session",
    "Evidence return bundle",
    "Return Broker / Drive",
    "Independent verification",
    "Registry + ContinuityOS checkpoint",
    "Dashboard snapshot"
  ],
  messages:[
    {from:"Fable 5", to:"Control Center", type:"oversight audit", status:"reported received", ref:"R63"},
    {from:"Claude", to:"Control Center", type:"return notice", status:"Gen-003 accepted with conditions", ref:"CLAUDE-BITUNIX"},
    {from:"Codex fleet", to:"Return Broker", type:"strict triplets", status:"per-slot / not direct chat", ref:"CURRENT_RETURN_REGISTRY"},
    {from:"Robert", to:"HANRI", type:"human decisions", status:"D1–D5 approved", ref:"R64 decision receipt"}
  ],
  security:[
    {id:"P0-1", title:"Arena PostgreSQL exposure", status:"OPEN_REVERIFY", action:"Confirm exposure; bind localhost/firewall; rotate password; prove app continuity."},
    {id:"P0-2", title:"Bearer token in panel artifact", status:"OPEN_REVERIFY", action:"Identify current token use; issue new token; update consumer; revoke old; redact artifacts."},
    {id:"P0-3", title:"Remote Administrator credential", status:"OPEN_REVERIFY", action:"Preserve break-glass; validate new key/access; rotate/disable old password; prove no lockout."}
  ],
  arbiter_content:{
    summary:"Точная фраза «контент спрашивает у ИИ, а наши ИИ отвечают» пока не найдена. Но восстановлена почти наверняка та же продуктовая идея: personal arbiter UI / research swarm. Пользователь задаёт вопрос или контент-задачу; несколько модельных proposers независимо отвечают; verifier проверяет факты и противоречия; Arbiter синтезирует финальный ответ с evidence ledger, confidence и unresolved questions.",
    flow:["Контент-вопрос","GPT / Claude / Gemini proposers","Normalizer","Verifier / Critic","Arbiter / Synthesizer","Готовый пост / разбор + evidence"],
    evidence_status:"RECOVERED_CONCEPT / EXACT_PHRASE_NOT_LOCATED",
    sources:["nftgpt.txt","MASTER_KNOWLEDGE_MAP.md","UNIVERSE_HUB_MASTER_ARCHITECTURE_V1.md"]
  }
};
