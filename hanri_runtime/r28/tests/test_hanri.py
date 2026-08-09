from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from hanri.truth import (audit_authority_surfaces, audit_occurrence_family, audit_partition, audit_recovery_provenance, recovery_provenance_audit_event, truth_kernel_audit_event)
from hanri.archive import (
    build_scope_coverage_certificate,
    classify_content,
    inspect_file,
    scan_causal_spine,
    scan_frontier_pair,
    select_frontier_pair,
)
from hanri.cli import (
    evaluate_event,
    falsify_candidate,
    load_json,
    make_candidate,
    make_finding,
    process_once,
    record_decision,
    record_event,
    sanitize,
    sha256_bytes,
    validate_event,
)


def base_event(**checks):
    return validate_event({
        "event_id": "event-1",
        "timestamp": "2026-07-22T00:00:00Z",
        "task_id": "TASK-1",
        "step_id": "STEP-1",
        "event_type": "STEP_END",
        "actor": "TEST",
        "goal": "Test",
        "human_summary": "Test event",
        "recursion_depth": 0,
        "checks": checks,
        "evidence_refs": [{"type": "TEST", "sha256": "a" * 64}],
        "can_trade": False,
    })


class RuleTests(unittest.TestCase):
    def test_user_completion_blocks_rerun_and_missing_without_coverage(self) -> None:
        event = base_event(
            user_confirmed_completion=True,
            rerun_requested=True,
            negative_claim="MISSING",
            coverage_certificate_present=False,
        )
        codes, stop = evaluate_event(event, 2)
        self.assertIn("RERUN_AFTER_USER_COMPLETION", codes)
        self.assertIn("NEGATIVE_CLAIM_WITHOUT_COVERAGE", codes)
        self.assertIsNone(stop)

    def test_tool_success_is_not_effect(self) -> None:
        event = base_event(tool_success=True, declared_complete=True, effect_rung="PROVIDER_RESPONSE")
        codes, _ = evaluate_event(event, 2)
        self.assertIn("TOOL_EFFECT_CONFUSION", codes)

    def test_git_baseline_and_temporal_leakage(self) -> None:
        event = base_event(
            persistent_write=True,
            git_baseline_verified=False,
            simulation_promoted_to_present=True,
        )
        codes, _ = evaluate_event(event, 2)
        self.assertIn("GIT_BASELINE_BYPASS", codes)
        self.assertIn("TEMPORAL_LEAKAGE", codes)

    def test_no_material_delta_stops_recursion(self) -> None:
        event = base_event()
        event["recursion_depth"] = 1
        codes, stop = evaluate_event(event, 2)
        self.assertIn("NO_MATERIAL_DELTA_RECURSION", codes)
        self.assertEqual(stop, "STOP_NO_MATERIAL_DELTA")

    def test_depth_above_two_stops(self) -> None:
        event = base_event(changed_evidence=True)
        event["recursion_depth"] = 3
        codes, stop = evaluate_event(event, 2)
        self.assertIn("RECURSION_DEPTH_EXCEEDED", codes)
        self.assertEqual(stop, "STOP_RECURSION_DEPTH_EXCEEDED")

    def test_duplicate_evidence_is_detected(self) -> None:
        event = base_event(evidence_occurrences=4, independent_evidence_families=1)
        codes, _ = evaluate_event(event, 2)
        self.assertIn("EVIDENCE_DOUBLE_COUNT", codes)

    def test_false_interiority_and_persona_confusion(self) -> None:
        event = base_event(sentience_claim=True, function_claimed_as_independent_agent=True)
        codes, _ = evaluate_event(event, 2)
        self.assertIn("FALSE_BACKGROUND_OR_INTERIORITY", codes)
        self.assertIn("PERSONA_AGENT_CONFUSION", codes)

    def test_dual_native_and_correction_learning(self) -> None:
        event = base_event(
            human_ai_views_disagree=True,
            correction_material=True,
            regression_case_created=False,
        )
        event["event_type"] = "OPERATOR_FEEDBACK"
        codes, _ = evaluate_event(event, 2)
        self.assertIn("DUAL_NATIVE_MISMATCH", codes)
        self.assertIn("CORRECTION_NOT_REGRESSION", codes)

    def test_human_agency_stack_and_p0_precedence(self) -> None:
        event = base_event(
            high_risk_or_irreversible=True,
            human_approval_present=False,
            stack_selected_before_equal_tests=True,
            known_p0_open=True,
            feature_or_expansion_work_started=True,
        )
        codes, _ = evaluate_event(event, 2)
        self.assertIn("HUMAN_AGENCY_BYPASS", codes)
        self.assertIn("PREMATURE_STACK_SELECTION", codes)
        self.assertIn("P0_PRECEDENCE_BREACH", codes)


    def test_archive_classification_version_scope_and_coverage_rules(self) -> None:
        event = base_event(
            content_classification_claimed=True,
            content_signature_verified=False,
            same_name_multiple_hashes=True,
            version_lineage_recorded=False,
            metric_claim_present=True,
            metric_scope_bound=False,
            same_label_multiple_entities=True,
            entity_ids_bound=False,
            security_debt_deferred=True,
            security_debt_owner_expiry_trigger_present=False,
            coverage_percent_claimed=True,
            per_file_coverage_ledger_present=False,
        )
        codes, _ = evaluate_event(event, 2)
        self.assertIn("CONTENT_CLASSIFICATION_WITHOUT_BYTE_INSPECTION", codes)
        self.assertIn("SAME_NAME_VERSION_COLLISION", codes)
        self.assertIn("METRIC_SCOPE_UNBOUND", codes)
        self.assertIn("ENTITY_IDENTITY_AMBIGUITY", codes)
        self.assertIn("DEFERRED_SECURITY_DEBT_EXPIRED", codes)
        self.assertIn("COVERAGE_CLAIM_WITHOUT_FILE_LEDGER", codes)

    def test_bidirectional_frontier_requires_both_sides(self) -> None:
        event = base_event(origin_frontier_processed=True, current_frontier_processed=False)
        event["event_type"] = "ARCHIVE_FRONTIER_ADVANCE"
        codes, _ = evaluate_event(event, 2)
        self.assertIn("BIDIRECTIONAL_FRONTIER_IMBALANCE", codes)


    def test_scope_liveness_root_cause_repo_and_cursor_rules(self) -> None:
        event = base_event(
            completeness_claim_present=True,
            coverage_scope_bound=False,
            historical_liveness_claim=True,
            current_liveness_claimed=True,
            fresh_target_readback=False,
            probe_count_promoted_as_root_cause_count=True,
            filesystem_root_exists=True,
            repository_root_claimed=True,
            git_toplevel_verified=False,
            primary_secondary_cursor_equated=True,
        )
        codes, _ = evaluate_event(event, 2)
        self.assertIn("COMPLETENESS_SCOPE_LEAKAGE", codes)
        self.assertIn("HISTORICAL_LIVENESS_PROMOTION", codes)
        self.assertIn("PROBE_ROOT_CAUSE_CONFLATION", codes)
        self.assertIn("ROOT_REPOSITORY_CONFLATION", codes)
        self.assertIn("PRIMARY_SECONDARY_CURSOR_CONFLATION", codes)

    def test_causal_spine_requires_pivot(self) -> None:
        event = base_event(
            origin_frontier_processed=True,
            pivot_frontier_processed=False,
            current_frontier_processed=True,
        )
        event["event_type"] = "ARCHIVE_CAUSAL_SPINE"
        codes, _ = evaluate_event(event, 2)
        self.assertIn("CAUSAL_SPINE_GAP", codes)

    def test_candidate_requires_human_gate_and_passes_falsification(self) -> None:
        event = base_event(tool_success=True, declared_complete=True, effect_rung="TOOL_INVOKED")
        event_sha = sha256_bytes(json.dumps(event, sort_keys=True).encode())
        finding = make_finding(event, "TOOL_EFFECT_CONFUSION", event_sha)
        candidate = make_candidate(event, finding)
        self.assertFalse(candidate["self_apply"])
        self.assertEqual(candidate["authority"], "HUMAN_REVIEW_REQUIRED")
        result = falsify_candidate(candidate, 2)
        self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")


