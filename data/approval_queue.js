window.HANRI_APPROVAL_QUEUE = {
  "schema_version": 1,
  "policy_version": "37.2.0-approval-queue-v1",
  "generated_at": "2026-08-11T20:50:00Z",
  "mode": "READ_ONLY_PROJECTION",
  "sovereign_channel": "EXACT_HUMAN_GATE",
  "auto_approval": false,
  "auto_execution": false,
  "can_trade": false,
  "capital_permission": "DENY",
  "summary": {
    "total": 1,
    "pending": 0,
    "approved_not_executed": 0,
    "executed_verified": 1,
    "denied": 0,
    "expired": 0,
    "rolled_back": 0,
    "failed": 0
  },
  "items": [
    {
      "queue_id": "AQ-7a4e0938832b1a35",
      "status": "EXECUTED_VERIFIED",
      "action_hash": "7a4e0938832b1a35c6d9c6b483ee206be4d924847c7602ef2bde4c5c81f0ffd0",
      "actor": "HANRI_EFFECT_GATEWAY",
      "operation": "update_dashboard_projection",
      "effect_class": "WRITE_REVERSIBLE",
      "target": "Control canter/00_DASHBOARD_CURRENT/HANRI_R64_DASHBOARD_CURRENT_R36_FULL_VERIFIED.html",
      "provider": "GOOGLE_DRIVE",
      "provider_target_id": "15GG9ElRV6Ed0gzGkB2b02JumHS58jU2r",
      "snapshot_id": "R64-P4-R37-GOVERNANCE-PHASE2-ACCEPTED-20260812T0329BKK",
      "before_sha256": "f29de43fb2bafcb54049159267331ceec8c46b5d2153291b9ba15bc8bbca75e3",
      "after_sha256": "a711c55e2443732dd4e004838a988ae3f8d9a7c88fac1f1350a90ede0441bee7",
      "approval_required": true,
      "approval_command": null,
      "expires_at": null,
      "receipt_status": "PASS",
      "receipt_sha256": "65abda776e26c4bf787d3e6c21decbc4d7b39d4f882dd2d6c980a2c153dedbf7",
      "replay_allowed": false,
      "evidence_state": "HASH_VERIFIED"
    }
  ],
  "projection_sha256": "fdf47d8fa45f264f51a72754439cc07b52c4b6cd40b1aeb03ab46e97b7898fa8"
};
