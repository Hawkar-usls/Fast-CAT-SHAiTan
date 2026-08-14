import unittest

from fastcat.control_full_rate import classify_full_rate_control


class FullRateControlGateTests(unittest.TestCase):
    def test_complete_coverage_admits_adjacent_triage(self):
        report = classify_full_rate_control(
            expected_frames=1218,
            processed_frames=1218,
            distinct_two_candidate_frames=1218,
            duplicate_face_risk_frames=0,
            incomplete_roi_frames=0,
        )
        self.assertEqual(report["status"], "PASS_CANDIDATE_ONLY")
        self.assertEqual(
            report["scientific_outcome"],
            "FULL_RATE_TWO_CANDIDATE_COVERAGE_COMPLETE",
        )
        self.assertTrue(report["adjacent_full_rate_ear_triage_admitted"])
        self.assertEqual(report["coverage_fraction"], 1.0)

    def test_detector_miss_is_valid_negative_not_pipeline_failure(self):
        report = classify_full_rate_control(
            expected_frames=1218,
            processed_frames=1218,
            distinct_two_candidate_frames=1217,
            duplicate_face_risk_frames=0,
            incomplete_roi_frames=1,
        )
        self.assertEqual(
            report["status"],
            "VALID_NEGATIVE_INCOMPLETE_CANDIDATE_COVERAGE",
        )
        self.assertFalse(report["adjacent_full_rate_ear_triage_admitted"])
        self.assertEqual(report["failures"], [])

    def test_duplicate_face_risk_blocks_triage_without_imputation(self):
        report = classify_full_rate_control(
            expected_frames=1218,
            processed_frames=1218,
            distinct_two_candidate_frames=1210,
            duplicate_face_risk_frames=8,
            incomplete_roi_frames=0,
        )
        self.assertEqual(
            report["scientific_outcome"],
            "FULL_RATE_TWO_CANDIDATE_COVERAGE_INCOMPLETE",
        )
        self.assertFalse(report["adjacent_full_rate_ear_triage_admitted"])

    def test_processed_count_mismatch_is_integrity_failure(self):
        report = classify_full_rate_control(
            expected_frames=1218,
            processed_frames=1217,
            distinct_two_candidate_frames=1217,
            duplicate_face_risk_frames=0,
            incomplete_roi_frames=0,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any(x.startswith("PROCESSED_FRAME_COUNT_MISMATCH") for x in report["failures"])
        )
        self.assertFalse(report["adjacent_full_rate_ear_triage_admitted"])

    def test_partition_mismatch_is_integrity_failure(self):
        report = classify_full_rate_control(
            expected_frames=1218,
            processed_frames=1218,
            distinct_two_candidate_frames=1218,
            duplicate_face_risk_frames=1,
            incomplete_roi_frames=0,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(
            any(
                x.startswith("FRAME_CLASSIFICATION_PARTITION_MISMATCH")
                for x in report["failures"]
            )
        )

    def test_upstream_integrity_failure_forces_fail_closed(self):
        report = classify_full_rate_control(
            expected_frames=1218,
            processed_frames=1218,
            distinct_two_candidate_frames=1218,
            duplicate_face_risk_frames=0,
            incomplete_roi_frames=0,
            integrity_failures=["FRAME_FILENAME_MISMATCH:7"],
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("FRAME_FILENAME_MISMATCH:7", report["failures"])
        self.assertFalse(report["adjacent_full_rate_ear_triage_admitted"])


if __name__ == "__main__":
    unittest.main()
