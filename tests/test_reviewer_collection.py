import copy
import unittest

from fastcat.review_consensus import canonical_sha256
from fastcat.reviewer_collection import build_reviewer_collection_receipt
from tests.test_review_consensus import make_bundle, policy


def collection_policy():
    return {
        "schema": "Fast-CAT/PILOT-001/reviewer-collection-protocol/v1.0",
        "required_reviewers": 2,
        "submission_protocol_schema": "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.1",
        "submission_protocol_canonical_sha256": canonical_sha256(submission_protocol()),
        "consensus_policy_schema": "Fast-CAT/PILOT-001/multi-reviewer-consensus-protocol/v1.0",
    }


def submission_protocol():
    return {
        "schema": "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.1",
        "source_id": "commons_hugging_2019",
        "expected_blinded_package": {
            "frame_manifest_file_sha256": "f" * 64,
            "workflow_artifact_digest": "sha256:" + "e" * 64,
            "blank_review_form_sha256": "b" * 64,
        },
    }


def consensus_policy():
    value = policy(required=2)
    value["schema"] = "Fast-CAT/PILOT-001/multi-reviewer-consensus-protocol/v1.0"
    return value


def admissible_bundle(reviewer_id):
    bundle = make_bundle(reviewer_id)
    form_sha = bundle["attestation"]["completed_review_form_sha256"]
    bundle["analysis"]["completed_review_form_sha256"] = form_sha
    bundle["verifier"]["review_form_sha256"] = form_sha
    return bundle


def receipt(bundles):
    return build_reviewer_collection_receipt(
        bundles=bundles,
        collection_policy=collection_policy(),
        submission_protocol=submission_protocol(),
        consensus_policy=consensus_policy(),
    )


