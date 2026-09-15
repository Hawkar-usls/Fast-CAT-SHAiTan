import tempfile
import unittest
import zipfile
from pathlib import Path

from fastcat.blinded_package_identity import verify_package_zip
from tests.test_blinded_package_identity import make_fixture


class BlindedPackageArchiveSurfaceTests(unittest.TestCase):
    def test_top_level_model_evidence_is_rejected(self):
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
                    failure.startswith("EXTRA_ARCHIVE_MEMBERS:")
                    and "model_rankings.json" in failure
                    for failure in report["failures"]
                ),
                report,
            )


if __name__ == "__main__":
    unittest.main()
