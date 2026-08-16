import unittest

from fastcat.causal_world_bridge import analyze_worlds


class CausalWorldBridgeTests(unittest.TestCase):
    def packet(self):
        return {
            "schema": "fastcat.causal_world_bridge.v1",
            "case_id": "fixture",
            "worlds": [
                {
                    "world_id": "root_a",
                    "status": "SOURCE_ROOT",
                    "events": ["COMMON", "A", "A2"],
                },
                {
                    "world_id": "root_b",
                    "status": "SOURCE_ROOT",
                    "events": ["COMMON", "B", "B2"],
                },
                {
                    "world_id": "hypothesis",
                    "status": "HYPOTHESIS_ONLY",
                    "events": ["COMMON", "H"],
                },
            ],
        }

    def test_first_divergence_is_after_common_prefix(self):
        result = analyze_worlds(self.packet())
        self.assertEqual(result["common_prefix"], ["COMMON"])
        self.assertEqual(result["first_divergence_index"], 1)
        self.assertEqual(result["status"], "DISAGREEMENT_PRESERVED")
        self.assertIsNone(result["winner"])

    def test_hypothesis_is_segregated_from_source_worlds(self):
        result = analyze_worlds(self.packet())
        self.assertEqual(result["source_worlds"], ["root_a", "root_b"])
        self.assertEqual(result["hypothesis_worlds"], ["hypothesis"])
        self.assertEqual(result["historical_claim"], "NOT_MADE")

    def test_identical_worlds_converge(self):
        packet = self.packet()
        packet["worlds"] = [
            {"world_id": "a", "status": "SOURCE_ROOT", "events": ["X", "Y"]},
            {"world_id": "b", "status": "SOURCE_ROOT", "events": ["X", "Y"]},
        ]
        result = analyze_worlds(packet)
        self.assertEqual(result["status"], "CONVERGED")
        self.assertIsNone(result["first_divergence_index"])


if __name__ == "__main__":
    unittest.main()