class ArchiveFrontierTests(unittest.TestCase):
    def test_systempack_and_zxcvbn_are_not_conflated(self) -> None:
        systempack = "# SYSTEMPACK_STRICT\n# >>> segment_trading.md\ncontent"
        wordlist = "the\nof\nand\nin\nwas\n"
        self.assertEqual(classify_content(Path("systempack_strict.md"), systempack), "SYSTEMPACK_PROJECT_CORPUS")
        self.assertEqual(
            classify_content(Path("browser/ZxcvbnData/3/english_wikipedia.txt"), wordlist),
            "ZXC_VBN_WORDLIST",
        )

    def test_same_name_collision_and_two_frontiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            current = root / "current"
            origin.mkdir()
            current.mkdir()
            (origin / "report.md").write_text("old", encoding="utf-8")
            (current / "report.md").write_text("new", encoding="utf-8")
            pair = select_frontier_pair([origin], [current])
            self.assertEqual(pair["status"], "PAIR_READY")
            self.assertEqual(len(pair["same_name_collisions"]), 1)
            self.assertTrue(pair["origin"]["content_signature_verified"])
            self.assertTrue(pair["current"]["content_signature_verified"])

    def test_inventory_cache_reuses_unchanged_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            current = root / "current"
            origin.mkdir()
            current.mkdir()
            (origin / "a.md").write_text("origin", encoding="utf-8")
            (current / "b.md").write_text("current", encoding="utf-8")
            first, cache = scan_frontier_pair([origin], [current])
            second, cache2 = scan_frontier_pair([origin], [current], inventory_cache=cache)
            self.assertEqual(first["origin"]["sha256"], second["origin"]["sha256"])
            self.assertEqual(first["current"]["sha256"], second["current"]["sha256"])
            self.assertEqual(len(cache), len(cache2))


    def test_causal_spine_and_scope_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            pivot = root / "pivot"
            current = root / "current"
            for folder in (origin, pivot, current):
                folder.mkdir()
            (origin / "origin.md").write_text("initial goal", encoding="utf-8")
            (pivot / "pivot.md").write_text("operator correction", encoding="utf-8")
            (current / "current.md").write_text("physical current state", encoding="utf-8")
            spine, cache = scan_causal_spine([origin], [pivot], [current], scope_id="TEST_SCOPE")
            self.assertEqual(spine["status"], "SPINE_READY")
            self.assertEqual(spine["coverage_certificate"]["scope_id"], "TEST_SCOPE")
            self.assertEqual(spine["coverage_certificate"]["denominator"], 3)
            self.assertEqual(len(cache), 3)

    def test_scope_certificate_is_manifest_bound(self) -> None:
        rows = [
            {"path": "/a", "sha256": "a" * 64, "size_bytes": 1, "content_class": "TEXT", "full_text_read": True},
            {"path": "/b", "sha256": "b" * 64, "size_bytes": 2, "content_class": "TEXT", "full_text_read": False},
        ]
        certificate = build_scope_coverage_certificate("SCOPE-1", rows)
        self.assertEqual(certificate["coverage_ratio"], "1/2")
        self.assertEqual(certificate["status"], "PARTIAL")
        self.assertEqual(len(certificate["scope_manifest_sha256"]), 64)



