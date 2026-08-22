import unittest

from fastcat.review_submission_binding import validate_frozen_package_binding


FRAME_MANIFEST_SHA = "0271018446726ccabd3be78e29c426e03d772e2bc01bb40ceb32ff246ae51c67"
CONTENT_IDENTITY_SHA = "87877d69e5fcfd44433b93106740ef641c320a8037b06aefe281fff9179378fd"
PACKAGE_MANIFEST_SHA = "85bf6a190377a304b607bd611cd7d9476e521b98682286f4d9cfb47d5878e3e4"
FILES_PAYLOAD_SHA = "2a550d1d32fff07757c6838f224a63fa5d87a00017b4dcc110154bd75fd99513"
BLANK_FORM_SHA = "b464040c69491ac1ce7e1083f2745a85361fe3884cce1b37d6c9c7bae946622d"


def protocol():
    return {
        "schema": "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.2",
        "expected_blinded_package": {
            "frame_manifest_file_sha256": FRAME_MANIFEST_SHA,
            "content_identity_file_sha256": CONTENT_IDENTITY_SHA,
            "package_manifest_file_sha256": PACKAGE_MANIFEST_SHA,
            "files_payload_sha256": FILES_PAYLOAD_SHA,
            "blank_review_form_sha256": BLANK_FORM_SHA,
        },
    }


def attestation():
    return {
        "schema": "Fast-CAT/PILOT-001/reviewer-attestation/v1.1",
        "blinded_package_content_identity_file_sha256": CONTENT_IDENTITY_SHA,
        "blinded_package_manifest_sha256": PACKAGE_MANIFEST_SHA,
        "blinded_package_files_payload_sha256": FILES_PAYLOAD_SHA,
        "blank_review_form_sha256": BLANK_FORM_SHA,
        "blinded_package_transport_sha256": "f" * 64,
    }


class FrozenPackageBindingTests(unittest.TestCase):
    def test_exact_canonical_package_identity_passes(self):
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

    def test_wrong_content_identity_fails_closed(self):
        bad = attestation()
        bad["blinded_package_content_identity_file_sha256"] = "0" * 64
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation=bad,
        )
        self.assertIn("ATTESTATION_CONTENT_IDENTITY_FILE_SHA256_MISMATCH", failures)

    def test_wrong_package_manifest_fails_closed(self):
        bad = attestation()
        bad["blinded_package_manifest_sha256"] = "0" * 64
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation=bad,
        )
        self.assertIn("ATTESTATION_PACKAGE_MANIFEST_SHA256_MISMATCH", failures)

    def test_wrong_files_payload_fails_closed(self):
        bad = attestation()
        bad["blinded_package_files_payload_sha256"] = "0" * 64
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation=bad,
        )
        self.assertIn("ATTESTATION_FILES_PAYLOAD_SHA256_MISMATCH", failures)

    def test_wrong_blank_form_lineage_fails_closed(self):
        bad = attestation()
        bad["blank_review_form_sha256"] = "0" * 64
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation=bad,
        )
        self.assertIn("ATTESTATION_BLANK_REVIEW_FORM_SHA256_MISMATCH", failures)

    def test_outer_transport_digest_is_not_admission_authority(self):
        first = attestation()
        second = attestation()
        first["blinded_package_transport_sha256"] = "1" * 64
        second["blinded_package_transport_sha256"] = "2" * 64
        self.assertEqual(
            validate_frozen_package_binding(
                protocol=protocol(),
                frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
                attestation=first,
            ),
            [],
        )
        self.assertEqual(
            validate_frozen_package_binding(
                protocol=protocol(),
                frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
                attestation=second,
            ),
            [],
        )

    def test_missing_lineage_fields_fail_closed(self):
        failures = validate_frozen_package_binding(
            protocol=protocol(),
            frame_manifest_file_sha256=FRAME_MANIFEST_SHA,
            attestation={},
        )
        self.assertIn("ATTESTATION_SCHEMA_MISMATCH", failures)
        self.assertIn("ATTESTATION_CONTENT_IDENTITY_FILE_SHA256_MISMATCH", failures)
        self.assertIn("ATTESTATION_PACKAGE_MANIFEST_SHA256_MISMATCH", failures)
        self.assertIn("ATTESTATION_FILES_PAYLOAD_SHA256_MISMATCH", failures)
        self.assertIn("ATTESTATION_BLANK_REVIEW_FORM_SHA256_MISMATCH", failures)


if __name__ == "__main__":
    unittest.main()
