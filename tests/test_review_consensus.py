import copy
import unittest

from fastcat.review_consensus import (
    _derive_review_onsets,
    _deterministic_pairing,
    build_consensus_report,
    canonical_sha256,
)


def make_rows():
    rows = []
    for frame in range(5):
        for subject in ("subject_A", "subject_B"):
            rows.append(
                {
                    "source_id": "commons_hugging_2019",
                    "frame_index": frame,
                    "pts_s": f"{frame * 0.06:.6f}",
                    "subject_id": subject,
                    "identity_confirmed": "yes",
                    "left_ear_EAD103": "ABSENT",
                    "right_ear_EAD103": "ABSENT",
                    "left_ear_EAD104": "ABSENT",
                    "right_ear_EAD104": "ABSENT",
                    "review_notes": "",
                }
            )
    return rows


def make_bundle(reviewer_id, rows=None, attestation=None):
    rows = copy.deepcopy(rows if rows is not None else make_rows())
    attestation = copy.deepcopy(
        attestation
        or {
            "schema": "Fast-CAT/PILOT-001/reviewer-attestation/v1.0",
            "reviewer_id": reviewer_id,
            "independent_of_fastcat_model_evidence_before_label_freeze": True,
            "saw_landmark_or_motion_rankings_before_label_freeze": False,
            "labels_frozen_before_model_reveal": True,
            "catfacs_competence_basis": "fixture",
            "completed_review_form_sha256": reviewer_id.rjust(64, "0")[-64:],
            "blinded_package_artifact_digest": "sha256:" + "e" * 64,
            "blank_review_form_sha256": "b" * 64,
            "review_completed_utc": "2026-08-14T00:00:00Z",
        }
    )
    rows_sha = canonical_sha256(rows)
    onsets = _derive_review_onsets(rows)
    matches, _ = _deterministic_pairing(onsets, 1000.0)
    onsets_sha = canonical_sha256(onsets)
    matches_sha = canonical_sha256(matches)
    analysis = {
        "schema": "Fast-CAT/PILOT-001/independent-review-ingestion/v1.1",
        "status": "PASS",
        "source_id": "commons_hugging_2019",
        "frame_manifest_file_sha256": "f" * 64,
        "reviewer_attestation_sha256": canonical_sha256(attestation),
        "normalized_review_rows": rows,
        "normalized_review_rows_sha256": rows_sha,
        "derived_onsets": onsets,
        "derived_onsets_sha256": onsets_sha,
        "matches": matches,
        "matches_sha256": matches_sha,
        "review_submission_integrity_established": True,
        "exact_frozen_package_binding_established": True,
        "independent_frame_level_estimate_established": False,
    }
    verifier = {
        "schema": "Fast-CAT/PILOT-001/independent-review-verifier/v1.0",
        "status": "PASS",
        "frame_manifest_file_sha256": "f" * 64,
        "normalized_review_rows_sha256_recomputed": rows_sha,
        "derived_onsets_sha256_recomputed": onsets_sha,
        "matches_sha256_recomputed": matches_sha,
        "independent_replay_established": True,
        "independent_frame_level_estimate_established": False,
    }
    return {"analysis": analysis, "attestation": attestation, "verifier": verifier}


def policy(required=2):
    return {
        "required_reviewers": required,
        "distinct_reviewer_ids_required": True,
        "distinct_attestation_hashes_required": True,
        "point_estimate_window_ms": 1000,
    }


