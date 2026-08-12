from __future__ import annotations

import json
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
CONFIG = RUNTIME / "config" / "r39.3.3.scheduler-package.json"
RUNNER = RUNTIME / "scripts" / "Run-R39.3.3AttentionHeartbeat-PS51.ps1"
INSTALLER = RUNTIME / "scripts" / "Install-R39.3.3AttentionScheduler-PS51.ps1"
VERIFY = RUNTIME / "scripts" / "Verify-R39.3.3AttentionScheduler-PS51.ps1"
RESTORE = RUNTIME / "scripts" / "Restore-R39.3.3AttentionScheduler-PS51.ps1"


def test_scheduler_package_policy_is_bounded() -> None:
    policy = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert policy["policy_version"] == "39.3.3-host-scheduler-package-v1"
    assert policy["task"]["name"] == "ControlCenter-HANRI-R39-Attention"
    assert policy["task"]["heartbeat_minutes"] == 5
    assert policy["task"]["multiple_instances"] == "IgnoreNew"
    assert policy["task"]["execution_time_limit_minutes"] == 10
    assert policy["runtime"]["git_worktree_dependency"] is False
    assert policy["runtime"]["semantic_hash_algorithm"] == "SEMANTIC_ENVELOPE_V2"
    boundary = policy["effect_boundary"]
    assert boundary["r36_task_modify"] is False
    assert boundary["provider_calls"] is False
    assert boundary["human_decision_execution"] is False
    assert boundary["self_apply"] is False
    assert boundary["auto_dispatch"] is False
    assert boundary["can_trade"] is False
    assert boundary["capital_permission"] == "DENY"


def test_production_heartbeat_has_no_test_or_git_hot_path() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "pytest" not in text
    assert "git " not in text.lower()
    assert "producer_adapters_operator_receipts_cli" in text
    assert "attention_fabric_semantic_cli" in text
    assert "continuous_attention_loop_semantic_cli" in text
    assert "attention_cadence_cli" in text
    assert "R39_3_3_CADENCE_PROBE_STATE.json" in text
    assert "SKIP_NOT_DUE" in text
    assert "SKIP_OVERLAP" in text
    assert "RUN_FULL_ATTENTION" in text
    assert "FileShare]::None" in text
    assert "EXECUTION_EFFECTS_PERFORMED 0" in text


def test_installer_is_apply_gated_and_side_by_side_with_r36() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    dry = text.index("if (-not $Apply)")
    register = text.index("Register-ScheduledTask -TaskName $TaskName")
    assert dry < register
    assert "-ExpectedCommit and -ExpectedTree are required with -Apply" in text
    assert "RepetitionInterval (New-TimeSpan -Minutes 5)" in text
    assert "-MultipleInstances IgnoreNew" in text
    assert "-ExecutionTimeLimit (New-TimeSpan -Minutes 10)" in text
    assert "ControlCenter-HANRI-R39-Attention" in text
    assert "ControlCenter-HANRI-R36" in text
    assert "R36 Scheduled Task XML changed during R39.3.3 install" in text
    assert "Disable-ScheduledTask -TaskName $R36TaskName" not in text
    assert "Unregister-ScheduledTask -TaskName $R36TaskName" not in text
    assert "Stop-ScheduledTask -TaskName $R36TaskName" not in text
    assert "scheduler_installed = $true" in text
    assert "can_trade = $false" in text
    assert "capital_permission = 'DENY'" in text


def test_installer_pins_runtime_and_human_decision_evidence() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "Copy-Item -Recurse -Force \"$SourceRoot\\*\" $InstallRuntime" in text
    assert "D1_D5_DECISION_RECEIPT.json" in text
    assert "installed human decision receipt SHA mismatch" in text
    assert "INSTALL_MANIFEST.json" in text
    assert "human_decision_receipt_sha256" in text
    assert "Run-R39.3.3AttentionHeartbeat-PS51.ps1" in text
    assert "manual preflight heartbeat failed" in text
    assert "scheduled heartbeat did not produce fresh receipt" in text


def test_verifier_is_read_only_and_checks_exact_task_contract() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    assert "Register-ScheduledTask" not in text
    assert "Unregister-ScheduledTask" not in text
    assert "Start-ScheduledTask" not in text
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in text
    assert "<Interval>PT5M</Interval>" in text
    assert "<ExecutionTimeLimit>PT10M</ExecutionTimeLimit>" in text
    assert "R36 Scheduled Task XML no longer matches install baseline" in text
    assert "EXECUTION_EFFECTS_PERFORMED 0" in text


def test_restore_is_separately_apply_gated_and_never_mutates_r36() -> None:
    text = RESTORE.read_text(encoding="utf-8")
    dry = text.index("if (-not $Apply)")
    unregister = text.index("Unregister-ScheduledTask -TaskName $TaskName")
    assert dry < unregister
    assert "Register-ScheduledTask -TaskName $TaskName" in text
    assert "R36 Scheduled Task changed during R39.3.3 rollback" in text
    assert "Disable-ScheduledTask -TaskName $R36TaskName" not in text
    assert "Unregister-ScheduledTask -TaskName $R36TaskName" not in text
    assert "Stop-ScheduledTask -TaskName $R36TaskName" not in text
    assert "can_trade = $false" in text
    assert "capital_permission = 'DENY'" in text
