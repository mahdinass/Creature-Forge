"""The Forge router is mounted in the real Studio app, before the /api catch-all, and creates nothing until used."""
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from creature_forge.studio.app import create_app


class ForgeWiringTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.forge = Path(self.tmp.name) / "forge"
        self.client = TestClient(create_app(forge_dir=self.forge))

    def tearDown(self):
        self.tmp.cleanup()

    def test_forge_routes_reach_the_router_not_the_catch_all(self):
        r = self.client.get("/api/forge/creatures")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])
        self.assertEqual(self.client.get("/api/forge/status").status_code, 200)

    def test_unknown_forge_path_is_a_json_404(self):
        r = self.client.get("/api/forge/no-such-thing")
        self.assertEqual(r.status_code, 404)
        self.assertIn("detail", r.json())

    def test_status_never_leaks_the_key_and_nothing_is_created_by_reads(self):
        body = self.client.get("/api/forge/status").text
        self.assertNotIn("NEBIUS_API_KEY=", body)
        self.assertFalse((self.forge / "jobs").exists())

    def test_version_lists_forge_routes(self):
        routes = self.client.get("/api/version").json()["api_routes"]
        self.assertIn("/api/forge/creatures", routes)


if __name__ == "__main__":
    unittest.main()
