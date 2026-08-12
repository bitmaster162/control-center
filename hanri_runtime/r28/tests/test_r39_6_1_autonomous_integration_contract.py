from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

WRAPPER = (SCRIPTS / "Invoke-R39.6.1AttentionHeartbeat-Wrapper-PS51.ps1").read_text(encoding="utf-8")
RUNNER = (SCRIPTS / "Run-R39.6.1BoundedRecommendationsLive-PS51.ps1").read_text(encoding="utf-8")
REFRESH = (SCRIPTS / "Refresh-R39.6.1RecommendationHeartbeatRuntime-PS51.ps1").read_text(encoding="utf-8")


def test_wrapper_layers_over_r39_5_1_core():
    assert "Invoke-R39.5.1AttentionHeartbeat-Core-PS51.ps1" in WRAPPER
    assert "Run-R39.6.1BoundedRecommendationsLive-PS51.ps1" in WRAPPER
    assert "Invoke-R39.5.1AttentionHeartbeat-Wrapper-PS51.ps1" not in WRAPPER


def test_wrapper_denies_stale_learning():
    assert "UPSTREAM_LEARNING_PENDING" in WRAPPER
    assert "stale recommendation compilation denied" in WRAPPER
    assert "UPSTREAM_EFFECTS_NONZERO" in WRAPPER
    assert "LEARNING_EFFECTS_NONZERO" in WRAPPER


def test_wrapper_runs_on_learning_or_pending_missing_or_stale():
    assert "$upstream.learning_executed" in WRAPPER
    assert "$pendingPath" in WRAPPER
    assert "$recommendationMissing" in WRAPPER
    assert "$recommendationStale" in WRAPPER
    assert "source_learning_state_sha256" in WRAPPER


def test_wrapper_has_retry_marker_without_effect_authority():
    assert "R39_6_1_RECOMMENDATION_PENDING.json" in WRAPPER
    assert "retry_on_next_heartbeat = $true" in WRAPPER
    assert "self_apply = $false" in WRAPPER
    assert "system_write = $false" in WRAPPER
    assert "operator_message = $false" in WRAPPER
    assert "capital_permission = 'DENY'" in WRAPPER


def test_runner_binds_exact_learning_receipt_state_and_cycle():
    assert "learning receipt/state SHA binding mismatch" in RUNNER
    assert "integration/learning semantic cycle mismatch" in RUNNER
    assert "upstream learning receipt SHA mismatch" in RUNNER
    assert "recommendation source learning state SHA mismatch" in RUNNER
    assert "recommendation source learning digest mismatch" in RUNNER


def test_runner_requires_human_review_and_no_execution_authority():
    assert "PENDING_HUMAN_REVIEW" in RUNNER
    assert "PROPOSAL_ONLY" in RUNNER
    assert "execution_authority -ne 'NONE'" in RUNNER
    assert "self_apply_authorized" in RUNNER
    assert "install_authorized" in RUNNER
    assert "system_write_authorized" in RUNNER
    assert "operator_message_authorized" in RUNNER


def test_refresh_preserves_full_wrapper_chain_at_stable_path():
    assert "Invoke-R39.3.3AttentionHeartbeat-Core-PS51.ps1" in REFRESH
    assert "Invoke-R39.4.1AttentionHeartbeat-Core-PS51.ps1" in REFRESH
    assert "Invoke-R39.5.1AttentionHeartbeat-Core-PS51.ps1" in REFRESH
    assert "Invoke-R39.6.1AttentionHeartbeat-Wrapper-PS51.ps1" in REFRESH
    assert "Invoke-R39.3.3AttentionHeartbeat-PS51.ps1" in REFRESH


def test_refresh_requires_new_exact_approval_namespace():
    assert "APPROVE_R39_6_1_RUNTIME_REFRESH:" in REFRESH
    assert "APPROVE_R39_5_1_RUNTIME_REFRESH:" not in REFRESH


def test_refresh_preflights_r39_6_1_before_live_swap():
    assert "R39_6_1_RECOMMENDATION_INTEGRATION_RECEIPT.json" in REFRESH
    assert "39.6.1-autonomous-recommendation-integration-v1" in REFRESH
    assert "recommendation_pending" in REFRESH
    preflight = REFRESH.index("R39.6.1 staged heartbeat preflight failed")
    move_live = REFRESH.index("Move-Item -LiteralPath $InstallRoot -Destination $backup")
    assert preflight < move_live


def test_refresh_lease_cleanup_is_owner_guarded():
    assert "$leaseOwned = $false" in REFRESH
    assert "if ($leaseOwned -and (Test-Path -LiteralPath $liveLease" in REFRESH


def test_no_manual_scheduler_trigger():
    combined = WRAPPER + RUNNER + REFRESH
    assert "Start-ScheduledTask" not in combined
    assert "Register-ScheduledTask" not in combined
    assert "Set-ScheduledTask" not in combined


def test_full_zero_effect_boundary_is_present():
    for script in (WRAPPER, RUNNER):
        for token in (
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
            "can_trade",
            "capital_permission",
        ):
            assert token in script
