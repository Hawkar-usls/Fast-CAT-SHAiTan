import unittest

from fastcat.gate001 import (
    canonical_sha256,
    event_pair_latency_interval_ms,
    validate_event_rows,
    validate_frame_ledger,
)


class DecodedPtsGateTests(unittest.TestCase):
    def test_frame_ledger_rejects_header_rate_as_substitute_for_pts(self):
        pts = [
            {"frame_index": 0, "pts_s": "0.000000", "key_frame": 1, "pict_type": "I"},
            {"frame_index": 1, "pts_s": "0.058000", "key_frame": 0, "pict_type": "P"},
            {"frame_index": 2, "pts_s": "0.117000", "key_frame": 0, "pict_type": "P"},
        ]
        ledger = {
            "schema": "Fast-CAT/PILOT-001/decoded-frame-ledger/v1.0",
            "source_id": "hug",
            "source_media_sha256": "a" * 64,
            "frame_count": len(pts),
            "frame_pts": pts,
            "frame_pts_sha256": canonical_sha256(pts),
        }
        failures, meta = validate_frame_ledger(
            ledger,
            expected_source_id="hug",
            expected_raw_sha256="a" * 64,
        )
        self.assertEqual(failures, [])
        self.assertAlmostEqual(meta["pts_gap_ms_min"], 58.0)
        self.assertAlmostEqual(meta["pts_gap_ms_max"], 59.0)

    def test_frame_ledger_rejects_non_monotonic_pts(self):
        pts = [
            {"frame_index": 0, "pts_s": "0.000000", "key_frame": 1, "pict_type": "I"},
            {"frame_index": 1, "pts_s": "0.000000", "key_frame": 0, "pict_type": "P"},
        ]
        ledger = {
            "schema": "Fast-CAT/PILOT-001/decoded-frame-ledger/v1.0",
            "source_id": "v",
            "source_media_sha256": "b" * 64,
            "frame_count": 2,
            "frame_pts": pts,
            "frame_pts_sha256": canonical_sha256(pts),
        }
        failures, _ = validate_frame_ledger(
            ledger,
            expected_source_id="v",
            expected_raw_sha256="b" * 64,
        )
        self.assertIn("FRAME_LEDGER_PTS_NOT_STRICT:1", failures)

    def test_first_visible_latency_interval_is_asymmetric_local_pts(self):
        signaller = {
            "onset_pts_s": 1.000,
            "previous_absent_pts_s": 0.941,
        }
        responder = {
            "onset_pts_s": 1.176,
            "previous_absent_pts_s": 1.117,
        }
        interval = event_pair_latency_interval_ms(signaller, responder)
        self.assertAlmostEqual(interval["point_ms"], 176.0)
        self.assertAlmostEqual(interval["lower_ms"], 117.0)
        self.assertAlmostEqual(interval["upper_ms"], 235.0)
        self.assertAlmostEqual(interval["signaller_bracket_ms"], 59.0)
        self.assertAlmostEqual(interval["responder_bracket_ms"], 59.0)
        self.assertAlmostEqual(interval["interval_width_ms"], 118.0)

    def test_event_gate_requires_previous_absent_pts(self):
        events = [
            {
                "event_id": "e1",
                "video_id": "v",
                "cat_id": "A",
                "action": "EAD104",
                "source": "manual_catfacs_frame_review",
                "confidence": 1.0,
                "onset_pts_s": 1.0,
            }
        ]
        failures, _ = validate_event_rows(
            events,
            allowed_actions={"EAD104"},
            allowed_sources={"manual_catfacs_frame_review"},
            min_confidence=0.9,
        )
        self.assertIn("EVENT_0:PREVIOUS_ABSENT_PTS_INVALID", failures)


if __name__ == "__main__":
    unittest.main()
