import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LicenseFilesTests(unittest.TestCase):
    def test_apache_2_0_text_and_notice_are_present(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0, January 2004", text)
        self.assertIn("TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION", text)
        notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
        self.assertIn("Creature Forge", notice)
        self.assertIn("THIRD_PARTY_NOTICES.md", notice)

    def test_package_metadata_declares_the_license(self):
        meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(meta["project"]["license"], "Apache-2.0")
        self.assertIn("LICENSE", meta["project"]["license-files"])
        self.assertGreaterEqual(int(re.search(r"setuptools>=(\d+)", meta["build-system"]["requires"][0]).group(1)), 77)

    def test_third_party_inventory_has_no_unresolved_licenses(self):
        text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        rows = [ln for ln in text.splitlines() if ln.startswith("| ") and not ln.startswith("| package") and not ln.startswith("|---")]
        self.assertGreater(len(rows), 50)
        self.assertEqual([r for r in rows if r.rstrip().endswith("| UNKNOWN |")], [])
        for needed in ("mujoco", "numpy", "react", "three"):
            self.assertTrue(any(r.lower().startswith(f"| {needed} ") for r in rows), needed)
        self.assertIn("No model weights are included", text)

    def test_no_secrets_or_credentials_are_named_in_the_license_files(self):
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            self.assertNotRegex((ROOT / name).read_text(encoding="utf-8"), r"(?i)api[_-]?key\s*[:=]\s*\S{12,}")


if __name__ == "__main__":
    unittest.main()
