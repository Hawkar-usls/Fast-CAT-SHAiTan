import copy
import unittest

from fastcat.numerical_reproducibility import compare_triage_reports


def protocol():
    return {
        "frozen_validation_requirements": {
            "same_transition_count_required": 2,
            "top_k_ranking_set": 2,
            "minimum_top_k_set_overlap_per_candidate_cat": 2,
            "floating_max_absolute_difference_limits": {
                "anchor_rms_iod": 0.00002,
                "interocular_distance_px": 0.0005,
                "left_ear_excess_over_anchor_iod": 0.00005,
                "right_ear_excess_over_anchor_iod": 0.00005,
                "max_ear_excess_over_anchor_iod": 0.00005,
                "left_ear_rms_iod": 0.00005,
                "right_ear_rms_iod": 0.00005,
            },
        },
        "claim_ceiling": "fixture",
    }


def report():
    rows = []
    for i in range(2):
        rows.append(
            {
                "candidate_cat_id": "cat_C_brown_left",
                "from_frame_index": i,
                "to_frame_index": i + 1,
                "from_pts_s": i * 0.033,
                "to_pts_s": (i + 1) * 0.033,
                "anchor_rms_iod": 0.1 + i * 0.01,
                "interocular_distance_px": 20.0 + i,
                "left_ear_excess_over_anchor_iod": 0.2 + i * 0.01,
                "right_ear_excess_over_anchor_iod": 0.3 + i * 0.01,
                "max_ear_excess_over_anchor_iod": 0.3 + i * 0.01,
                "left_ear_rms_iod": 0.4 + i * 0.01,
                "right_ear_rms_iod": 0.5 + i * 0.01,
            }
        )
    return {
        "source_id": "commons_tomcats_conflict_2020",
        "transition_count": 2,
        "transitions": rows,
        "rankings": {"cat_C_brown_left": [rows[1], rows[0]]},
    }


class NumericalReproducibilityTests(unittest.TestCase):
    def test_small_float_jitter_passes(self):
        a = report()
        b = copy.deepcopy(a)
        b["transitions"][0]["left_ear_rms_iod"] += 0.00001
        b["transitions"][1]["interocular_distance_px"] += 0.0002
        r = compare_triage_reports(baseline=a, candidate=b, protocol=protocol())
        self.assertEqual(r["status"], "VALIDATED_WITHIN_FROZEN_NUMERICAL_TOLERANCE")
        self.assertTrue(r["transition_key_set_exact_match"])

    def test_large_float_drift_fails(self):
        a = report()
        b = copy.deepcopy(a)
        b["transitions"][0]["left_ear_rms_iod"] += 0.001
        r = compare_triage_reports(baseline=a, candidate=b, protocol=protocol())
        self.assertEqual(r["status"], "NUMERICAL_REPRODUCIBILITY_OUTSIDE_FROZEN_TOLERANCE")
        self.assertTrue(any(x.startswith("FLOAT_TOLERANCE_EXCEEDED:left_ear_rms_iod") for x in r["failures"]))

    def test_transition_key_change_fails(self):
        a = report()
        b = copy.deepcopy(a)
        b["transitions"][0]["to_frame_index"] = 99
        r = compare_triage_reports(baseline=a, candidate=b, protocol=protocol())
        self.assertIn("TRANSITION_KEY_SET_MISMATCH", r["failures"])

    def test_top_k_set_change_fails(self):
        a = report()
        b = copy.deepcopy(a)
        extra = copy.deepcopy(b["transitions"][0])
        extra["from_frame_index"] = 10
        extra["to_frame_index"] = 11
        b["rankings"]["cat_C_brown_left"] = [b["transitions"][0], extra]
        r = compare_triage_reports(baseline=a, candidate=b, protocol=protocol())
        self.assertTrue(any(x.startswith("TOP_K_SET_OVERLAP_BELOW_REQUIRED") for x in r["failures"]))

    def test_source_mismatch_fails(self):
        a = report()
        b = copy.deepcopy(a)
        b["source_id"] = "wrong"
        r = compare_triage_reports(baseline=a, candidate=b, protocol=protocol())
        self.assertIn("SOURCE_ID_MISMATCH", r["failures"])


if __name__ == "__main__":
    unittest.main()
