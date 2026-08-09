import unittest

from fastcat.review_submission_binding import validate_frozen_package_binding


FRAME_MANIFEST_SHA = "0271018446726ccabd3be78e29c426e03d772e2bc01bb40ceb32ff246ae51c67"
ARTIFACT_DIGEST = "sha256:ee86e46ab1979d5836a96788106e3e2f809268f6cbe7ccf1c6b328478e6f3f2f"
BLANK_FORM_SHA = "b464040c69491ac1ce7e1083f2745a85361fe3884cce1b37d6c9c7bae946622d"


def protocol():
    return {
        "expected_blinded_package": {
            "frame_manifest_file_sha256": FRAME_MANIFEST_SHA,
            "workflow_artifact_digest": ARTIFACT_DIGEST,
            "blank_review_form_sha256": BLANK_FORM_SHA,
        }
    }


def attestation():
    return {
        "blinded_package_artifact_digest": ARTIFACT_DIGEST,
        "blank_review_form_sha256": BLANK_FORM_SHA,
    }


class FrozenPackageBindingTests(unittest.TestCase):
    def test_exact_frozen_package_identity_passes(self):
        self.assertEqual(
            validate_frozen_package_binding(
                protocol=protocol(),
                frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
                attestation=attestation(),
            ),
            [],
        )

    def test_wrong_frame_manifest_fails_closed(self):
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256="0" * 64,
            attestation=attestation(),
        )
        self.assertIn("FRAME_MANIFEST_FILE_SHA256_NOT_FROZEN_PACKAGE", failures)

    def test_wrong_artifact_digest_fails_closed(self):
        bad = attestation()
        bad["blinded_package_artifact_digest"] = "sha256:" + "0" * 64
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation=bad,
        )
        self.assertIn(
            "ATTESTATION_BLINDED_PACKAGE_ARTIFACT_DIGEST_MISMATCH",
            failures,
        )

    def test_wrong_blank_form_lineage_fails_closed(self):
        bad = attestation()
        bad["blank_review_form_sha256"] = "0" * 64
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation=bad,
        )
        self.assertIn("ATTESTATION_BLANK_REVIEW_FORM_SHA256_MISMATCH", failures)

    def test_missing_lineage_fields_fail_closed(self):
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation={},
        )
        self.assertIn(
            "ATTESTATION_BLINDED_PACKAGE_ARTIFACT_DIGEST_MISMATCH",
            failures,
        )
        self.assertIn("ATTESTATION_BLANK_REVIEW_FORM_SHA256_MISMATCH", failures)


if __name__ == "__main__":
    unittest.main()
