import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from creature_forge.studio.app import create_app, resolve_static


class StaticServingTests(unittest.TestCase):
    """SPA catch-all must never serve files outside the dist directory (harmless fixtures only)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.dist = root / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_text("INDEX-OK")
        (self.dist / "favicon.txt").write_text("FAV-OK")
        (root / "outside.txt").write_text("OUTSIDE-SECRET-FIXTURE")
        (root / "dist-sibling").mkdir()
        (root / "dist-sibling" / "x.txt").write_text("SIBLING-FIXTURE")  # shares the "dist" string prefix
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_static_allows_inside_and_rejects_escapes(self):
        self.assertEqual(resolve_static(self.dist, "favicon.txt"), (self.dist / "favicon.txt").resolve())
        for bad in ("", "../outside.txt", "..\outside.txt", "assets/../../outside.txt",
                    "../dist-sibling/x.txt", str(self.root / "outside.txt"), "nope.txt"):
            self.assertIsNone(resolve_static(self.dist, bad), bad)

    def test_http_never_leaks_outside_files(self):
        c = TestClient(create_app(dist_dir=self.dist))
        self.assertEqual(c.get("/favicon.txt").text, "FAV-OK")
        for url in ("/../outside.txt", "/%2e%2e/outside.txt", "/..%2foutside.txt", "/%2e%2e%2foutside.txt",
                    "/assets/../../outside.txt", "/..%5coutside.txt", "/%2e%2e/dist-sibling/x.txt",
                    "/" + (self.root / "outside.txt").as_posix()):
            r = c.get(url)
            self.assertNotIn("FIXTURE", r.text, url)
            self.assertNotIn("OUTSIDE-SECRET", r.text, url)

    def test_unknown_route_falls_back_to_index(self):
        c = TestClient(create_app(dist_dir=self.dist))
        self.assertEqual(c.get("/some/client/route").text, "INDEX-OK")


if __name__ == "__main__":
    unittest.main()
