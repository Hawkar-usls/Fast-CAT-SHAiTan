import hashlib
import json
import unittest
from pathlib import Path


PROTOCOL_PATH = Path("experiments/pilot_001/protocol.json")
OLD_PROTOCOL_CANONICAL_SHA256 = "4acf5c298e23e60751469eb62d51ffadd8408aee8c2b488343b60ac8c9902e4d"


class ProtocolV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_schema_and_preoutcome_amendment(self):
        p = self.protocol
        self.assertEqual(p["schema"], "Fast-CAT/PILOT-001/protocol/v1.1")
        self.assertTrue(p["analysis_frozen_before_measurement"])
        self.assertTrue(p["protocol_amended_before_action_onset_measurement"])
        self.assertEqual(
            p["amendment"]["previous_protocol_sha256_canonical_json"],
            OLD_PROTOCOL_CANONICAL_SHA256,
        )
        self.assertFalse(p["amendment"]["biological_outcomes_seen_before_amendment"])
        self.assertFalse(p["amendment"]["action_labels_seen_before_amendment"])

    def test_frozen_biological_design_did_not_move(self):
        p = self.protocol
        self.assertEqual(
            p["sources"],
            ["commons_hugging_2019", "commons_tomcats_conflict_2020"],
        )
        self.assertEqual(p["primary_actions"], ["EAD103", "EAD104"])
        self.assertEqual(p["rapid_mimicry_window_ms"], 1000)
        self.assertEqual(
            p["matching_policy"],
            "earliest_unused_same_action_other_cat_forward_within_window",
        )
        self.assertEqual(
            p["selection_policy"], "all_eligible_events_no_posthoc_dropping"
        )
        self.assertEqual(
            p["negative_outcome_policy"], "no_match_is_valid_and_must_be_preserved"
        )

    def test_decoded_pts_is_only_timing_authority(self):
        p = self.protocol
        self.assertIn("decoded video-frame presentation timestamps", p["timestamp_basis"])
        precision = p["precision_policy"]
        self.assertEqual(precision["header_fps_role"], "diagnostic_only")
        self.assertTrue(precision["global_nominal_frame_interval_bound_forbidden"])
        self.assertTrue(precision["forbid_sub_frame_claim_without_sub_frame_measurement"])
        self.assertIn("previous_absent_pts_s", precision["onset_bracket"])
        self.assertIn("responder_previous_absent_pts_s", precision["latency_acquisition_lower_bound"])
        self.assertIn("signaller_previous_absent_pts_s", precision["latency_acquisition_upper_bound"])

    def test_manual_action_admission_is_blinded_and_fail_closed(self):
        p = self.protocol
        manual = p["manual_catfacs_frame_review_admission"]
        self.assertTrue(manual["reviewer_independent_of_model_rankings_before_label_freeze"])
        self.assertTrue(manual["reviewer_or_protocol_must_justify_catfacs_action_coding_competence"])
        self.assertTrue(manual["all_reviewed_labels_frozen_and_sha256_bound_before_model_comparison"])
        self.assertTrue(manual["onset_requires_immediately_previous_absent_then_first_present"])
        self.assertTrue(manual["uncertain_or_not_visible_cannot_bridge_onset"])
        self.assertIn("UNCERTAIN", manual["allowed_states_before_onset_derivation"])
        self.assertIn("NOT_VISIBLE", manual["allowed_states_before_onset_derivation"])

    def test_landmark_and_claim_gates_do_not_promote_candidate_geometry(self):
        p = self.protocol
        landmark = p["landmark_detector_admission"]
        self.assertTrue(landmark["finite_48_point_geometry_is_not_accuracy_proof"])
        self.assertTrue(landmark["fixed_spatial_roi_identity_is_candidate_only"])
        self.assertTrue(landmark["body_detection_confidence_may_not_substitute_for_landmark_confidence"])
        requirements = p["claim_gate"]["INDEPENDENT_FRAME_LEVEL_ESTIMATE"]
        self.assertIn("decoded_frame_pts_ledger_verified", requirements)
        self.assertIn("two_cat_identity_established_independently", requirements)
        self.assertIn("previous_absent_plus_first_present_pts_brackets_verified", requirements)
        self.assertIn("independent_verifier_pass", requirements)

    def test_no_stale_nominal_fps_precision_language(self):
        text = PROTOCOL_PATH.read_text(encoding="utf-8")
        forbidden = [
            "delta_t +/- one nominal frame",
            "Δt ± one nominal frame",
            "1000 / fps",
            "1000/header_fps",
        ]
        lowered = text.lower()
        for phrase in forbidden:
            self.assertNotIn(phrase.lower(), lowered)


if __name__ == "__main__":
    unittest.main()
