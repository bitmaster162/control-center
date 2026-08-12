from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_wrapper_preserves_stable_task_path_via_core_split():
    text = read("scripts/Invoke-R39.4.1AttentionHeartbeat-Wrapper-PS51.ps1")
    assert "Invoke-R39.3.3AttentionHeartbeat-Core-PS51.ps1" in text
    assert "Run-R39.4.1OutcomeIntelligenceLive-PS51.ps1" in text
    assert "R39_4_1_OUTCOME_PENDING.json" in text
    assert "full_loop_executed" in text
    assert "OUTCOME_PENDING_RETRY" in text


def test_wrapper_retries_pending_outcome_and_surfaces_failure():
    text = read("scripts/Invoke-R39.4.1AttentionHeartbeat-Wrapper-PS51.ps1")
    assert "$needOutcome = [bool]$core.full_loop_executed -or" in text
    assert "retry_on_next_heartbeat = $true" in text
    assert "exit 1" in text
    assert "execution_effects_performed = 0" in text


def test_live_sidecar_is_zero_effect_and_metric_semantics_v2():
    text = read("scripts/Run-R39.4.1OutcomeIntelligenceLive-PS51.ps1")
    assert "hanri.outcome_intelligence_semantic_cli" in text
    assert "39.4.0.1-outcome-intelligence-metric-semantics-v1" in text
    for forbidden_true in (
        "scheduler_install=true",
        "scheduler_modify=true",
        "self_apply=true",
        "provider_calls=true",
    ):
        assert forbidden_true not in text


def test_runtime_refresh_requires_exact_approval_and_preserves_scheduler_xml():
    text = read("scripts/Refresh-R39.4.1OutcomeHeartbeatRuntime-PS51.ps1")
    assert "APPROVE_R39_4_1_RUNTIME_REFRESH:" in text
    assert "exact runtime refresh approval command mismatch" in text
    assert "scheduler XML changed during runtime refresh" in text
    assert "scheduler_modified = $false" in text
    assert "scheduler_xml_unchanged = $true" in text


def test_runtime_refresh_uses_same_live_lease_and_never_registers_task():
    text = read("scripts/Refresh-R39.4.1OutcomeHeartbeatRuntime-PS51.ps1")
    assert "R39_3_3_ATTENTION.lease" in text
    assert "FileMode]::CreateNew" in text
    assert "live_attention_lease_busy" in text
    assert "Register-ScheduledTask" not in text
    assert "Unregister-ScheduledTask" not in text
    assert "Set-ScheduledTask" not in text


def test_runtime_refresh_transforms_staged_runtime_not_repo_task_action():
    text = read("scripts/Refresh-R39.4.1OutcomeHeartbeatRuntime-PS51.ps1")
    assert "Invoke-R39.3.3AttentionHeartbeat-Core-PS51.ps1" in text
    assert "Invoke-R39.4.1AttentionHeartbeat-Wrapper-PS51.ps1" in text
    assert "Copy-Item -Force -LiteralPath $wrapperPath -Destination $taskPath" in text
    assert "stable_task_action_path" in text
    assert "$swapStarted = $true" in text
    assert "runtime backup missing during rollback" in text


def test_policy_keeps_effect_ceiling_closed():
    import json
    cfg = json.loads(read("config/r39.4.1.live-heartbeat-integration.json"))
    assert cfg["policy_version"] == "39.4.1-live-heartbeat-integration-v1"
    b = cfg["effect_boundary"]
    assert b["can_trade"] is False
    assert b["capital_permission"] == "DENY"
    for key in (
        "provider_calls",
        "scheduler_install",
        "scheduler_modify",
        "self_apply",
        "skill_install",
        "system_write",
        "operator_message",
        "auto_dispatch",
        "external_messages",
    ):
        assert b[key] is False
