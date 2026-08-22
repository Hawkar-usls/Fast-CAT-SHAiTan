import hashlib
import json
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from fastcat.blinded_package_identity import (
    canonical_bytes,
    sha256_bytes,
    verify_package_zip,
)


def make_fixture(root: Path):
    files = {
        "frame_manifest.json": b'{"fixture":true}\n',
        "review_form.csv": b"a,b\n,\n",
        "REVIEW_INSTRUCTIONS.md": b"# review\n",
        "frames/f000000.png": b"PNG-fixture",
    }
    entries = [
        {"path": path, "byte_length": len(data), "sha256": sha256_bytes(data)}
        for path, data in files.items()
    ]
    manifest = {
        "schema": "Fast-CAT/PILOT-001/blinded-review-package-manifest/v1.0",
        "source_id": "fixture",
        "protocol_sha256": "1" * 64,
        "frame_ledger_sha256": "2" * 64,
        "files": entries,
        "expected_annotation_rows": 2,
        "labels_initially_blank": True,
        "model_evidence_excluded": True,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "fixture",
    }
    manifest["files_payload_sha256"] = sha256_bytes(canonical_bytes(entries))
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    identity = {
        "schema": "Fast-CAT/PILOT-001/blinded-review-content-identity/v1.0",
        "source_id": "fixture",
        "canonical_package": {
            "package_manifest_schema": manifest["schema"],
            "package_manifest_file_sha256": sha256_bytes(manifest_bytes),
            "files_payload_sha256": manifest["files_payload_sha256"],
            "payload_file_count": len(entries),
            "frame_manifest_file_sha256": sha256_bytes(files["frame_manifest.json"]),
            "blank_review_form_sha256": sha256_bytes(files["review_form.csv"]),
            "instructions_file_sha256": sha256_bytes(files["REVIEW_INSTRUCTIONS.md"]),
            "protocol_sha256": "1" * 64,
            "frame_ledger_sha256": "2" * 64,
        },
        "original_transport": {},
    }
    archive = root / "original.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("package/package_manifest.json", manifest_bytes)
        for path, data in files.items():
            z.writestr("package/" + path, data)
    identity["original_transport"]["artifact_zip_sha256"] = hashlib.sha256(
        archive.read_bytes()
    ).hexdigest()
    return identity, archive, files, manifest_bytes


class BlindedPackageIdentityTests(unittest.TestCase):
    def test_exact_and_repacked_transport_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity, archive, _, _ = make_fixture(root)
            original = verify_package_zip(zip_path=archive, identity=identity)
            self.assertEqual(original["status"], "EXACT_CANONICAL_CONTENT_MATCH")
            self.assertTrue(original["original_transport_match"])
            repacked = root / "repacked.zip"
            with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(
                repacked, "w", compression=zipfile.ZIP_DEFLATED
            ) as zout:
                for name in zin.namelist():
                    zout.writestr(name, zin.read(name))
            replay = verify_package_zip(zip_path=repacked, identity=identity)
            self.assertEqual(replay["status"], "EXACT_CANONICAL_CONTENT_MATCH")
            self.assertFalse(replay["original_transport_match"])

    def test_mutation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity, archive, _, _ = make_fixture(root)
            bad = root / "bad.zip"
            with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(bad, "w") as zout:
                for name in zin.namelist():
                    payload = b"changed" if name == "package/review_form.csv" else zin.read(name)
                    zout.writestr(name, payload)
            report = verify_package_zip(zip_path=bad, identity=identity)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(any("review_form.csv" in x for x in report["failures"]))

    def test_extra_model_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity, archive, _, _ = make_fixture(root)
            bad = root / "extra.zip"
            with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(bad, "w") as zout:
                for name in zin.namelist():
                    zout.writestr(name, zin.read(name))
                zout.writestr("package/model_rankings.json", b"{}")
            report = verify_package_zip(zip_path=bad, identity=identity)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(
                any(x.startswith("EXTRA_ARCHIVE_MEMBERS:") for x in report["failures"])
            )

    def test_top_level_model_file_outside_package_prefix_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity, archive, _, _ = make_fixture(root)
            bad = root / "top-level-extra.zip"
            with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(bad, "w") as zout:
                for name in zin.namelist():
                    zout.writestr(name, zin.read(name))
                zout.writestr("model_rankings.json", b"{}")
            report = verify_package_zip(zip_path=bad, identity=identity)
            self.assertEqual(report["status"], "FAIL")
            self.assertTrue(
                any(
                    x.startswith("EXTRA_ARCHIVE_MEMBERS:")
                    and "model_rankings.json" in x
                    for x in report["failures"]
                ),
                report,
            )

    def test_duplicate_zip_member_name_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity, archive, _, _ = make_fixture(root)
            bad = root / "duplicate.zip"
            with zipfile.ZipFile(archive) as zin, zipfile.ZipFile(bad, "w") as zout:
                for name in zin.namelist():
                    zout.writestr(name, zin.read(name))
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    zout.writestr("package/review_form.csv", zin.read("package/review_form.csv"))
            report = verify_package_zip(zip_path=bad, identity=identity)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("DUPLICATE_ZIP_MEMBER_NAMES", report["failures"])

    def test_unsafe_manifest_path_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            identity, _, files, manifest_bytes = make_fixture(root)
            manifest = json.loads(manifest_bytes)
            manifest["files"][0]["path"] = "../frame_manifest.json"
            manifest["files_payload_sha256"] = sha256_bytes(
                canonical_bytes(manifest["files"])
            )
            new_manifest = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
            identity["canonical_package"]["package_manifest_file_sha256"] = sha256_bytes(
                new_manifest
            )
            identity["canonical_package"]["files_payload_sha256"] = manifest[
                "files_payload_sha256"
            ]
            bad = root / "unsafe.zip"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("package/package_manifest.json", new_manifest)
                for path, data in files.items():
                    z.writestr("package/" + path, data)
            report = verify_package_zip(zip_path=bad, identity=identity)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("FILE_0:PATH_INVALID", report["failures"])


if __name__ == "__main__":
    unittest.main()
