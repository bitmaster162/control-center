import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CONFIG = ROOT / "config" / "r39.3.3.host-scheduler.json"


def text(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_scheduler_policy_is_effect_gated_and_static_heartbeat():
    policy = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert policy["policy_version"] == "39.3.3-host-scheduler-package-v1"
    assert policy["heartbeat_minutes"] == 5
    assert policy["execution_time_limit_minutes"] == 10
    assert policy["multiple_instances"] == "IgnoreNew"
    assert policy["effect_boundary"]["install_authorized"] is False
    assert policy["effect_boundary"]["scheduler_install_requires_exact_approval"] is True
    assert policy["effect_boundary"]["dynamic_scheduler_reconfiguration"] is False
    assert policy["effect_boundary"]["can_trade"] is False
    assert policy["effect_boundary"]["capital_permission"] == "DENY"


def test_installer_defaults_to_plan_and_requires_exact_hash_approval():
    s = text("Install-R39.3.3AttentionTask-PS51.ps1")
    assert "[switch]$Apply" in s
    assert "APPROVE_R39_3_3_SCHEDULER:" in s
    assert "if (-not $Apply)" in s
    assert "exact scheduler approval command mismatch" in s
    assert "task precondition changed after approval plan" in s
    assert "source manifest changed after approval plan" in s
    assert "Register-ScheduledTask" in s
    assert "MultipleInstances IgnoreNew" in s
    assert "backup_existing" not in s.lower() or "taskBackup" in s
    assert "rollbackPerformed" in s
    assert "preflight" in s.lower()


def test_heartbeat_commits_cadence_only_after_successful_full_loop():
    s = text("Invoke-R39.3.3AttentionHeartbeat-PS51.ps1")
    loop_call = s.index("-File $loopRunner")
    loop_gate = s.index("full_attention_loop_failed")
    cadence_call = s.index("hanri.attention_cadence_cli")
    assert loop_call < loop_gate < cadence_call
    assert "cadence_state_exists_but_loop_receipt_missing" in s
    assert "SKIP_OVERLAP" in s
    assert "leaseMinutes = 10" in s
    assert "provider_calls = $false" in s
    assert "can_trade = $false" in s
    assert "capital_permission = 'DENY'" in s


def test_scheduled_full_loop_has_no_regression_or_git_hot_path():
    heartbeat = text("Invoke-R39.3.3AttentionHeartbeat-PS51.ps1")
    production = text("Run-R39.3.3ProductionAttentionLoop-PS51.ps1")
    assert "Run-R39.3.3ProductionAttentionLoop-PS51.ps1" in heartbeat
    assert "Run-R39.3.1SemanticContinuousAttentionLoop-PS51.ps1" not in heartbeat
    assert "pytest" not in production
    assert "git " not in production.lower()
    assert "producer_adapters_operator_receipts_cli" in production
    assert "attention_fabric_semantic_cli" in production
    assert "continuous_attention_loop_semantic_cli" in production
    assert "SEMANTIC_ENVELOPE_V2" in production
    assert "attention_coverage_not_complete" in production
    assert "provider_calls=true" in production
    assert "can_trade=true" in production
    assert "capital_permission_not_DENY" in production


def test_install_is_reversible_and_has_post_write_readback():
    s = text("Install-R39.3.3AttentionTask-PS51.ps1")
    assert "Export-ScheduledTask" in s
    assert "prior_task_xml_backup" in s
    assert "prior_app_backup" in s
    assert "Unregister-ScheduledTask" in s
    assert "Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force" in s
    assert "post_write_readback_verified = $true" in s
    assert "after_task_xml_sha256" in s


def test_uninstall_is_separately_hash_gated_and_restores_prior_task():
    s = text("Uninstall-R39.3.3AttentionTask-PS51.ps1")
    assert "APPROVE_R39_3_3_UNINSTALL:" in s
    assert "exact uninstall approval command mismatch" in s
    assert "prior_task_xml_backup" in s
    assert "Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force" in s
    assert "retired" in s


def test_verifier_binds_task_xml_and_installed_heartbeat():
    s = text("Verify-R39.3.3AttentionTask-PS51.ps1")
    assert "after_task_xml_sha256" in s
    assert "MultipleInstancesPolicy" in s
    assert "Invoke-R39.3.3AttentionHeartbeat-PS51.ps1" in s
    assert "HANRI_R39_3_3_SCHEDULER_VERIFY_PASS" in s