class SanitizationTests(unittest.TestCase):
    def test_secret_value_is_replaced_by_fingerprint(self) -> None:
        findings = []
        value = sanitize({"message": "token sk-" + "x" * 30}, findings)
        self.assertNotIn("sk-", value["message"])
        self.assertEqual(len(findings), 1)
        self.assertIn("value_sha256", findings[0])


class IntegrationTests(unittest.TestCase):
    def make_config(self, root: Path) -> Path:
        config = {
            "schema_version": 1,
            "program_version": "26.0.0",
            "shadow_only": True,
            "external_model_api": "DENY",
            "can_trade": False,
            "max_recursion_depth": 2,
            "state_root": str(root / "state"),
            "lock_file": str(root / "state" / "lock"),
            "event_inbox": str(root / "events"),
            "decision_inbox": str(root / "decisions"),
            "human_output_root": str(root / "human"),
            "current_state_paths": [],
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_dual_native_outputs_and_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            event = base_event(
                user_confirmed_completion=True,
                rerun_requested=True,
                avoidable_operator_burden=True,
            )
            recorded = record_event(config, None, json.dumps(event))
            self.assertEqual(recorded["status"], "RECORDED")
            receipt = process_once(config)
            self.assertGreaterEqual(receipt["findings_generated"], 2)
            state = load_json(root / "state" / "latest_ai_state.json")
            self.assertGreaterEqual(state["pending_human_decisions"], 2)
            digest = (root / "state" / "latest_human_digest.md").read_text(encoding="utf-8")
            self.assertIn("Human Decision Digest", digest)
            self.assertTrue((root / "human" / "latest_ai_state.json").exists())
            candidates = [json.loads(line) for line in (root / "state" / "candidate_delta_ledger.jsonl").read_text().splitlines()]
            decision = {
                "candidate_id": candidates[0]["candidate_id"],
                "verdict": "ACCEPT",
                "operator": "Robert",
                "can_trade": False,
            }
            record_decision(config, None, json.dumps(decision))
            process_once(config)
            digest2 = (root / "state" / "latest_human_digest.md").read_text(encoding="utf-8")
            self.assertIn("ACCEPT", digest2)

    def test_event_is_processed_once_by_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self.make_config(root)
            record_event(config, None, json.dumps(base_event(background_claim=True)))
            first = process_once(config)
            second = process_once(config)
            self.assertEqual(first["events_processed"], 1)
            self.assertEqual(second["events_processed"], 0)



class TruthKernelR27Tests(unittest.TestCase):
    def test_handoff_collector_disjoint_partition(self) -> None:
        audit = audit_partition(
            universe_id="HANDOFF_CANDIDATE_ROWS",
            total=206,
            components={"safe_unique_representatives": 99, "safe_duplicate_occurrences": 84, "unsafe_or_excluded_occurrences": 23},
            declared_disjoint=True,
        )
        self.assertEqual(audit["status"], "PASS")

    def test_handoff_report_mixed_universe_fails(self) -> None:
        audit = audit_partition(
            universe_id="HANDOFF_CANDIDATE_ROWS_MIXED",
            total=206,
            components={"safe_unique_representatives": 99, "all_duplicate_occurrences": 85, "unsafe_or_excluded_occurrences": 23},
            declared_disjoint=True,
        )
        self.assertEqual(audit["status"], "ARITHMETIC_PARTITION_INCONSISTENCY")
        self.assertEqual(audit["delta"], 1)

    def test_checkpoint_universes_are_not_one_partition(self) -> None:
        mixed = audit_partition(
            universe_id="STRONG_PROGRESS_MIXED_WITH_ALL_RECORDS",
            total=787,
            components={"evidenced_all_970": 327, "claimed_strong_progress": 551},
            declared_disjoint=True,
        )
        self.assertEqual(mixed["status"], "ARITHMETIC_PARTITION_INCONSISTENCY")
        correct_all = audit_partition(
            universe_id="ALL_CHECKPOINT_RECORDS",
            total=970,
            components={"evidenced": 327, "at_most_claimed": 643},
            declared_disjoint=True,
        )
        self.assertEqual(correct_all["status"], "PASS")

    def test_occurrence_family_dedup(self) -> None:
        rows = [{"path": f"copy-{i}", "sha256": "a" * 64} for i in range(5)]
        audit = audit_occurrence_family(rows)
        self.assertEqual(audit["occurrence_count"], 5)
        self.assertEqual(audit["unique_family_count"], 1)
        self.assertEqual(audit["duplicate_occurrence_count"], 4)

    def test_multiple_authority_surfaces_fail_without_broker(self) -> None:
        audit = audit_authority_surfaces([
            {"surface_id": "continuity_runtime", "root_or_target": "C:/PROJECTS/continuity_os", "mutable": True, "current_authority": True},
            {"surface_id": "sibling_package", "root_or_target": "C:/PROJECTS/continuityos", "mutable": True, "current_authority": True},
        ], single_effect_broker_verified=False)
        self.assertEqual(audit["status"], "AUTHORITY_SURFACE_MULTIPLICITY")

    def test_truth_kernel_event_maps_new_failure_classes(self) -> None:
        partition = audit_partition(
            universe_id="MIXED",
            total=10,
            components={"a": 7, "b": 7},
            declared_disjoint=True,
        )
        authority = audit_authority_surfaces([
            {"surface_id": "a", "mutable": True, "current_authority": True},
            {"surface_id": "b", "mutable": True, "current_authority": True},
        ], single_effect_broker_verified=False)
        event = truth_kernel_audit_event(
            task_id="R27",
            step_id="audit",
            partition_audits=[partition],
            authority_audit=authority,
            count_universes_mixed=True,
            spec_claimed_current_implementation=True,
            implementation_receipt_present=False,
            proof_ledger_claimed=True,
            proof_identity_fields_present=False,
        )
        codes, _ = evaluate_event(event, 2)
        for code in [
            "ARITHMETIC_PARTITION_INCONSISTENCY",
            "COUNT_UNIVERSE_CONFLATION",
            "AUTHORITY_SURFACE_MULTIPLICITY",
            "SPEC_IMPLEMENTATION_CONFLATION",
            "PROOF_LEDGER_SCHEMA_GAP",
        ]:
            self.assertIn(code, codes)


if __name__ == "__main__":
    unittest.main()


class RecoveryProvenanceR28Tests(unittest.TestCase):
    def test_recovery_audit_detects_self_ingestion_and_secret_scope_defects(self) -> None:
        artifacts = [
            {
                "artifact_id": "primary-1",
                "path": "project/HANDOFF.md",
                "sha256": "a" * 64,
                "artifact_role": "PRIMARY_SOURCE",
                "derivation_depth": 0,
                "copied": True,
                "primary_source_eligible": True,
                "secret_finding_count": 0,
            },
            {
                "artifact_id": "collector-ledger",
                "path": "handoff_recovery/old/HANDOFF_CANDIDATES.csv",
                "sha256": "b" * 64,
                "artifact_role": "RECOVERY_SELF_DERIVATIVE",
                "derivation_depth": 1,
                "copied": True,
                "primary_source_eligible": False,
                "secret_finding_count": 0,
            },
            {
                "artifact_id": "secret-bearing",
                "path": "Cowork/HANDOFF_OPUS.md",
                "sha256": "c" * 64,
                "artifact_role": "RESTRICTED_SECRET_BEARING",
                "derivation_depth": 0,
                "copied": True,
                "primary_source_eligible": False,
                "secret_finding_count": 2,
            },
        ]
        audit = audit_recovery_provenance(
            artifacts,
            credential_values_output_false=True,
            no_source_effect_proof_claimed=True,
            no_secret_content_proof_inferred=True,
            claimed_primary_coverage_count=3,
            unsafe_count_label="excluded_pointer_only",
            unsafe_non_pointer_count=2,
            secret_scanner_claimed_complete=True,
            secret_findings_escaped_scan=2,
        )
        self.assertEqual(audit["status"], "REVISE")
        expected = {
            "RECOVERY_SELF_INGESTION",
            "CONTENT_SECRET_SAFETY_FALSE_CLAIM",
            "CONTROL_ARTIFACT_COVERAGE_INFLATION",
            "PROOF_SCOPE_CONFLATION",
            "UNSAFE_ROW_LABEL_MISMATCH",
            "SECRET_SCANNER_COVERAGE_GAP",
        }
        self.assertEqual(set(audit["statuses"]), expected)
        event = recovery_provenance_audit_event(task_id="R28", step_id="recovery", audit=audit)
        codes, _ = evaluate_event(event, 2)
        self.assertEqual(set(codes), expected)

    def test_recovery_audit_passes_with_separate_proofs_and_primary_counts(self) -> None:
        audit = audit_recovery_provenance(
            [{
                "artifact_id": "primary-1",
                "path": "project/HANDOFF.md",
                "sha256": "a" * 64,
                "artifact_role": "PRIMARY_SOURCE",
                "derivation_depth": 0,
                "copied": True,
                "primary_source_eligible": True,
                "secret_finding_count": 0,
            }],
            credential_values_output_false=True,
            no_source_effect_proof_claimed=True,
            no_secret_content_proof_inferred=False,
            claimed_primary_coverage_count=1,
            unsafe_count_label="excluded_or_unsafe_count",
            unsafe_non_pointer_count=0,
            secret_scanner_claimed_complete=True,
            secret_findings_escaped_scan=0,
        )
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["statuses"], [])
