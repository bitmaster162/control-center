from __future__ import annotations

import copy
import unittest

from control_center.scripts.human_gate_atomic_consume_p0 import (
    HumanGateAtomicConsumeError,
    NO_EFFECTS,
    REQUIRED_SAFETY,
    build_human_gate_atomic_consume_verification,
    build_human_gate_consume_commit_candidate,
    build_human_gate_consume_compare,
    build_human_gate_consume_prepare,
    build_human_gate_state_snapshot,
    sha256_obj,
)

ROOT = "1" * 64
+PRIOR_CRED = "2" * 64
+PRIOR_NONCE = "3" * 64
+ASSERTION = "4" * 64
+CHALLENGE = "5" * 64
+NONCE = "6" * 64
+
+
+def registry_candidate(kind: str, digest_seed: str, *, challenge_id: str = CHALLENGE, nonce_sha: str = NONCE):
+    body = {
+        "schema": kind,
+        "registry_id": f"{kind}:r7",
+        "authority_root_sha256": ROOT,
+        "used_challenge_ids": (challenge_id,) if "nonce" in kind else (),
+        "used_nonce_sha256s": (nonce_sha,) if "nonce" in kind else (),
+        "entries": (),
+        "entry_count": 0,
+        "write_allowed": False,
+        "apply_allowed": False,
+        "execution_authority": "NONE",
+        "safety": dict(REQUIRED_SAFETY),
+        "effects": dict(NO_EFFECTS),
+        "seed": digest_seed,
+    }
+    body["registry_sha256"] = sha256_obj(body)
+    return body
+
+
+def approval_fixture():
+    next_nonce = registry_candidate("control_center.shadow_human_nonce_epoch_registry_snapshot.v1", "n")
+    next_cred = registry_candidate("control_center.shadow_human_credential_registry_snapshot.v1", "c")
+    body = {
+        "schema": "control_center.shadow_asymmetric_human_approval_verification.v2",
+        "challenge_id": CHALLENGE,
+        "case_id": "case-r7",
+        "case_sha256": "7" * 64,
+        "packet_sha256": "8" * 64,
+        "external_assertion_sha256": ASSERTION,
+        "external_assertion_digest_consumed": True,
+        "external_asymmetric_verifier_evidence": "EXPECTED_DIGEST_BOUND",
+        "trust_upgrade": "SELF_HASH_TO_INDEPENDENT_ASSERTION_DIGEST",
+        "prior_credential_registry_sha256": PRIOR_CRED,
+        "next_credential_registry_candidate": next_cred,
+        "next_credential_registry_candidate_sha256": next_cred["registry_sha256"],
+        "prior_nonce_registry_sha256": PRIOR_NONCE,
+        "next_nonce_registry_candidate": next_nonce,
+        "next_nonce_registry_candidate_sha256": next_nonce["registry_sha256"],
+        "registry_write_performed": False,
+        "approval_scope": "HUMAN_REVEAL_ONLY",
+        "status": "ASYMMETRIC_HUMAN_APPROVAL_VERIFIED_SHADOW_ONLY",
+        "execution_authority": "NONE",
+        "can_execute": False,
+        "apply_allowed": False,
+        "safety": dict(REQUIRED_SAFETY),
+        "effects": dict(NO_EFFECTS),
+    }
+    body["asymmetric_approval_verification_sha256"] = sha256_obj(body)
+    return body
+
+
+def state_fixture(*, generation=10, consumed_challenges=(), consumed_nonces=()):
+    return build_human_gate_state_snapshot(
+        state_id="human-gate:r7",
+        authority_root_sha256=ROOT,
+        generation=generation,
+        credential_registry_sha256=PRIOR_CRED,
+        nonce_registry_sha256=PRIOR_NONCE,
+        consumed_challenge_ids=consumed_challenges,
+        consumed_nonce_sha256s=consumed_nonces,
+        previous_state_sha256="9" * 64,
+    )
+
+
+class HumanGateAtomicConsumeTests(unittest.TestCase):
+    def build_chain(self):
+        approval = approval_fixture()
+        state = state_fixture()
+        prepare = build_human_gate_consume_prepare(
+            approval,
+            state,
+            expected_approval_sha256=approval["asymmetric_approval_verification_sha256"],
+            expected_prior_state_sha256=state["state_sha256"],
+        )
+        compare = build_human_gate_consume_compare(
+            prepare,
+            state,
+            expected_current_state_sha256=state["state_sha256"],
+        )
+        commit = build_human_gate_consume_commit_candidate(prepare, compare, state)
+        verification = build_human_gate_atomic_consume_verification(
+            prepare,
+            compare,
+            commit,
+            expected_commit_candidate_sha256=commit["commit_candidate_sha256"],
+        )
+        return approval, state, prepare, compare, commit, verification
+
+    def test_happy_path_is_protocol_verified_but_no_write(self):
+        _, _, _, _, commit, verification = self.build_chain()
+        self.assertEqual(verification["atomicity_status"], "PROTOCOL_VERIFIED_NO_DURABLE_COMMIT")
+        self.assertEqual(verification["toctou_guard_model"], "COMPARE_AND_SWAP_PRECONDITION")
+        self.assertFalse(verification["commit_performed"])
+        self.assertFalse(verification["human_gate_write_performed"])
+        self.assertEqual(verification["execution_authority"], "NONE")
+        self.assertEqual(commit["cas_generation_to"], commit["cas_generation_from"] + 1)
+
+    def test_prepare_rejects_already_consumed_challenge(self):
+        approval = approval_fixture()
+        state = state_fixture(consumed_challenges=(CHALLENGE,))
+        with self.assertRaisesRegex(HumanGateAtomicConsumeError, "prepare_challenge_already_consumed"):
+            build_human_gate_consume_prepare(
+                approval,
+                state,
+                expected_approval_sha256=approval["asymmetric_approval_verification_sha256"],
+                expected_prior_state_sha256=state["state_sha256"],
+            )
+
+    def test_compare_rejects_state_change_after_prepare(self):
+        approval = approval_fixture()
+        state = state_fixture()
+        prepare = build_human_gate_consume_prepare(
+            approval,
+            state,
+            expected_approval_sha256=approval["asymmetric_approval_verification_sha256"],
+            expected_prior_state_sha256=state["state_sha256"],
+        )
+        changed = build_human_gate_state_snapshot(
+            state_id=state["state_id"],
+            authority_root_sha256=ROOT,
+            generation=11,
+            credential_registry_sha256=PRIOR_CRED,
+            nonce_registry_sha256=PRIOR_NONCE,
+            previous_state_sha256=state["state_sha256"],
+        )
+        with self.assertRaisesRegex(HumanGateAtomicConsumeError, "compare_and_swap_state_changed"):
+            build_human_gate_consume_compare(
+                prepare,
+                changed,
+                expected_current_state_sha256=changed["state_sha256"],
+            )
+
+    def test_two_prepares_from_same_state_cannot_both_compare_after_first_hypothetical_commit(self):
+        approval = approval_fixture()
+        state = state_fixture()
+        p1 = build_human_gate_consume_prepare(
+            approval, state,
+            expected_approval_sha256=approval["asymmetric_approval_verification_sha256"],
+            expected_prior_state_sha256=state["state_sha256"],
+        )
+        p2 = copy.deepcopy(p1)
+        c1 = build_human_gate_consume_compare(p1, state, expected_current_state_sha256=state["state_sha256"])
+        commit1 = build_human_gate_consume_commit_candidate(p1, c1, state)
+        hypothetical_new_state = commit1["next_state_candidate"]
+        with self.assertRaisesRegex(HumanGateAtomicConsumeError, "compare_and_swap_state_changed"):
+            build_human_gate_consume_compare(
+                p2,
+                hypothetical_new_state,
+                expected_current_state_sha256=hypothetical_new_state["state_sha256"],
+            )
+
+    def test_commit_rejects_current_state_changed_after_compare(self):
+        approval = approval_fixture()
+        state = state_fixture()
+        prepare = build_human_gate_consume_prepare(
+            approval, state,
+            expected_approval_sha256=approval["asymmetric_approval_verification_sha256"],
+            expected_prior_state_sha256=state["state_sha256"],
+        )
+        compare = build_human_gate_consume_compare(prepare, state, expected_current_state_sha256=state["state_sha256"])
+        changed = dict(state)
+        changed["generation"] = 11
+        changed["state_sha256"] = sha256_obj({k: v for k, v in changed.items() if k != "state_sha256"})
+        with self.assertRaisesRegex(HumanGateAtomicConsumeError, "commit_compare_binding_mismatch|commit_state_changed_after_compare"):
+            build_human_gate_consume_commit_candidate(prepare, compare, changed)
+
+    def test_external_commit_digest_is_required(self):
+        _, _, prepare, compare, commit, _ = self.build_chain()
+        with self.assertRaisesRegex(HumanGateAtomicConsumeError, "atomic_commit_external_digest_mismatch"):
+            build_human_gate_atomic_consume_verification(
+                prepare, compare, commit, expected_commit_candidate_sha256="0" * 64
+            )
+
+    def test_durable_commit_overclaim_is_rejected_even_if_rehashed(self):
+        _, _, prepare, compare, commit, _ = self.build_chain()
+        forged = copy.deepcopy(commit)
+        forged["commit_performed"] = True
+        forged["commit_candidate_sha256"] = sha256_obj({k: v for k, v in forged.items() if k != "commit_candidate_sha256"})
+        with self.assertRaisesRegex(HumanGateAtomicConsumeError, "atomic_durable_commit_overclaim"):
+            build_human_gate_atomic_consume_verification(
+                prepare,
+                compare,
+                forged,
+                expected_commit_candidate_sha256=forged["commit_candidate_sha256"],
+            )
+
+
+if __name__ == "__main__":
+    unittest.main()
