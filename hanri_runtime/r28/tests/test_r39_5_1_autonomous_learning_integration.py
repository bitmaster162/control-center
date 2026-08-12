import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_policy_preserves_zero_effect_ceiling():
    cfg = json.loads(read("config/r39.5.1.autonomous-learning-integration.json"))
    assert cfg["policy_version"] == "39.5.1-autonomous-learning-integration-v1"
    assert cfg["heartbeat_minutes"] == 5
    assert cfg["runtime_refresh"]["stable_task_action_path_unchanged"] is True
    assert cfg["runtime_refresh"]["scheduler_xml_change_authorized"] is False
    boundary = cfg["effect_boundary"]
    assert boundary["proposal_only"] is True
    assert boundary["local_state_write_only"] is True
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"
    for key in (
        "provider_calls",
        "scheduler_install",
        "scheduler_modify",
        "human_decision_execution",
        "self_apply",
        "skill_install",
        "system_write",
        "operator_message",
        "auto_dispatch",
        "external_messages",
    ):
        assert boundary[key] is False


def test_live_learning_runner_requires_exact_complete_r39_4_1_upstream():
    text = read("scripts/Run-R39.5.1ImprovementLearningLive-PS51.ps1")
    assert "39.4.1-live-heartbeat-integration-v1" in text
    assert "R39_4_1_OUTCOME_INTEGRATION_RECEIPT.json" in text
    assert "upstream integration is not PASS" in text
    assert "upstream outcome is pending" in text
    assert "integration/outcome semantic cycle mismatch" in text
    assert "upstream outcome receipt SHA mismatch" in text


def test_live_learning_runner_uses_existing_r39_5_engine_and_checks_effects():
    text = read("scripts/Run-R39.5.1ImprovementLearningLive-PS51.ps1")
    assert "hanri.improvement_learning_cli" in text
    assert "39.5.0-improvement-learning-v1" in text
    assert "R39_5_IMPROVEMENT_LEARNING_STATE.json" in text
    assert "R39_5_IMPROVEMENT_LEARNING_RECEIPT.json" in text
    assert "proposal_only=false" in text
    assert "local_state_write_only=false" in text
    assert "learning receipt effects nonzero" in text
    assert "learning state effects nonzero" in text
    assert "CAN_TRADE false" in text
    assert "CAPITAL_PERMISSION DENY" in text


def test_wrapper_layers_r39_5_after_r39_4_1():
    text = read("scripts/Invoke-R39.5.1AttentionHeartbeat-Wrapper-PS51.ps1")
    assert "Invoke-R39.4.1AttentionHeartbeat-Core-PS51.ps1" in text
    assert "Run-R39.5.1ImprovementLearningLive-PS51.ps1" in text
    upstream_pos = text.index("& powershell -NoProfile -ExecutionPolicy Bypass -File $upstreamWrapper")
    learning_pos = text.index("& powershell -NoProfile -ExecutionPolicy Bypass -File $learningRunner")
    assert upstream_pos < learning_pos


def test_wrapper_bootstraps_and_retries_learning_without_stale_ranking():
    text = read("scripts/Invoke-R39.5.1AttentionHeartbeat-Wrapper-PS51.ps1")
    assert "$learningMissing = -not (Test-Path -LiteralPath $learningReceipt -PathType Leaf)" in text
    assert "$needLearning = [bool]$upstream.outcome_executed -or" in text
    assert "R39_5_1_LEARNING_PENDING.json" in text
    assert "retry_on_next_heartbeat = $true" in text
    assert "LEARNING_PENDING_RETRY" in text
    assert "stale outcome ranking denied" in text
    assert "UPSTREAM_R39_4_1_FAILED" in text


def test_wrapper_never_executes_effects_or_generalizes():
    text = read("scripts/Invoke-R39.5.1AttentionHeartbeat-Wrapper-PS51.ps1")
    assert "CAUSATION_CLAIMED false" in text
    assert "GENERALIZATION_AUTHORIZED false" in text
    assert "SELF_APPLY false" in text
    assert "SKILL_INSTALL false" in text
    assert "SYSTEM_WRITE false" in text
    assert "OPERATOR_MESSAGE false" in text
    assert "EXECUTION_EFFECTS_PERFORMED 0" in text
    assert "Start-ScheduledTask" not in text
    assert "Register-ScheduledTask" not in text


def test_runtime_refresh_preserves_stable_task_path_and_layer_split():
    text = read("scripts/Refresh-R39.5.1LearningHeartbeatRuntime-PS51.ps1")
    assert "Invoke-R39.3.3AttentionHeartbeat-Core-PS51.ps1" in text
    assert "Invoke-R39.4.1AttentionHeartbeat-Core-PS51.ps1" in text
    assert "Invoke-R39.5.1AttentionHeartbeat-Wrapper-PS51.ps1" in text
    assert "Copy-Item -Force -LiteralPath $r3951WrapperPath -Destination $taskPath" in text
    assert "stable_task_action_path" in text
    assert "scheduler_xml_change_authorized = $false" in text
    assert "scheduler XML changed during runtime refresh" in text


def test_runtime_refresh_requires_exact_approval_and_full_stack_preflight():
    text = read("scripts/Refresh-R39.5.1LearningHeartbeatRuntime-PS51.ps1")
    assert "APPROVE_R39_5_1_RUNTIME_REFRESH:" in text
    assert "exact R39.5.1 runtime refresh approval command mismatch" in text
    assert "R39_5_1_LEARNING_INTEGRATION_RECEIPT.json" in text
    assert "preflight learning_pending=true" in text
    assert "preflight effects nonzero" in text
    assert "runtime backup missing during rollback" in text


def test_runtime_refresh_uses_live_lease_without_stealing_unowned_lock():
    text = read("scripts/Refresh-R39.5.1LearningHeartbeatRuntime-PS51.ps1")
    assert "R39_3_3_ATTENTION.lease" in text
    assert "FileMode]::CreateNew" in text
    assert "live_attention_lease_busy" in text
    assert "$leaseOwned = $false" in text
    assert "$leaseOwned = $true" in text
    assert "if ($leaseOwned -and (Test-Path -LiteralPath $liveLease -PathType Leaf))" in text
    assert "Register-ScheduledTask" not in text
    assert "Unregister-ScheduledTask" not in text
    assert "Set-ScheduledTask" not in text
    assert "Start-ScheduledTask" not in text
