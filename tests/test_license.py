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
        self.assertModelWeightsDisclaimer(text)

    def assertModelWeightsDisclaimer(self, text: str) -> None:
        """The external-services section must name the hosted models and state that no model weights are included or
        redistributed. Checked on the meaning, not on one exact sentence: case and line wrapping are normalised, because the
        generator's wording is edited by hand (e.g. "No model weights are included or redistributed." vs "(no model weights
        are included or redistributed)") and an exact-substring check broke CI on such an edit."""
        m = re.search(r"^## External services and models.*?(?=^## |\Z)", text, flags=re.S | re.M)
        self.assertIsNotNone(m, "THIRD_PARTY_NOTICES.md must have an 'External services and models' section")
        section = re.sub(r"\s+", " ", m.group(0))
        self.assertRegex(section, r"(?i)\bnemotron\b", "the hosted model must be named")
        self.assertRegex(section, r"(?i)\bnebius\b", "the service providing the model must be named")
        self.assertRegex(section, r"(?i)\bno model weights (?:are|is) (?:included|redistributed|bundled)\b",
                         "the notices must state that no model weights are included or redistributed")

    def test_model_weights_disclaimer_check_accepts_both_wordings_and_rejects_its_absence(self):
        head = "## External services and models (not redistributed)\n\n- **NVIDIA Nemotron** via the Nebius Token Factory API "
        for ok in ("(no model weights are included or redistributed):", "used only through the API. No model weights are included or\n"
                   "  redistributed."):
            self.assertModelWeightsDisclaimer(head + ok + "\n\n## Python packages\n")
        for bad in ("model weights are included.", "", "(weights are not discussed)"):
            with self.assertRaises(AssertionError):
                self.assertModelWeightsDisclaimer(head + bad + "\n\n## Python packages\n")
        with self.assertRaises(AssertionError):     # the disclaimer outside the section does not count
            self.assertModelWeightsDisclaimer("## Python packages\nNo model weights are included.\n")

    def test_no_secrets_or_credentials_are_named_in_the_license_files(self):
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            self.assertNotRegex((ROOT / name).read_text(encoding="utf-8"), r"(?i)api[_-]?key\s*[:=]\s*\S{12,}")


if __name__ == "__main__":
    unittest.main()