class ReviewConsensusTests(unittest.TestCase):
    def test_two_identical_independent_reviews_pass_zero_match(self):
        report = build_consensus_report(
            bundles=[make_bundle("r1"), make_bundle("r2")],
            policy=policy(),
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["scientific_outcome"],
            "VALID_UNANIMOUS_CONSENSUS_ZERO_MATCHES",
        )
        self.assertEqual(report["agreement"]["exact_state_agreement_rate"], 1.0)
        self.assertEqual(report["derived_consensus_onsets"], [])
        self.assertFalse(report["independent_frame_level_estimate_established"])

    def test_disagreement_is_preserved_and_blocks_onset(self):
        rows1 = make_rows()
        rows2 = make_rows()
        rows1[2]["left_ear_EAD103"] = "PRESENT"
        rows2[2]["left_ear_EAD103"] = "ABSENT"
        b1 = make_bundle("r1", rows1)
        b2 = make_bundle("r2", rows2)
        report = build_consensus_report(bundles=[b1, b2], policy=policy())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["consensus_rows"][2]["left_ear_EAD103"], "DISAGREEMENT"
        )
        self.assertEqual(report["derived_consensus_onsets"], [])
        self.assertEqual(report["agreement"]["disagreement_state_cell_count"], 1)

    def test_unanimous_cross_subject_onsets_produce_match(self):
        rows1 = make_rows()
        rows2 = make_rows()
        for rows in (rows1, rows2):
            rows[2]["left_ear_EAD104"] = "PRESENT"
            rows[7]["right_ear_EAD104"] = "PRESENT"
        b1 = make_bundle("r1", rows1)
        b2 = make_bundle("r2", rows2)
        report = build_consensus_report(bundles=[b1, b2], policy=policy())
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["derived_consensus_onsets"]), 2)
        self.assertEqual(report["summary"]["n_matches"], 1)
        self.assertAlmostEqual(report["matches"][0]["latency_ms"], 120.0)

    def test_duplicate_reviewer_identity_fails_closed(self):
        b1 = make_bundle("same")
        b2 = make_bundle("same")
        b2["attestation"]["review_completed_utc"] = "2026-08-14T00:01:00Z"
        b2["analysis"]["reviewer_attestation_sha256"] = canonical_sha256(
            b2["attestation"]
        )
        report = build_consensus_report(bundles=[b1, b2], policy=policy())
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("REVIEWER_IDS_NOT_DISTINCT", report["failures"])

    def test_same_attestation_hash_fails_closed(self):
        same_attestation = make_bundle("r1")["attestation"]
        b1 = make_bundle("r1", attestation=same_attestation)
        b2 = make_bundle("r2", attestation=same_attestation)
        report = build_consensus_report(bundles=[b1, b2], policy=policy())
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("ATTESTATION_HASHES_NOT_DISTINCT", report["failures"])

    def test_attestation_tamper_is_detected(self):
        b2 = make_bundle("r2")
        b2["attestation"]["reviewer_id"] = "forged-r3"
        report = build_consensus_report(
            bundles=[make_bundle("r1"), b2], policy=policy()
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_1:ATTESTATION_CANONICAL_SHA256_MISMATCH",
            report["failures"],
        )

    def test_tampered_normalized_rows_hash_fails_closed(self):
        b2 = make_bundle("r2")
        b2["analysis"]["normalized_review_rows"][0]["identity_confirmed"] = "no"
        report = build_consensus_report(
            bundles=[make_bundle("r1"), b2], policy=policy()
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_1:NORMALIZED_ROWS_SHA256_MISMATCH",
            report["failures"],
        )

    def test_verifier_mismatch_fails_closed(self):
        b2 = make_bundle("r2")
        b2["verifier"]["normalized_review_rows_sha256_recomputed"] = "0" * 64
        report = build_consensus_report(
            bundles=[make_bundle("r1"), b2], policy=policy()
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn(
            "REVIEW_1:VERIFIER_NORMALIZED_ROWS_SHA256_MISMATCH",
            report["failures"],
        )

    def test_row_alignment_mismatch_fails_closed(self):
        b2 = make_bundle("r2")
        b2["analysis"]["normalized_review_rows"][0]["pts_s"] = "999.000000"
        new_sha = canonical_sha256(b2["analysis"]["normalized_review_rows"])
        b2["analysis"]["normalized_review_rows_sha256"] = new_sha
        b2["verifier"]["normalized_review_rows_sha256_recomputed"] = new_sha
        report = build_consensus_report(
            bundles=[make_bundle("r1"), b2], policy=policy()
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("REVIEW_1:ROW_KEY_ALIGNMENT_MISMATCH", report["failures"])

    def test_required_reviewer_count_is_enforced(self):
        report = build_consensus_report(
            bundles=[make_bundle("r1")], policy=policy(required=2)
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("REVIEWER_COUNT_BELOW_REQUIRED:1<2", report["failures"])


if __name__ == "__main__":
    unittest.main()
