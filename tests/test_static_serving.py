import os

os.environ.setdefault("CF_ALLOW_TESTSERVER", "1")  # Starlette TestClient sends Host: testserver (see studio/security.py)

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

    def test_unknown_api_route_is_json_404_not_html(self):
        c = TestClient(create_app(dist_dir=self.dist))
        for url in ("/api/nonexistent", "/api/lab/nope/deeper", "/api"):
            r = c.get(url)
            self.assertEqual(r.status_code, 404, url)
            self.assertTrue(r.headers["content-type"].startswith("application/json"), url)
            self.assertIn("detail", r.json())
        r = c.post("/api/nonexistent", json={})
        self.assertTrue(r.headers["content-type"].startswith("application/json"))

    def test_version_endpoint_reports_routes_and_build(self):
        c = TestClient(create_app(dist_dir=self.dist))
        v = c.get("/api/version").json()
        for key in ("git_commit", "started_at", "dist_built", "api_routes"):
            self.assertIn(key, v)
        self.assertIn("/api/version", v["api_routes"])
        self.assertIn("/api/lab/trials", v["api_routes"])

    def test_index_is_not_cached_but_assets_may_be(self):
        c = TestClient(create_app(dist_dir=self.dist))
        self.assertIn("no-cache", c.get("/").headers.get("cache-control", ""))
        self.assertIn("no-cache", c.get("/some/client/route").headers.get("cache-control", ""))


if __name__ == "__main__":
    unittest.main()
