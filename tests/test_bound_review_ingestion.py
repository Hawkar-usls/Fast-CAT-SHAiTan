import unittest

from fastcat.bound_review_ingestion import build_bound_submission_report
from fastcat.review_ingestion import REVIEW_HEADERS


RAW_SHA = "1ac95b351424d63d944969e19949a925e502fbb380153aa404f99390c9845e2e"
PTS_SHA = "98532adfb0c29815d780116b557802d2b45a81ae47a0cb6a8e569973684e31ee"
FRAME_MANIFEST_SHA = "0271018446726ccabd3be78e29c426e03d772e2bc01bb40ceb32ff246ae51c67"
CONTENT_IDENTITY_SHA = "87877d69e5fcfd44433b93106740ef641c320a8037b06aefe281fff9179378fd"
PACKAGE_MANIFEST_SHA = "85bf6a190377a304b607bd611cd7d9476e521b98682286f4d9cfb47d5878e3e4"
FILES_PAYLOAD_SHA = "2a550d1d32fff07757c6838f224a63fa5d87a00017b4dcc110154bd75fd99513"
BLANK_FORM_SHA = "b464040c69491ac1ce7e1083f2745a85361fe3884cce1b37d6c9c7bae946622d"
FORM_SHA = "f" * 64


def protocol():
    return {
        "schema": "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.2",
        "source_id": "commons_hugging_2019",
        "expected_blinded_package": {
            "raw_media_sha256": RAW_SHA,
            "decoded_frame_count": 2,
            "frame_pts_sha256": PTS_SHA,
            "subjects": ["subject_A", "subject_B"],
            "expected_annotation_rows": 4,
            "frame_manifest_file_sha256": FRAME_MANIFEST_SHA,
            "content_identity_file_sha256": CONTENT_IDENTITY_SHA,
            "package_manifest_file_sha256": PACKAGE_MANIFEST_SHA,
            "files_payload_sha256": FILES_PAYLOAD_SHA,
            "blank_review_form_sha256": BLANK_FORM_SHA,
        },
        "allowed_review_states": ["ABSENT", "PRESENT", "UNCERTAIN", "NOT_VISIBLE"],
        "allowed_identity_states": ["yes", "no", "uncertain"],
        "matching": {"point_estimate_window_ms": 1000},
    }


def manifest():
    return {
        "schema": "Fast-CAT/PILOT-001/blinded-review-frame-manifest/v1.0",
        "source_id": "commons_hugging_2019",
        "raw_media_sha256": RAW_SHA,
        "frame_count": 2,
        "frame_pts_sha256": PTS_SHA,
        "contains_model_derived_fields": False,
        "frames": [
            {"frame_index": 0, "pts_s": "0.000000"},
            {"frame_index": 1, "pts_s": "0.060000"},
        ],
    }


def rows():
    result = []
    for frame_index, pts_s in ((0, "0.000000"), (1, "0.060000")):
        for subject in ("subject_A", "subject_B"):
            result.append(
                {
                    "source_id": "commons_hugging_2019",
                    "frame_index": str(frame_index),
                    "pts_s": pts_s,
                    "subject_id": subject,
                    "identity_confirmed": "yes",
                    "left_ear_EAD103": "ABSENT",
                    "right_ear_EAD103": "ABSENT",
                    "left_ear_EAD104": "ABSENT",
                    "right_ear_EAD104": "ABSENT",
                    "review_notes": "",
                }
            )
    return result


def attestation():
    return {
        "schema": "Fast-CAT/PILOT-001/reviewer-attestation/v1.1",
        "reviewer_id": "fixture-reviewer",
        "independent_of_fastcat_model_evidence_before_label_freeze": True,
        "saw_landmark_or_motion_rankings_before_label_freeze": False,
        "labels_frozen_before_model_reveal": True,
        "catfacs_competence_basis": "fixture only",
        "completed_review_form_sha256": FORM_SHA,
        "blinded_package_content_identity_file_sha256": CONTENT_IDENTITY_SHA,
        "blinded_package_manifest_sha256": PACKAGE_MANIFEST_SHA,
        "blinded_package_files_payload_sha256": FILES_PAYLOAD_SHA,
        "blank_review_form_sha256": BLANK_FORM_SHA,
        "blinded_package_transport_sha256": "1" * 64,
        "review_completed_utc": "2026-08-09T00:00:00Z",
    }


class BoundReviewIngestionTests(unittest.TestCase):
    def test_exact_binding_allows_lower_level_validation(self):
        report = build_bound_submission_report(
            protocol=protocol(),
            frame_manifest=manifest(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            headers=REVIEW_HEADERS,
            review_rows=rows(),
            attestation=attestation(),
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["schema"], "Fast-CAT/PILOT-001/independent-review-ingestion/v1.2")
        self.assertTrue(report["exact_frozen_package_binding_established"])
        self.assertTrue(report["transport_independent_package_content_binding_established"])
        self.assertEqual(report["derived_onsets"], [])

    def test_wrong_manifest_hash_blocks_before_event_derivation(self):
        review_rows = rows()
        review_rows[2]["left_ear_EAD103"] = "PRESENT"
        report = build_bound_submission_report(
            protocol=protocol(),
            frame_manifest=manifest(),
            frame_manifest_file_sha256="0" * 64,
            headers=REVIEW_HEADERS,
            review_rows=review_rows,
            attestation=attestation(),
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["exact_frozen_package_binding_established"])
        self.assertEqual(report["derived_onsets"], [])
        self.assertEqual(report["matches"], [])
        self.assertIn("FRAME_MANIFEST_FILE_SHA256_NOT_FROZEN_PACKAGE", report["failures"])

    def test_wrong_content_identity_blocks_before_event_derivation(self):
        bad = attestation()
        bad["blinded_package_content_identity_file_sha256"] = "0" * 64
        report = build_bound_submission_report(
            protocol=protocol(),
            frame_manifest=manifest(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            headers=REVIEW_HEADERS,
            review_rows=rows(),
            attestation=bad,
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["derived_onsets"], [])
        self.assertIn("ATTESTATION_CONTENT_IDENTITY_FILE_SHA256_MISMATCH", report["failures"])

    def test_different_outer_transport_is_allowed(self):
        first = attestation()
        second = attestation()
        first["blinded_package_transport_sha256"] = "1" * 64
        second["blinded_package_transport_sha256"] = "2" * 64
        for value in (first, second):
            report = build_bound_submission_report(
                protocol=protocol(),
                frame_manifest=manifest(),
                frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
                headers=REVIEW_HEADERS,
                review_rows=rows(),
                attestation=value,
                completed_review_form_sha256=FORM_SHA,
            )
            self.assertEqual(report["status"], "PASS")
            self.assertTrue(report["transport_independent_package_content_binding_established"])


if __name__ == "__main__":
    unittest.main()