class ReviewerCollectionTests(unittest.TestCase):
    def test_zero_bundles_is_waiting_not_failure(self):
        report = receipt([])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["collection_state"], "WAITING_FOR_FIRST_REVIEWER")
        self.assertFalse(report["consensus_admission_ready"])
        self.assertEqual(report["admissible_bundle_count"], 0)
        self.assertFalse(report["human_independence_proven_by_software"])
        self.assertTrue(report["submission_protocol_identity_matches_frozen_policy"])

    def test_same_schema_modified_submission_protocol_fails_closed(self):
        frozen = submission_protocol()
        policy_value = collection_policy()
        modified = copy.deepcopy(frozen)
        modified["expected_blinded_package"]["frame_manifest_file_sha256"] = "0" * 64
        report = build_reviewer_collection_receipt(
            bundles=[],
            collection_policy=policy_value,
            submission_protocol=modified,
            consensus_policy=consensus_policy(),
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["collection_state"], "INVALID_COLLECTION")
        self.assertIn("SUBMISSION_PROTOCOL_CANONICAL_SHA256_MISMATCH", report["failures"])
        self.assertFalse(report["submission_protocol_identity_matches_frozen_policy"])

    def test_unpinned_submission_protocol_identity_fails_closed(self):
        policy_value = collection_policy()
        del policy_value["submission_protocol_canonical_sha256"]
        report = build_reviewer_collection_receipt(
            bundles=[],
            collection_policy=policy_value,
            submission_protocol=submission_protocol(),
            consensus_policy=consensus_policy(),
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("SUBMISSION_PROTOCOL_CANONICAL_SHA256_NOT_PINNED", report["failures"])

    def test_one_valid_bundle_waits_for_second_reviewer(self):
        report = receipt([admissible_bundle("reviewer-A")])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["collection_state"], "WAITING_FOR_SECOND_REVIEWER")
        self.assertEqual(report["admissible_bundle_count"], 1)
        self.assertFalse(report["consensus_admission_ready"])

    def test_two_valid_distinct_bundles_are_ready(self):
        report = receipt(
            [admissible_bundle("reviewer-A"), admissible_bundle("reviewer-B")]
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["collection_state"], "READY_FOR_CONSENSUS")
        self.assertTrue(report["consensus_admission_ready"])
        self.assertEqual(report["consensus_core_preflight_status"], "PASS")
        self.assertFalse(report["independent_frame_level_estimate_established"])

    def test_malformed_normalized_row_fails_closed_without_exception(self):
        bundle = admissible_bundle("reviewer-A")
        bundle["analysis"]["normalized_review_rows"] = [1]
        report = receipt([bundle])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["collection_state"], "INVALID_COLLECTION")
        self.assertIn(
            "REVIEW_0:NORMALIZED_REVIEW_ROW_0_NOT_OBJECT",
            report["failures"],
        )

    def test_duplicate_reviewer_id_fails_closed(self):
        first = admissible_bundle("same-reviewer")
        second = admissible_bundle("same-reviewer")
        second["attestation"]["review_completed_utc"] = "2026-08-14T00:01:00Z"
        second["analysis"]["reviewer_attestation_sha256"] = canonical_sha256(
            second["attestation"]
        )
        report = receipt([first, second])
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["collection_state"], "INVALID_COLLECTION")
        self.assertIn("REVIEWER_IDS_NOT_DISTINCT", report["failures"])

    def test_false_independence_attestation_fails_even_if_analysis_hash_is_rebound(self):
        first = admissible_bundle("reviewer-A")
        second = admissible_bundle("reviewer-B")
        second["attestation"][
            "independent_of_fastcat_model_evidence_before_label_freeze"
        ] = False
        second["analysis"]["reviewer_attestation_sha256"] = canonical_sha256(
            second["attestation"]
        )
        report = receipt([first, second])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_1:ATTESTATION_INDEPENDENCE_NOT_CONFIRMED",
            report["failures"],
        )

    def test_model_ranking_exposure_fails_closed(self):
        bundle = admissible_bundle("reviewer-A")
        bundle["attestation"]["saw_landmark_or_motion_rankings_before_label_freeze"] = True
        bundle["analysis"]["reviewer_attestation_sha256"] = canonical_sha256(
            bundle["attestation"]
        )
        report = receipt([bundle])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_0:ATTESTATION_MODEL_RANKING_EXPOSURE_NOT_FALSE",
            report["failures"],
        )

    def test_verifier_must_bind_exact_completed_review_form(self):
        bundle = admissible_bundle("reviewer-A")
        bundle["verifier"]["review_form_sha256"] = "0" * 64
        report = receipt([bundle])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_0:VERIFIER_REVIEW_FORM_SHA256_MISMATCH",
            report["failures"],
        )

    def test_same_completed_form_hash_is_allowed_for_distinct_reviewers(self):
        first = admissible_bundle("reviewer-A")
        second = admissible_bundle("reviewer-B")
        shared = first["analysis"]["completed_review_form_sha256"]
        second["attestation"]["completed_review_form_sha256"] = shared
        second["analysis"]["completed_review_form_sha256"] = shared
        second["verifier"]["review_form_sha256"] = shared
        second["analysis"]["reviewer_attestation_sha256"] = canonical_sha256(
            second["attestation"]
        )
        report = receipt([first, second])
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["collection_state"], "READY_FOR_CONSENSUS")
        self.assertEqual(report["completed_review_form_hash_collision_count"], 1)
        self.assertFalse(report["completed_review_forms_must_be_distinct"])

    def test_tampered_package_digest_fails_closed(self):
        bundle = admissible_bundle("reviewer-A")
        bundle["attestation"]["blinded_package_artifact_digest"] = "sha256:" + "0" * 64
        bundle["analysis"]["reviewer_attestation_sha256"] = canonical_sha256(
            bundle["attestation"]
        )
        report = receipt([bundle])
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_0:ATTESTATION_PACKAGE_DIGEST_MISMATCH",
            report["failures"],
        )


if __name__ == "__main__":
    unittest.main()
