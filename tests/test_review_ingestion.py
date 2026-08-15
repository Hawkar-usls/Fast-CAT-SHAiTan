import unittest

from fastcat.review_ingestion import (
    REVIEW_HEADERS,
    acquisition_interval_ms,
    build_submission_report,
    derive_onsets,
    deterministic_pairing,
)
from fastcat.review_submission_binding import validate_frozen_package_binding


RAW_SHA = "1ac95b351424d63d944969e19949a925e502fbb380153aa404f99390c9845e2e"
PTS_SHA = "98532adfb0c29815d780116b557802d2b45a81ae47a0cb6a8e569973684e31ee"
FORM_SHA = "a" * 64
FRAME_MANIFEST_FILE_SHA = "d7c6bea943272a4499074370cfbdceb1fc397eeb773513865a70e6bb62a63295"
ARTIFACT_DIGEST = "sha256:06dfdf946e61983ea598d2fc9cdd16ff6543904fec3eafa996322b1e10ecd40d"
BLANK_FORM_SHA = "4296c2503311eb2766d223db91c8d197acf0e685b2cc004aefef8ec8548883b0"


def protocol():
    return {
        "source_id": "commons_hugging_2019",
        "expected_blinded_package": {
            "raw_media_sha256": RAW_SHA,
            "decoded_frame_count": 50,
            "frame_pts_sha256": PTS_SHA,
            "subjects": ["subject_A", "subject_B"],
            "expected_annotation_rows": 100,
            "frame_manifest_file_sha256": FRAME_MANIFEST_FILE_SHA,
            "workflow_artifact_digest": ARTIFACT_DIGEST,
            "blank_review_form_sha256": BLANK_FORM_SHA,
        },
        "allowed_review_states": ["ABSENT", "PRESENT", "UNCERTAIN", "NOT_VISIBLE"],
        "allowed_identity_states": ["yes", "no", "uncertain"],
        "matching": {"point_estimate_window_ms": 1000},
    }


def frame_manifest():
    return {
        "schema": "Fast-CAT/PILOT-001/blinded-review-frame-manifest/v1.0",
        "source_id": "commons_hugging_2019",
        "raw_media_sha256": RAW_SHA,
        "frame_count": 50,
        "frame_pts_sha256": PTS_SHA,
        "contains_model_derived_fields": False,
        "claim_ceiling": "fixture",
        "frames": [
            {
                "frame_index": i,
                "pts_s": f"{i * 0.06:.6f}",
                "filename": f"f{i:06d}.png",
                "png_sha256": f"{i:064x}"[-64:],
                "rgb24_sha256": f"{i + 100:064x}"[-64:],
            }
            for i in range(50)
        ],
    }


def rows():
    out = []
    manifest = frame_manifest()
    for frame in manifest["frames"]:
        for subject in ("subject_A", "subject_B"):
            out.append(
                {
                    "source_id": "commons_hugging_2019",
                    "frame_index": str(frame["frame_index"]),
                    "pts_s": frame["pts_s"],
                    "subject_id": subject,
                    "identity_confirmed": "yes",
                    "left_ear_EAD103": "ABSENT",
                    "right_ear_EAD103": "ABSENT",
                    "left_ear_EAD104": "ABSENT",
                    "right_ear_EAD104": "ABSENT",
                    "review_notes": "",
                }
            )
    return out


def attestation(form_sha=FORM_SHA):
    return {
        "schema": "Fast-CAT/PILOT-001/reviewer-attestation/v1.0",
        "reviewer_id": "independent-reviewer-fixture",
        "independent_of_fastcat_model_evidence_before_label_freeze": True,
        "saw_landmark_or_motion_rankings_before_label_freeze": False,
        "labels_frozen_before_model_reveal": True,
        "catfacs_competence_basis": "fixture competence declaration",
        "completed_review_form_sha256": form_sha,
        "blinded_package_artifact_digest": ARTIFACT_DIGEST,
        "blank_review_form_sha256": BLANK_FORM_SHA,
        "review_completed_utc": "2026-08-09T00:00:00Z",
    }


