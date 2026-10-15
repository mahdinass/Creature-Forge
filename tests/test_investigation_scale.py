"""Smoke scale exists only for test servers: it is recorded in each record and refused for live investigations."""
import os
import unittest
from unittest import mock

from creature_forge import investigation as inv


class ScaleTests(unittest.TestCase):
    def test_default_is_full_and_unknown_values_are_rejected(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CF_INVESTIGATION_SCALE", None)
            self.assertEqual(inv.investigation_scale(), "full")
        with mock.patch.dict(os.environ, {"CF_INVESTIGATION_SCALE": "tiny"}):
            with self.assertRaises(ValueError):
                inv.investigation_scale()

    def test_live_mode_is_refused_at_smoke_scale_before_anything_runs(self):
        with mock.patch.dict(os.environ, {"CF_INVESTIGATION_SCALE": "smoke"}):
            with self.assertRaises(inv.LiveRefused) as cm:
                inv.run_investigation(None, "c-00000000", 1, "r-00000000", mode="live", forge_dir="unused")
            self.assertIn("full scale", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
