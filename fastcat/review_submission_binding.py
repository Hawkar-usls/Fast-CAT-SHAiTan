from __future__ import annotations

from typing import Any


ATTESTATION_SCHEMA = "Fast-CAT/PILOT-001/reviewer-attestation/v1.1"
SUBMISSION_PROTOCOL_SCHEMA = (
    "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.2"
)


def validate_frozen_package_binding(
    *,
    protocol: dict[str, Any],
    frame_manifest_file_sha256: str,
    attestation: dict[str, Any],
) -> list[str]:
    """Bind a submission to exact canonical blinded-package content.

    The original GitHub Actions artifact remains useful origin provenance, but
    its outer ZIP digest is no longer the admission authority. A different ZIP
    transport is admissible only when the reviewer binds the submission to the
    exact frozen content identity, package manifest, files payload and blank
    review form.
    """
    failures: list[str] = []
    if protocol.get("schema") != SUBMISSION_PROTOCOL_SCHEMA:
        failures.append("SUBMISSION_PROTOCOL_SCHEMA_MISMATCH")
        return failures
    expected = protocol.get("expected_blinded_package")
    if not isinstance(expected, dict):
        return failures + ["EXPECTED_BLINDED_PACKAGE_MISSING"]

    if frame_manifest_file_sha256 != str(
        expected.get("frame_manifest_file_sha256", "")
    ):
        failures.append("FRAME_MANIFEST_FILE_SHA256_NOT_FROZEN_PACKAGE")
    if attestation.get("schema") != ATTESTATION_SCHEMA:
        failures.append("ATTESTATION_SCHEMA_MISMATCH")
    if str(
        attestation.get("blinded_package_content_identity_file_sha256", "")
    ) != str(expected.get("content_identity_file_sha256", "")):
        failures.append("ATTESTATION_CONTENT_IDENTITY_FILE_SHA256_MISMATCH")
    if str(attestation.get("blinded_package_manifest_sha256", "")) != str(
        expected.get("package_manifest_file_sha256", "")
    ):
        failures.append("ATTESTATION_PACKAGE_MANIFEST_SHA256_MISMATCH")
    if str(attestation.get("blinded_package_files_payload_sha256", "")) != str(
        expected.get("files_payload_sha256", "")
    ):
        failures.append("ATTESTATION_FILES_PAYLOAD_SHA256_MISMATCH")
    if str(attestation.get("blank_review_form_sha256", "")) != str(
        expected.get("blank_review_form_sha256", "")
    ):
        failures.append("ATTESTATION_BLANK_REVIEW_FORM_SHA256_MISMATCH")
    return failures
