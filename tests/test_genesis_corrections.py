import unittest

from fastcat.genesis_corrections import (
    delta_quantization_interval_ms,
    required_historywise_pmax,
    sequential_any_false_positive_bound,
)


class GenesisCorrectionTests(unittest.TestCase):
    def test_120fps_delta_radius(self):
        h = 1000.0 / 120.0
        interval = delta_quantization_interval_ms(150.0, h)
        self.assertAlmostEqual(interval["acquisition_lower_ms"], 141.66666666666666)
        self.assertAlmostEqual(interval["acquisition_upper_ms"], 158.33333333333334)

    def test_30fps_delta_radius(self):
        h = 1000.0 / 30.0
        interval = delta_quantization_interval_ms(150.0, h)
        self.assertAlmostEqual(interval["acquisition_lower_ms"], 116.66666666666666)
        self.assertAlmostEqual(interval["acquisition_upper_ms"], 183.33333333333334)

    def test_required_pmax_roundtrip(self):
        pmax = required_historywise_pmax(familywise_alpha=0.05, trials=1000)
        bound = sequential_any_false_positive_bound(per_trial_pmax=pmax, trials=1000)
        self.assertAlmostEqual(bound, 0.05, places=12)

    def test_candidate_multiplicity_increases_bound(self):
        one = sequential_any_false_positive_bound(per_trial_pmax=1e-4, trials=100, candidates_per_trial=1)
        two = sequential_any_false_positive_bound(per_trial_pmax=1e-4, trials=100, candidates_per_trial=2)
        self.assertGreater(two, one)

    def test_zero_trials_zero_bound(self):
        self.assertEqual(sequential_any_false_positive_bound(per_trial_pmax=0.5, trials=0), 0.0)


if __name__ == "__main__":
    unittest.main()
