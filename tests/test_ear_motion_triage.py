import math
import unittest

from scripts.build_ear_motion_triage import transition_metrics


def base_face():
    # Synthetic 48-point cloud with a non-degenerate face and two ear groups.
    points = []
    for i in range(48):
        angle = 2.0 * math.pi * i / 48.0
        points.append((100.0 + 40.0 * math.cos(angle), 80.0 + 30.0 * math.sin(angle)))
    # Ensure a stable interocular pair.
    points[4] = (80.0, 75.0)
    points[8] = (120.0, 75.0)
    # Put ears above the face with distinct groups.
    for j, i in enumerate(range(22, 27)):
        points[i] = (75.0 + j * 3.0, 45.0 - abs(2 - j) * 2.0)
    for j, i in enumerate(range(27, 32)):
        points[i] = (113.0 + j * 3.0, 45.0 - abs(2 - j) * 2.0)
    return points


def apply_similarity(points, scale=1.1, angle=0.2, tx=12.0, ty=-7.0):
    c = scale * math.cos(angle)
    s = scale * math.sin(angle)
    return [(c * x - s * y + tx, s * x + c * y + ty) for x, y in points]


class EarMotionTriageTests(unittest.TestCase):
    def test_pure_global_similarity_has_near_zero_residual(self):
        previous = base_face()
        current = apply_similarity(previous)
        m = transition_metrics(previous, current)
        self.assertLess(m["anchor_rms_iod"], 1e-10)
        self.assertLess(m["right_ear_rms_iod"], 1e-10)
        self.assertLess(m["left_ear_rms_iod"], 1e-10)
        self.assertLess(m["max_ear_excess_over_anchor_iod"], 1e-10)

    def test_relative_right_ear_shift_survives_face_alignment(self):
        previous = base_face()
        current = apply_similarity(previous)
        # Add a local ear displacement after the global motion.
        for i in range(22, 27):
            x, y = current[i]
            current[i] = (x + 10.0, y - 4.0)
        m = transition_metrics(previous, current)
        self.assertLess(m["anchor_rms_iod"], 1e-10)
        self.assertGreater(m["right_ear_rms_iod"], 0.1)
        self.assertLess(m["left_ear_rms_iod"], 1e-10)
        self.assertGreater(m["right_ear_excess_over_anchor_iod"], 0.1)

    def test_local_non_ear_jitter_raises_anchor_quality_term(self):
        previous = base_face()
        current = apply_similarity(previous)
        x, y = current[0]
        current[0] = (x + 8.0, y + 8.0)
        m = transition_metrics(previous, current)
        self.assertGreater(m["anchor_rms_iod"], 0.0)


if __name__ == "__main__":
    unittest.main()
