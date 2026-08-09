import unittest

from fastcat.genesis_corrections import (
    decoded_pts_latency_interval_ms,
    required_historywise_pmax,
    sequential_any_false_positive_bound,
)


class GenesisCorrectionTests(unittest.TestCase):
    def test_decoded_pts_interval_uses_local_brackets(self):
        interval = decoded_pts_latency_interval_ms(
            signaller_previous_absent_pts_s=0.941,
            signaller_onset_pts_s=1.000,
            responder_previous_absent_pts_s=1.117,
            responder_onset_pts_s=1.176,
        )
        self.assertAlmostEqual(interval["point_ms"], 176.0)
        self.assertAlmostEqual(interval["acquisition_lower_ms"], 117.0)
        self.assertAlmostEqual(interval["acquisition_upper_ms"], 235.0)
        self.assertAlmostEqual(interval["signaller_bracket_ms"], 59.0)
        self.assertAlmostEqual(interval["responder_bracket_ms"], 59.0)
        self.assertAlmostEqual(interval["acquisition_interval_width_ms"], 118.0)

    def test_decoded_pts_interval_rejects_bad_bracket(self):
        with self.assertRaises(ValueError):
            decoded_pts_latency_interval_ms(
                signaller_previous_absent_pts_s=1.0,
                signaller_onset_pts_s=1.0,
                responder_previous_absent_pts_s=1.1,
                responder_onset_pts_s=1.2,
            )

    def test_required_pmax_roundtrip(self):
        pmax = required_historywise_pmax(familywise_alpha=0.05, trials=1000)
        bound = sequential_any_false_positive_bound(
            per_trial_pmax=pmax,
            trials=1000,
        )
        self.assertAlmostEqual(bound, 0.05, places=12)

    def test_candidate_multiplicity_increases_bound(self):
        one = sequential_any_false_positive_bound(
            per_trial_pmax=1e-4,
            trials=100,
            candidates_per_trial=1,
        )
        two = sequential_any_false_positive_bound(
            per_trial_pmax=1e-4,
            trials=100,
            candidates_per_trial=2,
        )
        self.assertGreater(two, one)

    def test_zero_trials_zero_bound(self):
        self.assertEqual(
            sequential_any_false_positive_bound(per_trial_pmax=0.5, trials=0),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