class ReviewIngestionTests(unittest.TestCase):
    def test_valid_zero_onset_review_is_successful_negative_outcome(self):
        report = build_submission_report(
            protocol=protocol(),
            frame_manifest=frame_manifest(),
            headers=REVIEW_HEADERS,
            review_rows=rows(),
            attestation=attestation(),
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["scientific_outcome"], "VALID_REVIEW_ZERO_MATCHES")
        self.assertEqual(report["derived_onsets"], [])
        self.assertEqual(report["matches"], [])
        self.assertFalse(report["independent_frame_level_estimate_established"])

    def test_absent_to_present_derives_onsets_and_matches_cross_laterality(self):
        review_rows = rows()

        def row(frame, subject):
            return review_rows[frame * 2 + (0 if subject == "subject_A" else 1)]

        row(1, "subject_A")["left_ear_EAD104"] = "PRESENT"
        row(3, "subject_B")["right_ear_EAD104"] = "PRESENT"

        report = build_submission_report(
            protocol=protocol(),
            frame_manifest=frame_manifest(),
            headers=REVIEW_HEADERS,
            review_rows=review_rows,
            attestation=attestation(),
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["derived_onsets"]), 2)
        self.assertEqual(report["summary"]["n_matches"], 1)
        match = report["matches"][0]
        self.assertEqual(match["action"], "EAD104")
        self.assertEqual(match["signaller_laterality"], "left")
        self.assertEqual(match["responder_laterality"], "right")
        self.assertAlmostEqual(match["latency_ms"], 120.0)
        self.assertAlmostEqual(match["acquisition_interval_ms"]["lower_ms"], 60.0)
        self.assertAlmostEqual(match["acquisition_interval_ms"]["upper_ms"], 180.0)
        self.assertFalse(report["independent_frame_level_estimate_established"])

    def test_uncertain_previous_frame_blocks_onset(self):
        review_rows = rows()
        review_rows[0]["left_ear_EAD103"] = "UNCERTAIN"
        review_rows[2]["left_ear_EAD103"] = "PRESENT"
        events = derive_onsets(
            [{**r, "frame_index": int(r["frame_index"])} for r in review_rows],
            protocol(),
        )
        self.assertFalse(any(x["subject_id"] == "subject_A" and x["action"] == "EAD103" and x["onset_frame_index"] == 1 for x in events))

    def test_identity_uncertain_blocks_onset(self):
        review_rows = rows()
        review_rows[0]["identity_confirmed"] = "uncertain"
        review_rows[2]["left_ear_EAD103"] = "PRESENT"
        events = derive_onsets(
            [{**r, "frame_index": int(r["frame_index"])} for r in review_rows],
            protocol(),
        )
        self.assertEqual(events, [])

    def test_attestation_hash_mismatch_fails_closed(self):
        report = build_submission_report(
            protocol=protocol(),
            frame_manifest=frame_manifest(),
            headers=REVIEW_HEADERS,
            review_rows=rows(),
            attestation=attestation("b" * 64),
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("ATTESTATION_REVIEW_FORM_SHA256_MISMATCH", report["failures"])
        self.assertEqual(report["derived_onsets"], [])

    def test_extra_model_column_is_rejected(self):
        report = build_submission_report(
            protocol=protocol(),
            frame_manifest=frame_manifest(),
            headers=REVIEW_HEADERS + ["model_score"],
            review_rows=rows(),
            attestation=attestation(),
            completed_review_form_sha256=FORM_SHA,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("REVIEW_HEADERS_MISMATCH_OR_MODEL_FIELDS_PRESENT", report["failures"])

    def test_exact_blinded_package_binding(self):
        content_identity_sha = "c" * 64
        package_manifest_sha = "d" * 64
        files_payload_sha = "e" * 64
        binding_protocol = {
            "schema": "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.2",
            "expected_blinded_package": {
                "frame_manifest_file_sha256": FRAME_MANIFEST_FILE_SHA,
                "content_identity_file_sha256": content_identity_sha,
                "package_manifest_file_sha256": package_manifest_sha,
                "files_payload_sha256": files_payload_sha,
                "blank_review_form_sha256": BLANK_FORM_SHA,
            },
        }
        binding_attestation = {
            "schema": "Fast-CAT/PILOT-001/reviewer-attestation/v1.1",
            "blinded_package_content_identity_file_sha256": content_identity_sha,
            "blinded_package_manifest_sha256": package_manifest_sha,
            "blinded_package_files_payload_sha256": files_payload_sha,
            "blank_review_form_sha256": BLANK_FORM_SHA,
            "blinded_package_transport_sha256": "1" * 64,
        }
        failures = validate_frozen_package_binding(
            protocol=binding_protocol,
            frame_manifest_file_sha256=FRAME_MANIFEST_FILE_SHA,
            attestation=binding_attestation,
        )
        self.assertEqual(failures, [])
        bad = dict(binding_attestation)
        bad["blinded_package_content_identity_file_sha256"] = "0" * 64
        failures = validate_frozen_package_binding(
            protocol=binding_protocol,
            frame_manifest_file_sha256=FRAME_MANIFEST_FILE_SHA,
            attestation=bad,
        )
        self.assertIn("ATTESTATION_CONTENT_IDENTITY_FILE_SHA256_MISMATCH", failures)

    def test_acquisition_interval_uses_both_local_brackets(self):
        interval = acquisition_interval_ms(
            {"previous_absent_pts_s": 0.000, "onset_pts_s": 0.060},
            {"previous_absent_pts_s": 0.120, "onset_pts_s": 0.180},
        )
        self.assertAlmostEqual(interval["point_ms"], 120.0)
        self.assertAlmostEqual(interval["lower_ms"], 60.0)
        self.assertAlmostEqual(interval["upper_ms"], 180.0)
        self.assertAlmostEqual(interval["interval_width_ms"], 120.0)

    def test_pairing_preserves_no_match(self):
        events = [
            {
                "event_id": "a",
                "source_id": "commons_hugging_2019",
                "subject_id": "subject_A",
                "action": "EAD103",
                "laterality": "left",
                "previous_absent_pts_s": 0.0,
                "onset_pts_s": 0.06,
            }
        ]
        matches, unmatched = deterministic_pairing(events, protocol())
        self.assertEqual(matches, [])
        self.assertEqual(unmatched, ["a"])


if __name__ == "__main__":
    unittest.main()
