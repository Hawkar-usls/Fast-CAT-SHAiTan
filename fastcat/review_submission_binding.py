from __future__ import annotations

from typing import Any


def validate_frozen_package_binding(
    *,
    protocol: dict[str, Any],
    frame_manifest_file_sha256: str,
    attestation: dict[str, Any],
) -> list[str]:
    """Validate that a review submission names the exact frozen blinded package.

    This is separate from biological label validation. It prevents a completed
    CSV from being silently paired with a different frame manifest or an
    unrecorded blank-form lineage.
    """
    failures: list[str] = []
    expected = protocol.get("expected_blinded_package", {})

    if frame_manifest_file_sha256 != str(
        expected.get("frame_manifest_file_sha256", "")
    ):
        failures.append("FRAME_MANIFEST_FILE_SHA256_NOT_FROZEN_PACKAGE")

    if str(attestation.get("blinded_package_artifact_digest", "")) != str(
        expected.get("workflow_artifact_digest", "")
    ):
        failures.append("ATTESTATION_BLINDED_PACKAGE_ARTIFACT_DIGEST_MISMATCH")

    if str(attestation.get("blank_review_form_sha256", "")) != str(
        expected.get("blank_review_form_sha256", "")
    ):
        failures.append("ATTESTATION_BLANK_REVIEW_FORM_SHA256_MISMATCH")

    return failures
