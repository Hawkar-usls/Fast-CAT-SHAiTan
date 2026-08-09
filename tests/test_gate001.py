import unittest

from fastcat.gate001 import deterministic_matches, summarize_matches, validate_landmark_rows


def points48():
    return [[float(i), float(i + 1)] for i in range(48)]


class Gate001Tests(unittest.TestCase):
    def test_requires_48_landmarks(self):
        rows = [{"video_id": "v", "cat_id": "A", "pts_s": 0.0, "confidence": 0.9, "landmarks": points48()[:-1]}]
        failures, _ = validate_landmark_rows(rows)
        self.assertTrue(any("LANDMARK_COUNT_NOT_48" in x for x in failures))

    def test_requires_two_cats(self):
        rows = [
            {"video_id": "v", "cat_id": "A", "pts_s": 0.0, "confidence": 0.9, "landmarks": points48()},
            {"video_id": "v", "cat_id": "A", "pts_s": 0.1, "confidence": 0.9, "landmarks": points48()},
        ]
        failures, _ = validate_landmark_rows(rows)
        self.assertIn("TWO_CAT_IDENTITY_NOT_ESTABLISHED:v", failures)

    def test_pts_must_increase(self):
        rows = [
            {"video_id": "v", "cat_id": "A", "pts_s": 0.1, "confidence": 0.9, "landmarks": points48()},
            {"video_id": "v", "cat_id": "A", "pts_s": 0.1, "confidence": 0.9, "landmarks": points48()},
            {"video_id": "v", "cat_id": "B", "pts_s": 0.0, "confidence": 0.9, "landmarks": points48()},
        ]
        failures, _ = validate_landmark_rows(rows)
        self.assertTrue(any(x.startswith("PTS_NOT_STRICTLY_INCREASING") for x in failures))

    def test_deterministic_ear_match(self):
        events = [
            {"event_id": "a1", "video_id": "v", "cat_id": "A", "action": "EAD104", "onset_pts_s": 1.000},
            {"event_id": "b1", "video_id": "v", "cat_id": "B", "action": "EAD104", "onset_pts_s": 1.150},
            {"event_id": "b2", "video_id": "v", "cat_id": "B", "action": "EAD104", "onset_pts_s": 1.300},
        ]
        matches = deterministic_matches(events, window_ms=1000)
        self.assertEqual(len(matches), 1)
        self.assertAlmostEqual(matches[0]["latency_ms"], 150.0)

    def test_no_match_is_valid_summary(self):
        summary = summarize_matches([])
        self.assertEqual(summary["n_matches"], 0)
        self.assertIsNone(summary["mean_ms"])

    def test_outside_window_not_matched(self):
        events = [
            {"event_id": "a1", "video_id": "v", "cat_id": "A", "action": "EAD104", "onset_pts_s": 1.000},
            {"event_id": "b1", "video_id": "v", "cat_id": "B", "action": "EAD104", "onset_pts_s": 2.001},
        ]
        self.assertEqual(deterministic_matches(events, window_ms=1000), [])


if __name__ == "__main__":
    unittest.main()
